@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo  Building Offline Bundle Wheelhouse (Windows)
echo ========================================================

echo [1/3] Exporting pinned requirements from uv...
uv export --all-packages --no-hashes --no-emit-workspace -o offline_bundle\requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uv export failed.
    exit /b 1
)

echo [2/3] Downloading all wheels into offline_bundle\wheelhouse...
pip download --dest offline_bundle\wheelhouse -r offline_bundle\requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] pip download failed.
    exit /b 1
)

echo [3/3] Generating SHA256 checksum manifest...
powershell -Command "Get-ChildItem -Recurse offline_bundle | Where-Object { -not $_.PSIsContainer -and $_.Name -ne 'MANIFEST.sha256' } | Get-FileHash -Algorithm SHA256 | ForEach-Object { '{0}  {1}' -f $_.Hash, (Resolve-Path -Relative $_.Path) } | Out-File -Encoding utf8 offline_bundle\MANIFEST.sha256"

echo ========================================================
echo [SUCCESS] Offline bundle built in offline_bundle/
echo ========================================================
