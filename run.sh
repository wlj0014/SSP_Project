#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate

pip install -r requirements.txt

python scripts/run_all_pairs.py "${1:-inputs}"
