#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/venv/bin/activate"
elif [[ -f "$ROOT/venv-test/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/venv-test/bin/activate"
fi

exec uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
