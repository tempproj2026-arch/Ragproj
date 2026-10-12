#!/usr/bin/env bash
set -e

echo "========================================================"
echo " RAG over Scanned Books - Offline Installation (Linux)  "
echo "========================================================"

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found in PATH."
    exit 1
fi

echo "[1/4] Creating virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "[2/4] Upgrading pip from offline wheelhouse..."
pip install --no-index --find-links=offline_bundle/wheelhouse pip setuptools wheel --upgrade 2>/dev/null || true

echo "[3/4] Installing third-party dependencies from offline wheelhouse..."
pip install --no-index --find-links=offline_bundle/wheelhouse -r offline_bundle/requirements.txt

echo "[4/4] Installing local workspace packages in editable mode..."
pip install --no-index --no-deps -e packages/core
pip install --no-index --no-deps -e packages/ingestion
pip install --no-index --no-deps -e packages/mcp_server

echo "========================================================"
echo "[SUCCESS] Offline installation completed successfully!"
echo "To activate: source .venv/bin/activate"
echo "========================================================"
