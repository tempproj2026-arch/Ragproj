import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from ragcore.paths import get_data_root, get_book_dir, get_page_dir
from ragcore.logging import get_logger

from .text import chunk_text_regions
from .table import chunk_table_region
from .formula import chunk_formula_region
from .figure import chunk_figure_region

logger = get_logger("ingestion.chunking.orchestrator")

def chunk_page(
    book_slug: str,
    page_number: int,
    current_section: str = "Introduction"
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """
    Chunks all regions on a single page, maintaining section continuity.
    Returns (chunks, figure_records, updated_section).
    """
    page_dir = get_page_dir(book_slug, page_number)
    page_json_path = page_dir / "page.json"

    if not page_json_path.exists():
        logger.warning(f"page.json not found for {book_slug} p{page_number:04d}")
        return [], [], current_section

    with open(page_json_path, "r", encoding="utf-8") as f:
        page_meta = json.load(f)

    regions = page_meta.get("regions", [])
    if not regions:
        return [], [], current_section

    page_chunks = []
    page_figures = []
    active_section = current_section

    # Group sequential text regions together while dispatching visual regions individually
    text_buffer = []

    def flush_text_buffer(sec: str) -> str:
        nonlocal page_chunks, text_buffer
        if not text_buffer:
            return sec
        t_chunks = chunk_text_regions(
            regions=text_buffer,
            book_slug=book_slug,
            page_number=page_number,
            current_section=sec
        )
        page_chunks.extend(t_chunks)
        # Update active section if any chunk introduced a new one
        if t_chunks:
            sec = t_chunks[-1].get("section", sec)
        text_buffer = []
        return sec

    for reg in regions:
        kind = reg.get("kind", "text")

        if kind == "text":
            text_buffer.append(reg)
        else:
            # Flush accumulated text before visual element
            active_section = flush_text_buffer(active_section)

            if kind == "table":
                t_chunks = chunk_table_region(
                    region=reg,
                    book_slug=book_slug,
                    page_number=page_number,
                    current_section=active_section
                )
                page_chunks.extend(t_chunks)

            elif kind == "formula":
                f_chunks = chunk_formula_region(
                    region=reg,
                    book_slug=book_slug,
                    page_number=page_number,
                    current_section=active_section
                )
                page_chunks.extend(f_chunks)

            elif kind == "figure":
                fig_chunk, fig_rec = chunk_figure_region(
                    region=reg,
                    book_slug=book_slug,
                    page_number=page_number,
                    current_section=active_section
                )
                if fig_chunk:
                    page_chunks.append(fig_chunk)
                if fig_rec:
                    page_figures.append(fig_rec)

    # Flush any remaining text at the end of the page
    active_section = flush_text_buffer(active_section)

    return page_chunks, page_figures, active_section

def chunk_book(book_slug: str) -> Dict[str, Any]:
    """
    Performs domain-aware chunking for all pages of a book.
    Saves chunks.json and figures.json in the book root directory.
    """
    book_dir = get_book_dir(book_slug)
    book_json_path = book_dir / "book.json"

    if not book_json_path.exists():
        raise FileNotFoundError(f"book.json not found for book: {book_slug}")

    with open(book_json_path, "r", encoding="utf-8") as f:
        book_info = json.load(f)

    total_pages = book_info.get("page_count", 0)
    logger.info(f"=== Starting Chunking for Book: {book_slug} ({total_pages} pages) ===")

    all_chunks = []
    all_figures = []
    active_section = f"Book: {book_slug}"

    for page_num in range(1, total_pages + 1):
        chunks, figures, active_section = chunk_page(
            book_slug=book_slug,
            page_number=page_num,
            current_section=active_section
        )
        all_chunks.extend(chunks)
        all_figures.extend(figures)

    # Assign sequential IDs and document slug
    type_counts = {}
    for i, c in enumerate(all_chunks):
        c["chunk_id"] = f"{book_slug}_c{i+1:05d}"
        c["book_slug"] = book_slug
        c_type = c.get("content_type", "unknown")
        type_counts[c_type] = type_counts.get(c_type, 0) + 1

    for i, f in enumerate(all_figures):
        f["figure_id"] = f"{book_slug}_fig{i+1:04d}"

    # Save chunks.json
    chunks_path = book_dir / "chunks.json"
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)

    # Save figures.json
    figures_path = book_dir / "figures.json"
    with open(figures_path, "w", encoding="utf-8") as f:
        json.dump(all_figures, f, indent=2)

    logger.info(
        f"=== Finished Chunking {book_slug}: {len(all_chunks)} chunks, "
        f"{len(all_figures)} figures saved. Type counts: {type_counts} ==="
    )

    return {
        "book_slug": book_slug,
        "total_pages": total_pages,
        "total_chunks": len(all_chunks),
        "total_figures": len(all_figures),
        "type_counts": type_counts,
        "chunks_path": str(chunks_path),
        "figures_path": str(figures_path)
    }

def chunk_all_books() -> List[Dict[str, Any]]:
    """Chunks all books found under data/books/."""
    data_root = get_data_root()
    books_root = data_root / "books"
    results = []

    for book_folder in sorted(books_root.iterdir()):
        if book_folder.is_dir() and (book_folder / "book.json").exists():
            res = chunk_book(book_folder.name)
            results.append(res)

    return results

if __name__ == "__main__":
    summaries = chunk_all_books()
    for s in summaries:
        print(s)
