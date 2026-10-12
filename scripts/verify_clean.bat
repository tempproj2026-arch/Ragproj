@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo  Verifying Clean Environment (Phase 6 Exit Criteria)
echo ========================================================

set CLEAN=1

echo [1/3] Checking data\dev absence...
if exist "data\dev" (
    echo   [FAIL] data\dev still exists!
    set CLEAN=0
) else (
    echo   [OK] data\dev does not exist.
)

echo [2/3] Checking for leaked development PDFs or page images in data\...
for /r data %%f in (*.pdf *.png) do (
    echo   [FAIL] Leaked file found: %%f
    set CLEAN=0
)
if !CLEAN! equ 1 (
    echo   [OK] No leaked PDFs or image crops found in data\.
)

echo [3/3] Checking database backups...
if exist "data\backups" (
    echo   [FAIL] data\backups still exists!
    set CLEAN=0
) else (
    echo   [OK] data\backups does not exist.
)

echo ========================================================
if !CLEAN! equ 1 (
    echo [SUCCESS] Environment is completely clean of development data!
    exit /b 0
) else (
    echo [WARNING] Development artifacts are still present. Please run scripts\purge_dev_data.bat.
    exit /b 1
)
