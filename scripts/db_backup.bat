@echo off
setlocal

set BACKUP_DIR=data\backups
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
set TIMESTAMP=%dt:~0,8%_%dt:~8,6%
set OUTFILE=%BACKUP_DIR%\db_backup_%TIMESTAMP%.sql

echo Backing up database to %OUTFILE%...
docker exec -t rag_postgres_dev pg_dump -U postgres rag_dev > "%OUTFILE%"
if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] Backup created at %OUTFILE%
) else (
    echo [ERROR] Backup failed.
    exit /b 1
)
