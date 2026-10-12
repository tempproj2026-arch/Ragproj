@echo off
setlocal

echo ========================================================
echo  Verifying Offline Air-Gap Readiness (Windows)
echo ========================================================

set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    python scripts\verify_offline.py
) else (
    where uv >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        uv run python scripts\verify_offline.py
    ) else (
        python scripts\verify_offline.py
    )
)

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Verification failed.
    exit /b 1
)

echo [SUCCESS] Verification script finished successfully.
