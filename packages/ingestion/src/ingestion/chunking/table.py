import re
from typing import List, Dict, Any, Optional

def clean_markdown_table_text(text: str) -> str:
    """Extracts raw markdown table content from VLM code block wrappers if present."""
    if not text:
        return ""
    # Strip ```markdown and ``` wrappers
    text = re.sub(r'^```(?:markdown)?\s*', '', text.strip(), flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text.strip())
    return text.strip()

def parse_markdown_table_lines(table_text: str):
    """
    Parses a markdown table into (title_or_caption, headers, separator, data_rows).
    """
    lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    caption_lines = []
    table_lines = []

    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            table_lines.append(line)
        else:
            caption_lines.append(line)

    caption = " ".join(caption_lines).strip()
    if len(table_lines) < 2:
        return caption, "", "", table_lines

    headers = table_lines[0]
    separator = table_lines[1]
    data_rows = table_lines[2:]
    return caption, headers, separator, data_rows

def verbalize_table_rows(headers: str, data_rows: List[str]) -> str:
    """
    Converts markdown table rows into plain text key-value pairs for BM25/trigram search indexing.
    Example: 'Product: Petroleum ether, Baume: 95, Specific Gravity: .6222, Pounds/Gal: 5.18'
    """
    if not headers or not data_rows:
        return ""

    header_cols = [c.strip() for c in headers.strip("|").split("|")]
    verbalized_items = []

    for row in data_rows:
        row_cols = [c.strip() for c in row.strip("|").split("|")]
        pairs = []
        for i, val in enumerate(row_cols):
            if val and val not in ["-", "—"]:
                h_name = header_cols[i] if i < len(header_cols) and header_cols[i] else f"Col{i+1}"
                pairs.append(f"{h_name}: {val}")
        if pairs:
            verbalized_items.append(", ".join(pairs))

    return "\n".join(verbalized_items)

def chunk_table_region(
    region: Dict[str, Any],
    book_slug: str,
    page_number: int,
    current_section: Optional[str] = None,
    max_rows_per_chunk: int = 10
) -> List[Dict[str, Any]]:
    """
    Chunks a table region. Preserves headers on all row slices and builds verbalized search text.
    """
    raw_text = region.get("extracted_text", "")
    table_text = clean_markdown_table_text(raw_text)
    reg_id = region.get("id")

    if not table_text:
        return []

    caption, headers, separator, data_rows = parse_markdown_table_lines(table_text)
    table_title = caption or current_section or "Data Table"
    breadcrumb = f"[Book: {book_slug} | Table: {table_title} | Page: {page_number}]"

    # If it's a small table or parsing failed to find structured rows, keep as single chunk
    if len(data_rows) <= max_rows_per_chunk or not headers:
        content = table_text
        verbalized = verbalize_table_rows(headers, data_rows) if headers else ""
        search_parts = [breadcrumb, content]
        if verbalized:
            search_parts.append(f"Row Data:\n{verbalized}")
        search_text = "\n\n".join(search_parts)

        return [{
            "content_type": "table",
            "content": content,
            "search_text": search_text,
            "section": table_title,
            "page_number": page_number,
            "region_id": reg_id,
            "metadata": {
                "region_id": reg_id,
                "row_count": len(data_rows),
                "is_split": False
            }
        }]

    # For large multi-row tables, chunk by groups of rows, repeating headers in every sub-chunk
    chunks = []
    total_rows = len(data_rows)
    for start_idx in range(0, total_rows, max_rows_per_chunk):
        row_slice = data_rows[start_idx:start_idx + max_rows_per_chunk]
        slice_table_lines = [headers, separator] + row_slice
        slice_markdown = "\n".join(slice_table_lines)
        if caption:
            slice_markdown = f"**{caption} (Rows {start_idx+1} to {start_idx+len(row_slice)} of {total_rows})**\n\n{slice_markdown}"

        verbalized = verbalize_table_rows(headers, row_slice)
        search_parts = [
            breadcrumb,
            slice_markdown
        ]
        if verbalized:
            search_parts.append(f"Row Data:\n{verbalized}")
        search_text = "\n\n".join(search_parts)

        chunks.append({
            "content_type": "table",
            "content": slice_markdown,
            "search_text": search_text,
            "section": table_title,
            "page_number": page_number,
            "region_id": reg_id,
            "metadata": {
                "region_id": reg_id,
                "row_start": start_idx + 1,
                "row_end": start_idx + len(row_slice),
                "total_rows": total_rows,
                "is_split": True
            }
        })

    return chunks
