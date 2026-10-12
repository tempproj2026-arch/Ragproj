@echo off
setlocal

echo ========================================================
echo  [CAUTION] Purging Development Data (Phase 6)
echo ========================================================

set /p CONFIRM="Are you sure you want to completely PURGE all development data? (type 'yes' to proceed): "
if not "%CONFIRM%"=="yes" (
    echo [ABORTED] Purge canceled by user.
    exit /b 0
)

echo [1/5] Stopping and wiping development Docker volume...
docker compose -f docker\compose.yaml down -v 2>nul

echo [2/5] Purging data\dev directory...
if exist "data\dev" rmdir /s /q "data\dev"

echo [3/5] Purging development backups...
if exist "data\backups" rmdir /s /q "data\backups"

echo [4/5] Removing temporary logs and cache folders...
del /q /f *.log 2>nul
del /q /f data\*.log 2>nul
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo [5/5] Resetting empty data directories for production...
if not exist "data\prod" mkdir "data\prod"
if not exist "data\prod\input" mkdir "data\prod\input"
if not exist "data\prod\books" mkdir "data\prod\books"

echo ========================================================
echo [SUCCESS] Development data purge complete!
echo Run scripts\verify_clean.bat to verify clean environment.
echo ========================================================
