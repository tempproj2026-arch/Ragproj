@echo off
setlocal

if "%~1"=="" (
    echo Usage: scripts\db_restore.bat path\to\backup.sql
    exit /b 1
)

set BACKUP_FILE=%~1

if not exist "%BACKUP_FILE%" (
    echo [ERROR] File %BACKUP_FILE% does not exist.
    exit /b 1
)

echo Restoring database from %BACKUP_FILE%...
docker exec -i rag_postgres_dev psql -U postgres rag_dev < "%BACKUP_FILE%"
if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] Database restored successfully from %BACKUP_FILE%.
) else (
    echo [ERROR] Database restore failed.
    exit /b 1
)
