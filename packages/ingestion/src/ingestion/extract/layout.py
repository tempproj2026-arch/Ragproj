import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import DocItemLabel

from ragcore.config import settings
from ragcore.paths import get_data_root, get_book_dir, get_page_dir, get_relative_path
from ragcore.logging import get_logger

logger = get_logger("ingestion.extract.layout")

_converter: Optional[DocumentConverter] = None

def get_layout_converter() -> DocumentConverter:
    """Initializes and returns cached DocumentConverter with layout-only pipeline (no slow CPU OCR)."""
    global _converter
    if _converter is None:
        opts = PdfPipelineOptions()
        opts.do_ocr = False
        opts.do_table_structure = True
        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
    return _converter

def map_docling_label_to_kind(label: Any) -> str:
    """Maps Docling labels to our 4 canonical kinds: text, table, formula, figure."""
    label_str = str(label).lower()
    if "picture" in label_str or "figure" in label_str or "graphic" in label_str:
        return "figure"
    elif "table" in label_str:
        return "table"
    elif "formula" in label_str or "equation" in label_str:
        return "formula"
    else:
        return "text"

def extract_book_layout(
    book_slug: str,
    pdf_path: Path,
    force: bool = False
) -> Dict[str, Any]:
    """
    Runs Docling layout extraction on a book's PDF, identifies regions (text, table,
    formula, figure), crops region images to regions/rXXX_<kind>.png, and updates page.json.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    book_dir = get_book_dir(book_slug)
    logger.info(f"Extracting layout for book {book_slug} using Docling...")

    converter = get_layout_converter()
    conv_result = converter.convert(str(pdf_path))
    doc = conv_result.document

    # Group items by page_no (1-indexed)
    page_items: Dict[int, List[Any]] = {}
    for item, level in doc.iterate_items():
        prov_list = getattr(item, "prov", None)
        if prov_list and len(prov_list) > 0:
            page_no = prov_list[0].page_no
            if page_no not in page_items:
                page_items[page_no] = []
            page_items[page_no].append(item)

    total_regions = 0
    pages_processed = 0

    total_pages = len(doc.pages)
    for page_no in range(1, total_pages + 1):
        items = page_items.get(page_no, [])
        page_dir = get_page_dir(book_slug, page_no)
        page_png = page_dir / "page.png"
        page_json_path = page_dir / "page.json"
        regions_dir = page_dir / "regions"
        regions_dir.mkdir(parents=True, exist_ok=True)

        if not page_png.exists() or not page_json_path.exists():
            continue

        try:
            with open(page_json_path, "r", encoding="utf-8") as f:
                page_meta = json.load(f)
        except Exception:
            page_meta = {"page_number": page_no, "book_slug": book_slug}

        if not force and page_meta.get("status") in ["extracted", "indexed"] and page_meta.get("regions"):
            continue

        img = Image.open(page_png)
        img_w, img_h = img.width, img.height

        p_size = doc.pages[page_no].size
        pdf_w = p_size.width
        pdf_h = p_size.height

        scale_x = img_w / pdf_w
        scale_y = img_h / pdf_h

        region_records = []
        reading_order = []

        for r_idx, item in enumerate(items, start=1):
            prov = item.prov[0]
            bbox = prov.bbox
            kind = map_docling_label_to_kind(getattr(item, "label", "text"))
            reg_id = f"r{r_idx:03d}_{kind}"

            # Convert Docling bottom-left coords to PIL top-left pixel coords
            x0 = max(0, int(round(bbox.l * scale_x)))
            y0 = max(0, int(round((pdf_h - bbox.t) * scale_y)))
            x1 = min(img_w, int(round(bbox.r * scale_x)))
            y1 = min(img_h, int(round((pdf_h - bbox.b) * scale_y)))

            # Skip degenerated boxes
            if (x1 - x0) < 5 or (y1 - y0) < 5:
                continue

            # Add minor padding (4px)
            pad = 4
            crop_box = (
                max(0, x0 - pad),
                max(0, y0 - pad),
                min(img_w, x1 + pad),
                min(img_h, y1 + pad),
            )

            crop_img = img.crop(crop_box)
            crop_filename = f"{reg_id}.png"
            crop_path = regions_dir / crop_filename
            crop_img.save(crop_path, format="PNG")

            reg_data = {
                "id": reg_id,
                "kind": kind,
                "label": str(getattr(item, "label", "text")),
                "bbox": [x0, y0, x1, y1],
                "image_path": get_relative_path(crop_path),
                "reading_order": r_idx,
                "flags": {}
            }
            region_records.append(reg_data)
            reading_order.append(reg_id)

        # Fallback: if no distinct sub-regions detected, treat entire page as text region
        if len(region_records) == 0:
            reg_id = "r001_text"
            crop_path = regions_dir / f"{reg_id}.png"
            img.save(crop_path, format="PNG")
            region_records.append({
                "id": reg_id,
                "kind": "text",
                "label": "full_page",
                "bbox": [0, 0, img_w, img_h],
                "image_path": get_relative_path(crop_path),
                "reading_order": 1,
                "flags": {"fallback_full_page": True}
            })
            reading_order.append(reg_id)

        page_meta["regions"] = region_records
        page_meta["reading_order"] = reading_order
        page_meta["status"] = "extracted"

        with open(page_json_path, "w", encoding="utf-8") as f:
            json.dump(page_meta, f, indent=2)

        total_regions += len(region_records)
        pages_processed += 1

    logger.info(f"Book {book_slug}: Extracted {total_regions} regions across {pages_processed} pages.")
    return {
        "book_slug": book_slug,
        "pages_processed": pages_processed,
        "total_regions": total_regions
    }

if __name__ == "__main__":
    data_root = get_data_root()
    input_dir = data_root / "input"
    for pdf_file in input_dir.glob("*.pdf"):
        slug = pdf_file.stem
        extract_book_layout(slug, pdf_file)
