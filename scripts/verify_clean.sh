#!/usr/bin/env bash
set -e

echo "========================================================"
echo " Verifying Clean Environment (Phase 6 Exit Criteria)    "
echo "========================================================"

CLEAN=0

echo "[1/3] Checking data/dev absence..."
if [ -d "data/dev" ]; then
    echo "  [FAIL] data/dev still exists!"
    CLEAN=1
else
    echo "  [OK] data/dev does not exist."
fi

echo "[2/3] Checking for leaked development PDFs or page images in data/..."
LEAKED=$(find data -type f \( -name "*.pdf" -o -name "*.png" \) 2>/dev/null || true)
if [ -n "$LEAKED" ]; then
    echo "  [FAIL] Leaked files found:"
    echo "$LEAKED"
    CLEAN=1
else
    echo "  [OK] No leaked PDFs or image crops found in data/."
fi

echo "[3/3] Checking database backups..."
if [ -d "data/backups" ]; then
    echo "  [FAIL] data/backups still exists!"
    CLEAN=1
else
    echo "  [OK] data/backups does not exist."
fi

echo "========================================================"
if [ $CLEAN -eq 0 ]; then
    echo "[SUCCESS] Environment is completely clean of development data!"
    exit 0
else
    echo "[WARNING] Development artifacts are still present. Please run scripts/purge_dev_data.sh."
    exit 1
fi
