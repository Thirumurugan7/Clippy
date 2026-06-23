#!/usr/bin/env bash
# Start the ClipForge worker (separate process; one job at a time).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec ./.venv/bin/python -u -m worker.worker
