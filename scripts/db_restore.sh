#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
    echo "Usage: scripts/db_restore.sh path/to/backup.sql"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] File $BACKUP_FILE does not exist."
    exit 1
fi

echo "Restoring database from $BACKUP_FILE..."
docker exec -i rag_postgres_dev psql -U postgres rag_dev < "$BACKUP_FILE"
echo "[SUCCESS] Database restored successfully from $BACKUP_FILE."
