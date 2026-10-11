import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from ragcore.config import settings
from ragcore.logging import get_logger
from ragcore.db.connection import Database
from ragcore.retriever import retriever
from .formatting import format_search_results, format_figure_results
from .images import resolve_image_path

logger = get_logger("mcp_server.tools")

def search_text(
    query: str,
    top_k: int = 5,
    book_slug: Optional[str] = None,
    content_type: Optional[str] = None
) -> str:
    """
    Primary search tool. Use this tool FIRST to answer any technical question, explain how components work, find data in tables, formulas, definitions, or procedures.
    
    Args:
        query: Technical search query or question (e.g. 'carburetor needle valve operation', 'distillation temperature curve', 'Prony brake formula').
        top_k: Number of relevant sections to return (default 5, max 20).
        book_slug: Optional book filter ('chapter_1_2_3_scanned' or 'chapter_4_5_scanned').
        content_type: Optional filter by content type ('text', 'table', 'figure', 'formula').
    """
    types = [content_type] if content_type else None
    top_k = min(max(1, top_k), 20)
    
    results = retriever.search_hybrid(
        query=query,
        top_k=top_k,
        content_types=types
    )
    
    # Filter by book_slug if specified
    if book_slug:
        results = [r for r in results if r.document_slug == book_slug]

    return format_search_results(results)

def get_page(book_slug: str, page_number: int) -> str:
    """
    Retrieves the complete transcription and visual element breakdown of a specific page.
    
    Args:
        book_slug: Identifier of the book (e.g. 'chapter_1_2_3_scanned' or 'chapter_4_5_scanned').
        page_number: 1-indexed page number (e.g. 1 to 25).
    """
    page_folder = Path(settings.data_root) / "books" / book_slug / "pages" / f"p{page_number:04d}"
    page_md_path = page_folder / "page.md"

    if not page_md_path.exists():
        return f"Error: Page {page_number} for book '{book_slug}' not found."

    with open(page_md_path, "r", encoding="utf-8") as f:
        page_content = f.read()

    # Query database for visual regions on this page
    elements_summary = []
    with Database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.kind, r.reading_order, r.image_path, c.content_type, c.section
                FROM regions r
                JOIN pages p ON r.page_id = p.id
                JOIN documents d ON p.document_id = d.id
                LEFT JOIN chunks c ON c.region_id = r.id
                WHERE d.slug = %s AND p.page_number = %s
                ORDER BY r.reading_order;
            """, (book_slug, page_number))
            rows = cur.fetchall()
            for r in rows:
                kind, order, img, ctype, section = r
                item = f"- **Order {order} [{kind.upper()}]**"
                if section:
                    item += f" Section: *{section}*"
                if img:
                    item += f" | Crop: `{img}`"
                elements_summary.append(item)

    summary_text = "\n".join(elements_summary) if elements_summary else "No structured sub-regions recorded."

    return f"""# Book: `{book_slug}` | Page: {page_number}

## Full Page Content
{page_content}

---
## Detected Visual Elements & Layout Structure
{summary_text}
"""

def search_figures(query: str, top_k: int = 3) -> str:
    """
    Visual diagram search tool. Use ONLY when the user explicitly asks to SEE, view, or find a technical diagram, schematic drawing, or visual illustration.
    
    Args:
        query: Description or name of the visual diagram (e.g. 'carburetor diagram', 'distillation chart', 'flywheel schematic').
        top_k: Number of figures to return (default 3, max 10).
    """
    top_k = min(max(1, top_k), 10)
    results = retriever.search_figures(query=query, top_k=top_k)
    return format_figure_results(results)

def list_books() -> str:
    """
    Lists all indexed technical books, page counts, chunk counts, and table/figure statistics.
    """
    with Database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    d.id, d.slug, d.title, d.page_count,
                    COUNT(DISTINCT c.id) AS chunk_count,
                    COUNT(DISTINCT f.id) AS figure_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                LEFT JOIN pages p ON p.document_id = d.id
                LEFT JOIN regions r ON r.page_id = p.id
                LEFT JOIN figures f ON f.region_id = r.id
                GROUP BY d.id, d.slug, d.title, d.page_count
                ORDER BY d.id;
            """)
            rows = cur.fetchall()

    if not rows:
        return "No documents currently indexed in the database."

    lines = ["# Indexed Technical Books Catalog\n"]
    lines.append("| ID | Book Slug | Title | Pages | Chunks | Figures |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        doc_id, slug, title, pages, chunks, figures = r
        lines.append(f"| {doc_id} | `{slug}` | {title or 'N/A'} | {pages} | {chunks} | {figures} |")

    return "\n".join(lines)
