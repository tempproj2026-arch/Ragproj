import json
import re
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
import numpy as np
from PIL import Image
from rapidocr import RapidOCR

from ragcore.paths import get_data_root, get_page_dir, resolve_path
from ragcore.logging import get_logger

logger = get_logger("ingestion.extract.number_check")

_ocr_engine: Optional[RapidOCR] = None

def get_ocr_engine() -> RapidOCR:
    """Returns singleton RapidOCR instance."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine

def normalize_number(num_str: str) -> str:
    """Normalizes numeric representations for fair comparison (e.g. '1,200' -> '1200', '.777' -> '0.777')."""
    s = num_str.strip().replace(",", "")
    if s.startswith(".") and s[1:].isdigit():
        s = "0" + s
    if s.startswith("-.") and s[2:].isdigit():
        s = "-0" + s[1:]
    return s

def extract_numbers(text: str) -> Set[str]:
    """
    Extracts all numeric tokens from text: integers, decimals, fractions, and ranges.
    """
    if not text:
        return set()

    # Pattern matches:
    # 1. Fractions like 1 11/16 or 11/16
    # 2. Decimals/integers like -140, .7777, 1,200, 33,000, 3.1415
    pattern = r'(?:(?:\b\d+\s+)?\b\d+/\d+\b)|(?:-?\b(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?\b|-?\b\.\d+\b)'
    raw_matches = re.findall(pattern, text)

    results = set()
    for m in raw_matches:
        m_clean = m.strip()
        if not m_clean or m_clean in ["-", "."]:
            continue
        # If it's pure decimal/int, normalize
        if "/" not in m_clean:
            results.add(normalize_number(m_clean))
        else:
            results.add(m_clean)
    return results

def run_ocr_on_crop(image_path: Path) -> List[str]:
    """Runs RapidOCR on a cropped image and returns detected text strings."""
    ocr = get_ocr_engine()
    img = Image.open(image_path).convert("RGB")
    res = ocr(np.array(img))
    if res and getattr(res, "txts", None):
        return list(res.txts)
    return []

def cross_check_numbers(
    image_path: Path,
    vlm_text: str,
    kind: str = "table"
) -> Dict[str, Any]:
    """
    Cross-checks numbers extracted by the VLM against a secondary OCR pass on the crop.
    Flags any numbers detected by OCR that the VLM might have missed or transcribed differently.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Crop image not found: {image_path}")

    vlm_numbers = extract_numbers(vlm_text)
    ocr_lines = run_ocr_on_crop(image_path)
    ocr_text = " ".join(ocr_lines)
    ocr_numbers = extract_numbers(ocr_text)

    matched = vlm_numbers.intersection(ocr_numbers)
    vlm_only = vlm_numbers - ocr_numbers
    ocr_only = ocr_numbers - vlm_numbers

    total_unique = len(vlm_numbers.union(ocr_numbers))
    if total_unique == 0:
        agreement_rate = 1.0
    else:
        agreement_rate = len(matched) / total_unique

    # We flag as a discrepancy if OCR detected high-confidence digits that the VLM missed,
    # or if the agreement rate is low on content that has multiple numbers.
    has_discrepancy = False
    if kind in ["table", "formula"]:
        if len(ocr_only) > 0 and len(vlm_numbers) < len(ocr_numbers):
            has_discrepancy = True
        elif total_unique >= 4 and agreement_rate < 0.5:
            has_discrepancy = True

    return {
        "has_discrepancy": has_discrepancy,
        "agreement_rate": round(agreement_rate, 3),
        "vlm_number_count": len(vlm_numbers),
        "ocr_number_count": len(ocr_numbers),
        "matched_count": len(matched),
        "vlm_only": sorted(list(vlm_only)),
        "ocr_only": sorted(list(ocr_only)),
        "matched": sorted(list(matched)),
    }

def check_page_numbers(
    book_slug: str,
    page_number: int
) -> Dict[str, Any]:
    """
    Performs number cross-checks on all regions of a page and records verification in page.json.
    """
    page_dir = get_page_dir(book_slug, page_number)
    page_json_path = page_dir / "page.json"

    if not page_json_path.exists():
        raise FileNotFoundError(f"page.json not found: {page_json_path}")

    with open(page_json_path, "r", encoding="utf-8") as f:
        page_meta = json.load(f)

    regions = page_meta.get("regions", [])
    discrepancies = 0

    for reg in regions:
        kind = reg.get("kind", "text")
        vlm_text = reg.get("extracted_text", "")
        rel_img_path = reg.get("image_path")
        # Cross-check visual elements that have crop images (tables, formulas)
        if rel_img_path and kind in ["table", "formula"]:
            abs_img_path = resolve_path(rel_img_path)
            check_result = cross_check_numbers(abs_img_path, vlm_text, kind=kind)
            reg["flags"] = reg.get("flags", {})
            reg["flags"]["number_check"] = check_result

            if check_result["has_discrepancy"]:
                reg["flags"]["discrepancy"] = True
                discrepancies += 1

    page_flags = page_meta.get("flags", {})
    if discrepancies > 0:
        page_flags["has_number_discrepancies"] = True
        page_flags["discrepancy_count"] = discrepancies
    else:
        page_flags["has_number_discrepancies"] = False

    page_meta["flags"] = page_flags

    with open(page_json_path, "w", encoding="utf-8") as f:
        json.dump(page_meta, f, indent=2)

    return {
        "book_slug": book_slug,
        "page_number": page_number,
        "regions_checked": len(regions),
        "discrepancies_found": discrepancies
    }

if __name__ == "__main__":
    # Test on page 2
    res = check_page_numbers("chapter_1_2_3_scanned", 2)
    print("Page 2 Number Check Result:", res)
