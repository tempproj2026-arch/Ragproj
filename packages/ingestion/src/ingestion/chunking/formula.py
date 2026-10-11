import re
from typing import List, Dict, Any, Optional

def clean_formula_content(text: str) -> str:
    """Cleans VLM-generated formula text and ensures clean LaTeX formatting."""
    if not text:
        return ""
    # Strip markdown code fences like ```latex or ```
    text = re.sub(r'^```(?:latex|math)?\s*', '', text.strip(), flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text.strip())
    return text.strip()

def chunk_formula_region(
    region: Dict[str, Any],
    book_slug: str,
    page_number: int,
    current_section: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Creates an atomic chunk for mathematical formulas, bundling LaTeX syntax
    with variable descriptions and mathematical terms.
    """
    raw_text = region.get("extracted_text", "")
    formula_text = clean_formula_content(raw_text)
    reg_id = region.get("id")

    if not formula_text:
        return []

    formula_title = current_section or "Formula"
    breadcrumb = f"[Book: {book_slug} | Formula / Equation | Section: {formula_title} | Page: {page_number}]"

    # Identify LaTeX expressions if present
    has_latex = bool(re.search(r'(\$\$?|\\\[|\\begin\{equation\}|\\frac)', formula_text))
    search_keywords = "Mathematical Formula, Equation, Computation, Calculation"

    search_text = f"{breadcrumb}\n{search_keywords}\n\n{formula_text}"

    return [{
        "content_type": "formula",
        "content": formula_text,
        "search_text": search_text,
        "section": formula_title,
        "page_number": page_number,
        "region_id": reg_id,
        "metadata": {
            "region_id": reg_id,
            "has_latex": has_latex,
            "char_count": len(formula_text)
        }
    }]
