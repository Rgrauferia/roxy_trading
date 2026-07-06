#!/bin/sh
set -eu

python_bin="${PYTHON_BIN:-python}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python3"
fi

echo "Starting Roxy stock stream bridge on port ${PORT:-10000}"
exec "$python_bin" -u -m tools.roxy_stock_stream_bridge
