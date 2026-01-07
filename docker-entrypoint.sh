#!/usr/bin/env bash
set -euo pipefail

# Simple Docker entrypoint to run the APScheduler-based scanner by default.
# If you want the Streamlit app, override the command in docker-compose.

export PYTHONUNBUFFERED=1

if [ "$1" = "scanner" ]; then
  exec python tools/aps_scanner_service.py
else
  exec "$@"
fi
