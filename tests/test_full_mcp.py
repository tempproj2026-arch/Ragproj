import sys
from mcp_server.tools import list_books, get_page, search_text, search_figures

def run_tests():
    print("==================================================")
    print("        RAG TECHNICAL BOOKS MCP SERVER TEST       ")
    print("==================================================\n")

    print("1. [MCP Tool: list_books]")
    print(list_books())
    print("\n" + "-"*50 + "\n")

    print("2. [MCP Tool: get_page (Book 1, Page 1)]")
    page_text = get_page("chapter_1_2_3_scanned", 1)
    print(page_text[:400] + "...\n")
    print("-" * 50 + "\n")

    print("3. [MCP Tool: search_text ('carburetor needle valve operation')]")
    try:
        search_res = search_text("carburetor needle valve operation", top_k=2)
        print(search_res)
    except Exception as e:
        print(f"Error calling search_text: {e}")
        print("Note: If Colab tunnel is down, restart the Colab cells and update .env")
    print("\n" + "-" * 50 + "\n")

    print("4. [MCP Tool: search_figures ('carburetor diagram')]")
    try:
        fig_res = search_figures("carburetor diagram", top_k=2)
        print(fig_res)
    except Exception as e:
        print(f"Error calling search_figures: {e}")
    print("\n==================================================")
    print("              MCP TEST COMPLETE                   ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
