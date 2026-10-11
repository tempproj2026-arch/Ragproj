import os
import sys
from pathlib import Path

# Ensure working directory is always the project root
ROOT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path(r"D:\Ragproj")
os.chdir(ROOT_DIR)

# Add package sources to sys.path
sys.path.insert(0, str(ROOT_DIR / "packages" / "core" / "src"))
sys.path.insert(0, str(ROOT_DIR / "packages" / "ingestion" / "src"))
sys.path.insert(0, str(ROOT_DIR / "packages" / "mcp_server" / "src"))

# Launch FastMCP server
from mcp_server.server import main

if __name__ == "__main__":
    main()
