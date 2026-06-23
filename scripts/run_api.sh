#!/usr/bin/env bash
# Start the ClipForge API (FastAPI on :8000). Run from anywhere.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec ./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
