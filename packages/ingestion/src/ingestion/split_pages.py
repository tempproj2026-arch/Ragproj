import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
import pypdfium2 as pdfium
from PIL import Image

from ragcore.config import settings
from ragcore.paths import get_data_root, get_book_dir, get_page_dir, get_relative_path
from ragcore.logging import get_logger

logger = get_logger("ingestion.split_pages")

def compute_file_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def compute_bytes_sha256(data: bytes) -> str:
    """Computes SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()

def split_pdf(
    pdf_path: Path,
    book_slug: Optional[str] = None,
    dpi_scale: float = 3.0,  # 72 dpi * 3.0 = 216 dpi (200-300 dpi standard)
    force: bool = False
) -> Dict[str, Any]:
    """
    Splits a PDF into per-page folders with page.png, regions/ folder, and page.json.
    
    Layout:
    data/books/<book_slug>/
        book.json
        pages/
            p0001/
                page.png
                page.json
                regions/
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if book_slug is None:
        book_slug = pdf_path.stem

    data_root = get_data_root()
    book_dir = get_book_dir(book_slug)
    book_dir.mkdir(parents=True, exist_ok=True)
    pages_root = book_dir / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)

    file_hash = compute_file_sha256(pdf_path)
    logger.info(f"Splitting {pdf_path.name} (slug={book_slug}, hash={file_hash[:8]}...)")

    doc = pdfium.PdfDocument(str(pdf_path))
    total_pages = len(doc)

    book_info = {
        "slug": book_slug,
        "title": book_slug.replace("_", " ").title(),
        "source_file": pdf_path.name,
        "source_hash": file_hash,
        "page_count": total_pages,
        "dpi": int(72 * dpi_scale),
    }

    # Save book.json
    book_json_path = book_dir / "book.json"
    with open(book_json_path, "w", encoding="utf-8") as f:
        json.dump(book_info, f, indent=2)

    pages_created = 0
    pages_skipped = 0

    for i in range(total_pages):
        page_num = i + 1
        page_dir = get_page_dir(book_slug, page_num)
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "regions").mkdir(parents=True, exist_ok=True)

        page_png_path = page_dir / "page.png"
        page_json_path = page_dir / "page.json"

        # Check if already processed
        if not force and page_png_path.exists() and page_json_path.exists():
            try:
                with open(page_json_path, "r", encoding="utf-8") as f:
                    cached_meta = json.load(f)
                if cached_meta.get("status") in ["split", "extracted", "indexed"]:
                    pages_skipped += 1
                    continue
            except Exception:
                pass  # Recreate if corrupt

        # Render page
        page = doc[i]
        pil_image: Image.Image = page.render(scale=dpi_scale).to_pil()
        pil_image.save(page_png_path, format="PNG", optimize=True)

        with open(page_png_path, "rb") as f:
            page_hash = compute_bytes_sha256(f.read())

        page_meta = {
            "page_number": page_num,
            "book_slug": book_slug,
            "page_hash": page_hash,
            "image_path": get_relative_path(page_png_path),
            "width": pil_image.width,
            "height": pil_image.height,
            "dpi": int(72 * dpi_scale),
            "status": "split",
            "regions": [],
            "reading_order": [],
            "flags": {}
        }

        with open(page_json_path, "w", encoding="utf-8") as f:
            json.dump(page_meta, f, indent=2)

        pages_created += 1

    logger.info(f"Finished {book_slug}: {pages_created} pages rendered, {pages_skipped} pages skipped.")
    return {
        "book_slug": book_slug,
        "page_count": total_pages,
        "pages_created": pages_created,
        "pages_skipped": pages_skipped
    }

if __name__ == "__main__":
    import sys
    data_root = get_data_root()
    input_dir = data_root / "input"
    for pdf in input_dir.glob("*.pdf"):
        split_pdf(pdf)
