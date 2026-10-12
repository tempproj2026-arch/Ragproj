import sys

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from .tools import search_text, get_page, search_figures, list_books

# Initialize FastMCP Server
mcp = FastMCP(
    name="rag-technical-books",
    instructions=(
        "MCP server for querying scanned technical books with complex layouts, "
        "tables, formulas, and technical diagrams indexed in PostgreSQL with pgvector."
    )
)

# Register tools with MCP
mcp.tool()(search_text)
mcp.tool()(get_page)
mcp.tool()(search_figures)
mcp.tool()(list_books)

# Register resources with MCP
@mcp.resource("book://{book_slug}/pages/{page_number}")
def page_resource(book_slug: str, page_number: int) -> str:
    """Full markdown content and visual element layout of a specific page."""
    return get_page(book_slug, int(page_number))

def main():
    """Starts the FastMCP server with STDIO transport for LM Studio / Claude Desktop."""
    transport = "stdio"
    if len(sys.argv) > 1 and sys.argv[1] == "--sse":
        transport = "sse"
    mcp.run(transport=transport)

if __name__ == "__main__":
    main()
