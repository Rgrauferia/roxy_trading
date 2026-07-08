#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export ROXY_DESKTOP_HELPER_URL="${ROXY_DESKTOP_HELPER_URL:-http://127.0.0.1:8765}"

HOST="${ROXY_DESKTOP_HELPER_HOST:-127.0.0.1}"
PORT="${ROXY_DESKTOP_HELPER_PORT:-8765}"

echo "Starting Roxy Desktop Helper on http://${HOST}:${PORT}"
python3 -m roxy_desktop_helper.server --host "$HOST" --port "$PORT"
