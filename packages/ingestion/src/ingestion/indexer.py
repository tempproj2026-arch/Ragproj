import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ragcore.config import settings
from ragcore.logging import get_logger
from ragcore.db.connection import Database
from ragcore.embeddings import embed_texts, embed_figures

logger = get_logger("ingestion.indexer")

class Indexer:
    def __init__(self, data_root: Optional[Path] = None):
        self.data_root = Path(data_root or settings.data_root)

    def init_meta(self):
        """Ensures the meta table has accurate provenance records."""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO meta (schema_version, text_model_name, text_model_dim, image_model_name, image_model_dim)
                    VALUES (1, 'BAAI/bge-m3', 1024, 'google/siglip-so400m-patch14-384', 1152)
                    ON CONFLICT (schema_version) DO UPDATE SET
                        text_model_name = EXCLUDED.text_model_name,
                        text_model_dim = EXCLUDED.text_model_dim,
                        image_model_name = EXCLUDED.image_model_name,
                        image_model_dim = EXCLUDED.image_model_dim;
                """)
            conn.commit()
        logger.info("Database 'meta' table verified.")

    def index_book(self, book_slug: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Indexes an entire book:
        1. Inserts/updates document record.
        2. Inserts pages and detected regions.
        3. Computes text embeddings and inserts chunks with full-text search vector.
        4. Computes visual embeddings and inserts figures.
        """
        book_dir = self.data_root / "books" / book_slug
        if not book_dir.exists():
            raise FileNotFoundError(f"Book directory not found: {book_dir}")

        chunks_file = book_dir / "chunks.json"
        figures_file = book_dir / "figures.json"

        if not chunks_file.exists():
            raise FileNotFoundError(f"chunks.json not found in {book_dir}. Run chunking first.")
        if not figures_file.exists():
            raise FileNotFoundError(f"figures.json not found in {book_dir}. Run chunking first.")

        with open(chunks_file, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)

        with open(figures_file, "r", encoding="utf-8") as f:
            figures_data = json.load(f)

        # Scan pages in directory
        pages_dir = book_dir / "pages"
        page_folders = sorted([p for p in pages_dir.iterdir() if p.is_dir() and p.name.startswith("p")])
        page_count = len(page_folders)

        book_title = title or book_slug.replace("_", " ").title()
        root_path = f"books/{book_slug}"

        start_time = time.time()
        logger.info(f"--- Indexing {book_slug} ({page_count} pages, {len(chunks_data)} chunks, {len(figures_data)} figures) ---")

        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Insert or update document
                cur.execute("""
                    INSERT INTO documents (slug, title, source_hash, page_count, root_path)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE SET
                        title = EXCLUDED.title,
                        page_count = EXCLUDED.page_count,
                        root_path = EXCLUDED.root_path
                    RETURNING id;
                """, (book_slug, book_title, f"hash_{book_slug}", page_count, root_path))
                doc_id = cur.fetchone()[0]

                # Clear old data for this document to ensure clean re-indexing
                cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
                cur.execute("DELETE FROM figures WHERE image_path LIKE %s", (f"books/{book_slug}%",))
                cur.execute("DELETE FROM pages WHERE document_id = %s", (doc_id,))
                conn.commit()

                logger.info(f"Document registered: ID={doc_id}, Slug='{book_slug}'")

                # 2. Insert pages and regions
                region_map: Dict[Tuple[int, str], int] = {}  # (page_number, region_id_str) -> region_db_id

                for p_folder in page_folders:
                    page_num_str = p_folder.name[1:]
                    page_num = int(page_num_str)

                    page_json_path = p_folder / "page.json"
                    page_data = {}
                    if page_json_path.exists():
                        with open(page_json_path, "r", encoding="utf-8") as pf:
                            page_data = json.load(pf)

                    page_hash = page_data.get("page_hash", f"hash_p{page_num:04d}")
                    page_rel_folder = f"books/{book_slug}/pages/{p_folder.name}"
                    page_rel_image = page_data.get("image_path", f"{page_rel_folder}/page.png")
                    status = page_data.get("status", "completed")

                    cur.execute("""
                        INSERT INTO pages (document_id, page_number, page_hash, folder_path, image_path, status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id;
                    """, (doc_id, page_num, page_hash, page_rel_folder, page_rel_image, status))
                    page_db_id = cur.fetchone()[0]

                    # Insert regions for this page
                    regions = page_data.get("regions", [])
                    for reg in regions:
                        reg_id_str = reg.get("id")
                        kind = reg.get("kind", "text")
                        bbox = json.dumps(reg.get("bbox", []))
                        img_path = reg.get("image_path")
                        reading_order = reg.get("reading_order", 0)
                        flags = json.dumps(reg.get("flags", {}))

                        cur.execute("""
                            INSERT INTO regions (page_id, kind, bbox, image_path, reading_order, flags)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id;
                        """, (page_db_id, kind, bbox, img_path, reading_order, flags))
                        reg_db_id = cur.fetchone()[0]

                        if reg_id_str:
                            region_map[(page_num, reg_id_str)] = reg_db_id

                conn.commit()
                logger.info(f"Indexed {len(page_folders)} pages and {len(region_map)} regions.")

                # 3. Compute text embeddings & insert chunks
                logger.info(f"Embedding {len(chunks_data)} text chunks using BAAI/bge-m3 (1024-dim)...")
                chunk_texts = [c["search_text"] for c in chunks_data]
                text_embeddings = embed_texts(chunk_texts, batch_size=32)

                logger.info("Inserting chunks into database...")
                for chunk, embedding in zip(chunks_data, text_embeddings):
                    p_num = chunk["page_number"]
                    r_id_str = chunk.get("region_id")
                    db_reg_id = region_map.get((p_num, r_id_str)) if r_id_str else None

                    cur.execute("""
                        INSERT INTO chunks (
                            document_id, region_id, page_number, content_type,
                            content, search_text, section, embedding, tsv
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s, to_tsvector('english', %s)
                        );
                    """, (
                        doc_id,
                        db_reg_id,
                        p_num,
                        chunk["content_type"],
                        chunk["content"],
                        chunk["search_text"],
                        chunk.get("section"),
                        embedding,
                        chunk["search_text"]
                    ))

                conn.commit()
                logger.info(f"Successfully inserted {len(chunks_data)} chunks with 1024-dim embeddings & tsvector.")

                # 4. Compute figure embeddings & insert figures
                if figures_data:
                    logger.info(f"Embedding {len(figures_data)} figures using Google SigLIP (1152-dim)...")
                    fig_paths = [self.data_root / f["image_path"] for f in figures_data]
                    fig_embeddings = embed_figures(fig_paths, batch_size=16)

                    logger.info("Inserting figures into database...")
                    for fig, embedding in zip(figures_data, fig_embeddings):
                        p_num = fig["page_number"]
                        r_id_str = fig.get("region_id")
                        db_reg_id = region_map.get((p_num, r_id_str)) if r_id_str else None

                        cur.execute("""
                            INSERT INTO figures (
                                region_id, caption, description, image_path, embedding
                            ) VALUES (
                                %s, %s, %s, %s, %s
                            );
                        """, (
                            db_reg_id,
                            fig.get("caption"),
                            fig.get("description"),
                            fig["image_path"],
                            embedding
                        ))

                    conn.commit()
                    logger.info(f"Successfully inserted {len(figures_data)} figures with 1152-dim embeddings.")

        elapsed = time.time() - start_time
        summary = {
            "book_slug": book_slug,
            "document_id": doc_id,
            "pages_indexed": page_count,
            "chunks_indexed": len(chunks_data),
            "figures_indexed": len(figures_data),
            "elapsed_seconds": round(elapsed, 2)
        }
        logger.info(f"Indexing completed for {book_slug} in {elapsed:.2f}s: {summary}")
        return summary

    def index_all(self) -> List[Dict[str, Any]]:
        """Indexes all books available in the data directory."""
        self.init_meta()
        books_dir = self.data_root / "books"
        results = []
        for book_folder in sorted(books_dir.iterdir()):
            if book_folder.is_dir() and (book_folder / "chunks.json").exists():
                res = self.index_book(book_folder.name)
                results.append(res)
        return results

if __name__ == "__main__":
    indexer = Indexer()
    all_res = indexer.index_all()
    print("\n--- Final Indexing Report ---")
    for r in all_res:
        print(f"Book: {r['book_slug']} | Pages: {r['pages_indexed']} | Chunks: {r['chunks_indexed']} | Figures: {r['figures_indexed']} | Time: {r['elapsed_seconds']}s")
