import re
from typing import List, Dict, Any, Optional

def clean_text(text: str) -> str:
    """Normalizes whitespace and removes unwanted OCR noise."""
    if not text:
        return ""
    # Collapse multiple spaces while preserving newlines
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def split_sentences(text: str) -> List[str]:
    """Splits text into sentences based on punctuation boundaries."""
    # Split on sentence terminals followed by space and capital letter or end of line
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'])', text)
    return [s.strip() for s in sentences if s.strip()]

def chunk_text_regions(
    regions: List[Dict[str, Any]],
    book_slug: str,
    page_number: int,
    current_section: Optional[str] = None,
    target_chars: int = 1200,
    max_chars: int = 1800,
    overlap_chars: int = 150
) -> List[Dict[str, Any]]:
    """
    Groups and chunks sequential text regions on a page into semantic chunks.
    Maintains running section headers and prepends breadcrumbs.
    """
    chunks = []
    active_section = current_section or "General"
    accumulated_texts = []
    accumulated_region_ids = []
    accumulated_len = 0

    for reg in regions:
        if reg.get("kind") != "text":
            continue

        text = clean_text(reg.get("extracted_text", ""))
        if not text:
            continue

        label = reg.get("label", "text")
        reg_id = reg.get("id")

        # Check if this region is a section heading
        is_heading = (
            label in ["section_header", "title", "header"] or
            (len(text) < 100 and text.isupper()) or
            text.startswith("#")
        )

        if is_heading:
            clean_heading = text.lstrip("#").strip()
            # If we had accumulated text, flush it before changing section
            if accumulated_texts:
                combined_content = "\n\n".join(accumulated_texts)
                breadcrumb = f"[Book: {book_slug} | Section: {active_section} | Page: {page_number}]"
                search_text = f"{breadcrumb}\n{combined_content}"
                chunks.append({
                    "content_type": "text",
                    "content": combined_content,
                    "search_text": search_text,
                    "section": active_section,
                    "page_number": page_number,
                    "region_id": accumulated_region_ids[0] if accumulated_region_ids else None,
                    "metadata": {
                        "region_ids": list(accumulated_region_ids),
                        "char_count": len(combined_content)
                    }
                })
                accumulated_texts = []
                accumulated_region_ids = []
                accumulated_len = 0

            active_section = clean_heading
            accumulated_texts.append(f"### {clean_heading}")
            if reg_id:
                accumulated_region_ids.append(reg_id)
            accumulated_len += len(clean_heading) + 5
            continue

        # Regular text paragraph
        # If adding this paragraph exceeds max_chars, flush current accumulated buffer
        if accumulated_len + len(text) > max_chars and accumulated_texts:
            combined_content = "\n\n".join(accumulated_texts)
            breadcrumb = f"[Book: {book_slug} | Section: {active_section} | Page: {page_number}]"
            search_text = f"{breadcrumb}\n{combined_content}"
            chunks.append({
                "content_type": "text",
                "content": combined_content,
                "search_text": search_text,
                "section": active_section,
                "page_number": page_number,
                "region_id": accumulated_region_ids[0] if accumulated_region_ids else None,
                "metadata": {
                    "region_ids": list(accumulated_region_ids),
                    "char_count": len(combined_content)
                }
            })
            accumulated_texts = []
            accumulated_region_ids = []
            accumulated_len = 0

        # If a single paragraph is itself larger than max_chars, split by sentences
        if len(text) > max_chars:
            sentences = split_sentences(text)
            sub_accum = []
            sub_len = 0
            for sent in sentences:
                if sub_len + len(sent) > target_chars and sub_accum:
                    sub_content = " ".join(sub_accum)
                    breadcrumb = f"[Book: {book_slug} | Section: {active_section} | Page: {page_number}]"
                    search_text = f"{breadcrumb}\n{sub_content}"
                    chunks.append({
                        "content_type": "text",
                        "content": sub_content,
                        "search_text": search_text,
                        "section": active_section,
                        "page_number": page_number,
                        "region_id": reg_id,
                        "metadata": {
                            "region_ids": [reg_id] if reg_id else [],
                            "char_count": len(sub_content)
                        }
                    })
                    # Keep last sentence for overlap if available
                    sub_accum = [sub_accum[-1]] if len(sub_accum) > 1 else []
                    sub_len = sum(len(s) for s in sub_accum)

                sub_accum.append(sent)
                sub_len += len(sent) + 1

            if sub_accum:
                accumulated_texts.extend(sub_accum)
                if reg_id:
                    accumulated_region_ids.append(reg_id)
                accumulated_len += sub_len
        else:
            accumulated_texts.append(text)
            if reg_id:
                accumulated_region_ids.append(reg_id)
            accumulated_len += len(text)

    # Flush any remaining text on the page
    if accumulated_texts:
        combined_content = "\n\n".join(accumulated_texts)
        breadcrumb = f"[Book: {book_slug} | Section: {active_section} | Page: {page_number}]"
        search_text = f"{breadcrumb}\n{combined_content}"
        chunks.append({
            "content_type": "text",
            "content": combined_content,
            "search_text": search_text,
            "section": active_section,
            "page_number": page_number,
            "region_id": accumulated_region_ids[0] if accumulated_region_ids else None,
            "metadata": {
                "region_ids": list(accumulated_region_ids),
                "char_count": len(combined_content)
            }
        })

    return chunks
