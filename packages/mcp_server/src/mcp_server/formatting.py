from pathlib import Path
from typing import List, Dict, Any, Optional

from ragcore.config import settings
from ragcore.retriever import SearchResult, FigureResult

def format_search_results(results: List[SearchResult]) -> str:
    """Formats hybrid search results into clean markdown for LLM context."""
    if not results:
        return "No relevant sections found matching the query."

    lines = [f"Found {len(results)} relevant sections:\n"]
    for r in results:
        header = f"### [Rank {r.rank}] Book: `{r.document_slug}` | Page: {r.page_number} | Type: `{r.content_type}` (Score: {r.score})"
        if r.section:
            header += f"\n**Section:** {r.section}"

        lines.append(header)
        lines.append("")

        content = r.content
        if r.figure_image_path:
            abs_p = (Path(settings.data_root) / r.figure_image_path).resolve()
            abs_url = f"file:///{abs_p.as_posix()}"
            content = content.replace(r.figure_image_path, abs_url)
            lines.append(content)
            lines.append(f"\n*(Embed diagram in answer: `![{r.section or 'Diagram'}]({abs_url})`)*")
        else:
            lines.append(content)

        lines.append("\n---\n")

    return "\n".join(lines)

def format_figure_results(results: List[FigureResult]) -> str:
    """Formats figure retrieval results into clean markdown with embeddable image URLs."""
    if not results:
        return "No relevant technical figures found matching the query."

    lines = [f"Found {len(results)} matching technical diagrams:\n"]
    for idx, f in enumerate(results, start=1):
        abs_p = (Path(settings.data_root) / f.image_path).resolve()
        abs_url = f"file:///{abs_p.as_posix()}"
        caption = f.caption or f"Figure {idx}"

        lines.append(f"### [Figure {idx}] Book: `{f.document_slug}` | Page: {f.page_number} (Similarity: {f.score})")
        lines.append(f"\n![{caption}]({abs_url})\n")
        lines.append(f"**Caption:** {caption}")
        lines.append(f"**Image File:** `{abs_p}`")
        if f.description:
            lines.append(f"**Detailed Breakdown:**\n{f.description}")
        lines.append(f"\n*(Tip: Display this diagram directly to the user with: `![{caption}]({abs_url})`)*")
        lines.append("\n---\n")

    return "\n".join(lines)

