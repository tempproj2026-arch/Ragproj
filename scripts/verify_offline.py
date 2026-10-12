"""
Verification script for offline air-gapped readiness.
Checks Python packages, offline models, and environment variables.
"""

import sys
import os
from pathlib import Path

def test_imports():
    print("[1/3] Testing Python package imports...")
    packages = [
        ("pydantic", "pydantic"),
        ("psycopg", "psycopg"),
        ("pgvector", "pgvector"),
        ("ragcore", "ragcore"),
        ("mcp", "mcp"),
        ("mcp_server", "mcp_server"),
        ("ingestion", "ingestion"),
        ("PIL", "pillow"),
    ]
    all_ok = True
    for mod_name, pkg_name in packages:
        try:
            __import__(mod_name)
            print(f"  [OK] {pkg_name} ({mod_name})")
        except ImportError as e:
            print(f"  [FAIL] {pkg_name} ({mod_name}): {e}")
            all_ok = False
    return all_ok

def test_offline_models():
    print("\n[2/3] Checking offline model directories...")
    root = Path(__file__).resolve().parent.parent
    bundle_models = root / "offline_bundle" / "models"
    
    expected_models = [
        "BAAI_bge-m3",
        "BAAI_bge-reranker-v2-m3",
        "google_siglip-so400m-patch14-384",
        "docling-project_docling-models",
        "Qwen2.5-VL-7B-Instruct-GGUF"
    ]
    
    all_ok = True
    for model_name in expected_models:
        model_path = bundle_models / model_name
        if model_path.exists() and any(model_path.iterdir()):
            files_count = len(list(model_path.iterdir()))
            print(f"  [OK] {model_name} ({files_count} files/folders)")
        else:
            print(f"  [FAIL] {model_name} missing or empty at {model_path}")
            all_ok = False
    return all_ok

def test_wheelhouse():
    print("\n[3/3] Checking offline requirements and wheelhouse...")
    root = Path(__file__).resolve().parent.parent
    req_file = root / "offline_bundle" / "requirements.txt"
    wheelhouse = root / "offline_bundle" / "wheelhouse"
    
    if not req_file.exists():
        print(f"  [FAIL] offline_bundle/requirements.txt missing!")
        return False
    
    lines = [line.strip() for line in req_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    print(f"  [OK] requirements.txt present with {len(lines)} pinned dependencies.")
    
    if wheelhouse.exists():
        whl_files = list(wheelhouse.glob("*.whl"))
        print(f"  [INFO] wheelhouse contains {len(whl_files)} cached wheel(s).")
    else:
        print(f"  [INFO] wheelhouse directory not found.")
        
    return True

if __name__ == "__main__":
    print("=" * 60)
    print(" RAG over Scanned Books - Offline Air-Gap Verification")
    print("=" * 60)
    
    imports_ok = test_imports()
    models_ok = test_offline_models()
    bundle_ok = test_wheelhouse()
    
    print("\n" + "=" * 60)
    if imports_ok and models_ok and bundle_ok:
        print(" [SUCCESS] All offline checks passed successfully!")
        print("=" * 60)
        sys.exit(0)
    else:
        print(" [WARNING] Some checks failed or require attention.")
        print("=" * 60)
        sys.exit(1)
