#!/bin/sh
set -eu

python_bin="${PYTHON_BIN:-python}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python3"
fi

echo "Starting Roxy stock stream bridge on port ${PORT:-8765}"
exec "$python_bin" -m uvicorn tools.roxy_stock_stream_bridge:app --host 0.0.0.0 --port "${PORT:-8765}"
