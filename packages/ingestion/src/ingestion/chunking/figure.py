import re
from typing import Dict, Any, Tuple, Optional

def extract_figure_title_and_caption(description: str) -> Tuple[str, str]:
    """
    Extracts figure title (e.g. 'Fig. 35. - Sand filter for eight people')
    and clean description text from the VLM output.
    """
    if not description:
        return "Technical Figure", ""

    lines = [l.strip() for l in description.splitlines() if l.strip()]
    title = ""

    # Look for patterns like 'Fig. 35', 'Figure 3', '**Fig. 35**'
    for line in lines[:5]:
        m = re.search(r'(?:Fig(?:ure)?\.?\s*\d+[^.\n]*\.?)', line, re.IGNORECASE)
        if m:
            title = m.group(0).strip("*_# ")
            break

    if not title and lines:
        first_line = lines[0].lstrip("*# ").strip()
        if len(first_line) < 80:
            title = first_line

    if not title:
        title = "Technical Diagram"

    return title, description

def chunk_figure_region(
    region: Dict[str, Any],
    book_slug: str,
    page_number: int,
    current_section: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Extracts a searchable text Chunk and a standalone Figure database record
    from a figure region.
    """
    raw_description = region.get("extracted_text", "")
    rel_img_path = region.get("image_path", "")
    reg_id = region.get("id")

    if not raw_description and not rel_img_path:
        return None, None

    title, clean_desc = extract_figure_title_and_caption(raw_description)
    section_name = title or current_section or "Technical Figure"
    breadcrumb = f"[Book: {book_slug} | Figure: {title} | Page: {page_number}]"

    # 1. Searchable Text Chunk for chunks table
    content_parts = []
    if rel_img_path:
        content_parts.append(f"![{title}]({rel_img_path})\n")
    content_parts.append(f"### {title}\n\n{clean_desc}")
    chunk_content = "\n".join(content_parts)

    search_text = f"{breadcrumb}\nTechnical Diagram, Illustration, Schematic\n\n{clean_desc}"

    chunk = {
        "content_type": "figure",
        "content": chunk_content,
        "search_text": search_text,
        "section": section_name,
        "page_number": page_number,
        "region_id": reg_id,
        "metadata": {
            "region_id": reg_id,
            "image_path": rel_img_path,
            "figure_title": title,
            "char_count": len(chunk_content)
        }
    }

    # 2. Standalone Figure Record for figures table & SigLIP visual embeddings
    figure_record = {
        "region_id": reg_id,
        "page_number": page_number,
        "book_slug": book_slug,
        "caption": title,
        "description": clean_desc,
        "image_path": rel_img_path,
        "bbox": region.get("bbox", [])
    }

    return chunk, figure_record
