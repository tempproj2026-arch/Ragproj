#!/usr/bin/env bash
set -e

echo "========================================================"
echo " [CAUTION] Purging Development Data (Phase 6)           "
echo "========================================================"

read -p "Are you sure you want to completely PURGE all development data? (type 'yes' to proceed): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "[ABORTED] Purge canceled by user."
    exit 0
fi

echo "[1/5] Stopping and wiping development Docker volume..."
docker compose -f docker/compose.yaml down -v || true

echo "[2/5] Purging data/dev directory..."
rm -rf data/dev

echo "[3/5] Purging development backups..."
rm -rf data/backups

echo "[4/5] Removing temporary logs and cache folders..."
rm -f *.log data/*.log
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "[5/5] Resetting empty data directories for production..."
mkdir -p data/prod/input data/prod/books

echo "========================================================"
echo "[SUCCESS] Development data purge complete!"
echo "Run scripts/verify_clean.sh to verify clean environment."
echo "========================================================"
