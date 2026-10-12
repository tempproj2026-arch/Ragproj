import argparse
import sys
import time
from pathlib import Path

from ragcore.config import settings
from ragcore.logging import get_logger

logger = get_logger("ingestion.cli")

def cmd_ingest(args):
    """Executes the full end-to-end ingestion pipeline on a scanned PDF."""
    from ingestion.split_pages import split_pdf
    from ingestion.extract.layout import extract_book_layout
    from ingestion.pipeline import run_extraction_pipeline
    from ingestion.chunking.orchestrator import ChunkingOrchestrator
    from ingestion.indexer import Indexer
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        sys.exit(1)

    book_slug = args.slug or pdf_path.stem
    book_title = args.title or book_slug.replace("_", " ").title()
    dpi_scale = args.dpi_scale
    force = args.force

    print("\n" + "=" * 65)
    print(f"      STARTING FULL INGESTION PIPELINE: {book_slug}")
    print("=" * 65)
    print(f"PDF Source:  {pdf_path}")
    print(f"Book Slug:   {book_slug}")
    print(f"Book Title:  {book_title}")
    print(f"DPI Scale:   {dpi_scale} (Render resolution: {int(72 * dpi_scale)} DPI)")
    print(f"Force Mode:  {force}\n")

    t_start = time.time()

    # Step 1: Render pages to 216 DPI PNGs
    print("[1/5] Splitting PDF into high-res 216 DPI page images...")
    split_res = split_pdf(pdf_path, book_slug=book_slug, dpi_scale=dpi_scale, force=force)
    print(f"      Rendered {split_res.get('page_count', 0)} pages.\n")

    # Step 2: Docling layout analysis and native OCR
    print("[2/5] Running Docling layout analysis & native OCR...")
    layout_res = extract_book_layout(book_slug, pdf_path, force=force)
    print(f"      Extracted {layout_res.get('total_regions', 0)} regions ({layout_res.get('visual_regions_count', 0)} visual crops).\n")

    # Step 3: VLM visual extraction & dual-pass verification
    print("[3/5] Running Vision Language Model extraction on visual crops...")
    vlm_res = run_extraction_pipeline(book_slug, force=force)
    print(f"      Completed VLM extraction for {vlm_res.get('pages_processed', 0)} pages.\n")

    # Step 4: Multi-modal Chunking
    print("[4/5] Chunking content (semantic text, markdown tables, formulas, figures)...")
    orchestrator = ChunkingOrchestrator()
    chunk_res = orchestrator.chunk_book(book_slug)
    print(f"      Generated {chunk_res.get('total_chunks', 0)} chunks and {chunk_res.get('total_figures', 0)} figures.\n")

    # Step 5: Database Indexing into PostgreSQL
    print("[5/5] Indexing into PostgreSQL 16 + pgvector...")
    indexer = Indexer()
    indexer.init_meta()
    idx_res = indexer.index_book(book_slug, title=book_title)
    print(f"      Indexed {idx_res['chunks_indexed']} chunks and {idx_res['figures_indexed']} figures in {idx_res['elapsed_seconds']}s.\n")

    total_time = time.time() - t_start
    print("=" * 65)
    print(f"SUCCESS: Ingestion of '{book_slug}' completed in {total_time:.2f}s!")
    print("=" * 65 + "\n")

def cmd_reindex(args):
    """Re-chunks and re-indexes existing books into PostgreSQL."""
    from ingestion.indexer import Indexer
    from ingestion.chunking.orchestrator import ChunkingOrchestrator

    indexer = Indexer()
    indexer.init_meta()
    orchestrator = ChunkingOrchestrator()

    if args.book:
        print(f"--- Re-indexing Book: {args.book} ---")
        orchestrator.chunk_book(args.book)
        indexer.index_book(args.book)
    else:
        print("--- Re-indexing All Books ---")
        books_dir = Path(settings.data_root) / "books"
        for b in sorted(books_dir.iterdir()):
            if b.is_dir() and (b / "pages").exists():
                orchestrator.chunk_book(b.name)
        indexer.index_all()
    print("Re-indexing complete!\n")

def cmd_status(args):
    """Displays database health, row counts, and indexed catalog."""
    from ragcore.db.connection import Database
    print("\n=== PostgreSQL RAG Database Status ===")
    try:
        with Database.get_connection(timeout=5.0) as conn:
            with conn.cursor() as cur:
                # Meta info
                cur.execute("SELECT schema_version, text_model_name, text_model_dim, image_model_name, image_model_dim FROM meta LIMIT 1")
                m = cur.fetchone()
                if m:
                    print(f"Schema Version:   {m[0]}")
                    print(f"Text Model:       {m[1]} ({m[2]} dimensions)")
                    print(f"Vision Model:     {m[3]} ({m[4]} dimensions)")

                print("\n--- Row Counts ---")
                for tbl in ["documents", "pages", "regions", "chunks", "figures"]:
                    cur.execute(f"SELECT count(*) FROM {tbl}")
                    print(f"  {tbl:<12}: {cur.fetchone()[0]}")

                print("\n--- Indexed Books Catalog ---")
                cur.execute("""
                    SELECT d.id, d.slug, d.title, d.page_count, count(c.id) as chunks
                    FROM documents d
                    LEFT JOIN chunks c ON c.document_id = d.id
                    GROUP BY d.id, d.slug, d.title, d.page_count
                    ORDER BY d.id
                """)
                rows = cur.fetchall()
                for r in rows:
                    print(f"  ID {r[0]}: [{r[1]}] '{r[2]}' ({r[3]} pages, {r[4]} chunks)")
    except Exception as e:
        print(f"Database Connection Error: {e}")
        print("Ensure Docker container 'rag_postgres_dev' is running on port 5432.")
    print("======================================\n")

def cmd_benchmark(args):
    """Executes the 56-question accuracy evaluation benchmark."""
    from tests.test_eval_benchmark import run_evaluation
    run_evaluation()

def main():
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.cli",
        description="Unified Ingestion and Management CLI for Technical Book RAG"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest subcommand
    p_ingest = subparsers.add_parser("ingest", help="Run full ingestion on a PDF file")
    p_ingest.add_argument("--pdf", required=True, help="Path to input scanned PDF")
    p_ingest.add_argument("--slug", help="Optional book slug identifier")
    p_ingest.add_argument("--title", help="Optional book title")
    p_ingest.add_argument("--dpi-scale", type=float, default=3.0, help="DPI scale factor (default 3.0 = 216 DPI)")
    p_ingest.add_argument("--force", action="store_true", help="Force overwrite of existing files")
    p_ingest.set_defaults(func=cmd_ingest)

    # Reindex subcommand
    p_reindex = subparsers.add_parser("reindex", help="Re-chunk and re-embed existing books into PostgreSQL")
    p_reindex.add_argument("--book", help="Optional specific book slug to reindex")
    p_reindex.set_defaults(func=cmd_reindex)

    # Status subcommand
    p_status = subparsers.add_parser("status", help="Check database connection and table counts")
    p_status.set_defaults(func=cmd_status)

    # Benchmark subcommand
    p_bench = subparsers.add_parser("benchmark", help="Run the 56-question evaluation benchmark")
    p_bench.set_defaults(func=cmd_benchmark)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
