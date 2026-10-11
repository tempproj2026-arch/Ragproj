import json
import time
from pathlib import Path
from typing import Dict, Any, List

from ragcore.paths import get_data_root, get_book_dir, get_page_dir
from ragcore.logging import get_logger
from ingestion.extract.vlm_client import extract_page_regions_vlm
from ingestion.extract.number_check import check_page_numbers

logger = get_logger("ingestion.pipeline")

def run_extraction_pipeline(
    book_slug: str,
    force: bool = False
) -> Dict[str, Any]:
    """
    Orchestrates the VLM region extraction and dual-pass number cross-checking
    for all pages in a book. Supports resuming if interrupted.
    """
    book_dir = get_book_dir(book_slug)
    book_json_path = book_dir / "book.json"

    if not book_json_path.exists():
        raise FileNotFoundError(f"book.json not found for book: {book_slug}")

    with open(book_json_path, "r", encoding="utf-8") as f:
        book_info = json.load(f)

    total_pages = book_info.get("page_count", 0)
    logger.info(f"=== Starting Extraction for Book: {book_slug} ({total_pages} pages) ===")

    start_time = time.time()
    pages_processed = 0
    pages_skipped = 0
    total_discrepancies = 0

    for page_num in range(1, total_pages + 1):
        page_dir = get_page_dir(book_slug, page_num)
        page_json_path = page_dir / "page.json"

        if not page_json_path.exists():
            continue

        try:
            with open(page_json_path, "r", encoding="utf-8") as f:
                page_meta = json.load(f)
        except Exception:
            page_meta = {}

        # Check if already completed and verified
        already_extracted = page_meta.get("status") == "vlm_extracted" and "has_number_discrepancies" in page_meta.get("flags", {})
        if not force and already_extracted:
            pages_skipped += 1
            continue

        logger.info(f"[{book_slug}] Processing Page {page_num}/{total_pages}...")
        t_page = time.time()

        try:
            # Step 1: VLM extraction on all regions
            vlm_res = extract_page_regions_vlm(book_slug, page_num, force=force)

            # Step 2: Number cross-check
            num_res = check_page_numbers(book_slug, page_num)
            discrepancies = num_res.get("discrepancies_found", 0)
            total_discrepancies += discrepancies

            duration = time.time() - t_page
            logger.info(
                f"[{book_slug}] Page {page_num} done in {duration:.1f}s | "
                f"Regions: {vlm_res.get('regions_extracted', 0)} | "
                f"Discrepancies: {discrepancies}"
            )
            pages_processed += 1
        except Exception as e:
            logger.error(f"[{book_slug}] Error processing page {page_num}: {e}")
            raise e

    elapsed = time.time() - start_time
    logger.info(
        f"=== Finished {book_slug}: {pages_processed} pages processed, "
        f"{pages_skipped} pages skipped, {total_discrepancies} discrepancies flagged in {elapsed:.1f}s ==="
    )

    return {
        "book_slug": book_slug,
        "total_pages": total_pages,
        "pages_processed": pages_processed,
        "pages_skipped": pages_skipped,
        "discrepancies_found": total_discrepancies,
        "duration_seconds": round(elapsed, 1)
    }

def run_all_books_pipeline(force: bool = False) -> List[Dict[str, Any]]:
    """Runs extraction and verification across all books in data/books/."""
    data_root = get_data_root()
    books_root = data_root / "books"

    results = []
    for book_folder in books_root.iterdir():
        if book_folder.is_dir() and (book_folder / "book.json").exists():
            res = run_extraction_pipeline(book_folder.name, force=force)
            results.append(res)
    return results

if __name__ == "__main__":
    results = run_all_books_pipeline()
    print("\n--- Pipeline Summary ---")
    for r in results:
        print(r)
