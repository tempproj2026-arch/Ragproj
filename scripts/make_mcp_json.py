"""
Generates the LM Studio MCP server configuration block with absolute paths.
Usage:
    python scripts/make_mcp_json.py [--save]
"""

import sys
import json
import argparse
from pathlib import Path

def generate_config():
    root = Path(__file__).resolve().parent.parent
    
    # Detect Python binary
    if sys.platform == "win32":
        venv_python = root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = root / ".venv" / "bin" / "python"
        
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable
    runner_script = str(root / "run_mcp.py")
    
    core_src = str(root / "packages" / "core" / "src")
    ingest_src = str(root / "packages" / "ingestion" / "src")
    mcp_src = str(root / "packages" / "mcp_server" / "src")
    sep = ";" if sys.platform == "win32" else ":"
    pythonpath = sep.join([core_src, ingest_src, mcp_src])
    
    config = {
        "mcpServers": {
            "scanned-books": {
                "command": python_cmd,
                "args": [
                    runner_script
                ],
                "env": {
                    "PYTHONPATH": pythonpath
                }
            }
        }
    }
    return config

def main():
    parser = argparse.ArgumentParser(description="Generate LM Studio MCP configuration")
    parser.add_argument("--save", action="store_true", help="Save directly to mcp_config.json in project root")
    args = parser.parse_args()
    
    cfg = generate_config()
    json_str = json.dumps(cfg, indent=2)
    
    print("\nLM Studio MCP Configuration:")
    print("=" * 60)
    print(json_str)
    print("=" * 60)
    
    if args.save:
        root = Path(__file__).resolve().parent.parent
        out_path = root / "mcp_config.json"
        out_path.write_text(json_str, encoding="utf-8")
        print(f"\nSaved configuration to {out_path}")

if __name__ == "__main__":
    main()
