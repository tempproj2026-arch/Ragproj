#!/usr/bin/env bash
set -e

echo "========================================================"
echo " Building Offline Bundle Wheelhouse (Linux)             "
echo "========================================================"

echo "[1/3] Exporting pinned requirements from uv..."
uv export --all-packages --no-hashes --no-emit-workspace -o offline_bundle/requirements.txt

echo "[2/3] Downloading all wheels into offline_bundle/wheelhouse..."
pip download --dest offline_bundle/wheelhouse -r offline_bundle/requirements.txt

echo "[3/3] Generating SHA256 checksum manifest..."
find offline_bundle -type f ! -name "MANIFEST.sha256" -exec sha256sum {} + > offline_bundle/MANIFEST.sha256

echo "========================================================"
echo "[SUCCESS] Offline bundle built in offline_bundle/"
echo "========================================================"
