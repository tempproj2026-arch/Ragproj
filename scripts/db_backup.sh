#!/usr/bin/env bash
set -e

BACKUP_DIR="data/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTFILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

echo "Backing up database to $OUTFILE..."
docker exec -t rag_postgres_dev pg_dump -U postgres rag_dev > "$OUTFILE"
echo "[SUCCESS] Backup created at $OUTFILE"
