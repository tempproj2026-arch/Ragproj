#!/usr/bin/env bash
set -e

echo "========================================================"
echo " Verifying Offline Air-Gap Readiness (Linux)           "
echo "========================================================"

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

python3 scripts/verify_offline.py
