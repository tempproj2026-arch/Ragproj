import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

from ragcore.paths import get_data_root, get_book_dir, get_page_dir, get_relative_path
from ragcore.logging import get_logger

logger = get_logger("ingestion.extract.layout")

_converter: Optional[DocumentConverter] = None

def get_layout_converter() -> DocumentConverter:
    """
    Initializes and returns cached DocumentConverter with full layout detection
    and local RapidOCR with onnxruntime for accurate text and column segmentation.
    """
    global _converter
    if _converter is None:
        opts = PdfPipelineOptions()
        opts.do_ocr = True
        opts.do_table_structure = True
        _converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
    return _converter

def map_docling_label_to_kind(label: Any) -> str:
    """Maps Docling labels to our canonical kinds: text, table, formula, figure."""
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
    Runs Docling with local OCR on the PDF:
    - Extracts all body text, headings, and lists directly with native reading order and two-column handling.
    - Specialized visual elements (figures, tables, formulas) are cropped into regions/ for downstream Vision Model analysis.
    - Text blocks do NOT require image crops or Vision Model calls.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    book_dir = get_book_dir(book_slug)
    logger.info(f"Extracting layout and text for book {book_slug} using Docling with OCR...")

    converter = get_layout_converter()
    conv_result = converter.convert(str(pdf_path))
    doc = conv_result.document

    # Group all items by page_no (1-indexed) in Docling's natural reading order
    page_items: Dict[int, List[Any]] = {}
    for item, level in doc.iterate_items():
        prov_list = getattr(item, "prov", None)
        if prov_list and len(prov_list) > 0:
            page_no = prov_list[0].page_no
            if page_no not in page_items:
                page_items[page_no] = []
            page_items[page_no].append(item)

    total_regions = 0
    special_crops_count = 0
    pages_processed = 0
    total_pages = len(doc.pages)

    for page_no in range(1, total_pages + 1):
        page_dir = get_page_dir(book_slug, page_no)
        page_png = page_dir / "page.png"
        page_json_path = page_dir / "page.json"
        page_md_path = page_dir / "page.md"
        regions_dir = page_dir / "regions"
        regions_dir.mkdir(parents=True, exist_ok=True)

        if not page_png.exists() or not page_json_path.exists():
            continue

        try:
            with open(page_json_path, "r", encoding="utf-8") as f:
                page_meta = json.load(f)
        except Exception:
            page_meta = {"page_number": page_no, "book_slug": book_slug}

        img = Image.open(page_png)
        img_w, img_h = img.width, img.height

        p_size = doc.pages[page_no].size
        pdf_w = p_size.width
        pdf_h = p_size.height

        scale_x = img_w / pdf_w
        scale_y = img_h / pdf_h

        items = page_items.get(page_no, [])
        region_records = []
        reading_order = []
        md_lines = [f"# Book: {book_slug} - Page {page_no}\n"]

        r_counter = 1
        for item in items:
            label_raw = getattr(item, "label", "text")
            kind = map_docling_label_to_kind(label_raw)
            reg_id = f"r{r_counter:03d}_{kind}"

            prov = item.prov[0]
            b = prov.bbox
            x0 = max(0, int(round(b.l * scale_x)))
            y0 = max(0, int(round((pdf_h - b.t) * scale_y)))
            x1 = min(img_w, int(round(b.r * scale_x)))
            y1 = min(img_h, int(round((pdf_h - b.b) * scale_y)))
            bbox = [x0, y0, x1, y1]

            if kind in ["figure", "table", "formula"]:
                # Specialized visual element: Crop to PNG for Vision Model
                crop_box = (
                    max(0, x0 - 4),
                    max(0, y0 - 4),
                    min(img_w, x1 + 4),
                    min(img_h, y1 + 4),
                )
                if (crop_box[2] - crop_box[0]) >= 10 and (crop_box[3] - crop_box[1]) >= 10:
                    crop_img = img.crop(crop_box)
                    crop_filename = f"{reg_id}.png"
                    crop_path = regions_dir / crop_filename
                    crop_img.save(crop_path, format="PNG")

                    reg_data = {
                        "id": reg_id,
                        "kind": kind,
                        "label": str(label_raw),
                        "bbox": bbox,
                        "image_path": get_relative_path(crop_path),
                        "reading_order": r_counter,
                        "needs_vlm": True,
                        "extracted_text": None,
                        "flags": {}
                    }
                    region_records.append(reg_data)
                    reading_order.append(reg_id)
                    md_lines.append(f"<!-- region:{reg_id} kind:{kind} needs_vlm:true -->\n")
                    r_counter += 1
                    special_crops_count += 1
            else:
                # Text element: Take extracted text directly from Docling
                text_content = getattr(item, "text", "")
                if text_content and text_content.strip():
                    text_str = text_content.strip()
                    reg_data = {
                        "id": reg_id,
                        "kind": "text",
                        "label": str(label_raw),
                        "bbox": bbox,
                        "image_path": None,
                        "reading_order": r_counter,
                        "needs_vlm": False,
                        "extracted_text": text_str,
                        "flags": {}
                    }
                    region_records.append(reg_data)
                    reading_order.append(reg_id)
                    md_lines.append(f"<!-- region:{reg_id} kind:text -->\n{text_str}\n")
                    r_counter += 1

        # Write initial page.md with native text
        with open(page_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        page_meta["regions"] = region_records
        page_meta["reading_order"] = reading_order
        page_meta["status"] = "layout_extracted"
        page_meta["special_crops_count"] = sum(1 for r in region_records if r.get("needs_vlm"))

        with open(page_json_path, "w", encoding="utf-8") as f:
            json.dump(page_meta, f, indent=2)

        total_regions += len(region_records)
        pages_processed += 1

    logger.info(
        f"Book {book_slug}: Extracted {total_regions} items ({special_crops_count} visual crops for VLM) "
        f"across {pages_processed} pages."
    )
    return {
        "book_slug": book_slug,
        "pages_processed": pages_processed,
        "total_regions": total_regions,
        "special_crops_count": special_crops_count
    }

if __name__ == "__main__":
    data_root = get_data_root()
    input_dir = data_root / "input"
    for pdf_file in input_dir.glob("*.pdf"):
        extract_book_layout(pdf_file.stem, pdf_file, force=True)
