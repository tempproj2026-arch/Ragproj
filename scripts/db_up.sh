#!/usr/bin/env bash
set -e

echo "========================================================"
echo " Starting PostgreSQL + pgvector container               "
echo "========================================================"

docker compose -f docker/compose.yaml up -d
echo "[SUCCESS] PostgreSQL + pgvector container started."
docker ps -f name=rag_postgres
