@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo  RAG over Scanned Books - Offline Installation (Windows)
echo ========================================================

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo Please install Python 3.11 or add it to PATH.
    exit /b 1
)

echo [1/4] Creating virtual environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [2/4] Upgrading pip from offline wheelhouse...
python -m pip install --no-index --find-links=offline_bundle/wheelhouse pip setuptools wheel --upgrade 2>nul

echo [3/4] Installing third-party dependencies from offline wheelhouse...
python -m pip install --no-index --find-links=offline_bundle/wheelhouse -r offline_bundle/requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install offline requirements from wheelhouse.
    exit /b 1
)

echo [4/4] Installing local workspace packages in editable mode...
python -m pip install --no-index --no-deps -e packages\core
python -m pip install --no-index --no-deps -e packages\ingestion
python -m pip install --no-index --no-deps -e packages\mcp_server

echo ========================================================
echo [SUCCESS] Offline installation completed successfully!
echo To activate: .venv\Scripts\activate.bat
echo ========================================================
