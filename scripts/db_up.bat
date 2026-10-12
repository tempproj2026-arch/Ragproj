@echo off
setlocal

echo ========================================================
echo  Starting PostgreSQL + pgvector container
echo ========================================================

docker compose -f docker\compose.yaml up -d
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to start Docker container.
    exit /b 1
)

echo [SUCCESS] PostgreSQL + pgvector container started.
docker ps -f name=rag_postgres
