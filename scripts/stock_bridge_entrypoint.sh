#!/bin/sh
set -eu

python_bin="${PYTHON_BIN:-python}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python3"
fi

app_dir="${APP_DIR:-/app}"
if [ ! -f "${app_dir}/tools/roxy_stock_stream_bridge.py" ]; then
  app_dir="$(pwd)"
fi

export PYTHONPATH="${PYTHONPATH:-${app_dir}}"
port="${PORT:-10000}"
echo "Starting Roxy stock stream bridge via uvicorn on port ${port}"
echo "Python: $($python_bin --version 2>&1)"
echo "PYTHONPATH: ${PYTHONPATH}"
test -f "${app_dir}/tools/roxy_stock_stream_bridge.py"
exec "$python_bin" -m uvicorn tools.roxy_stock_stream_bridge:app --host 0.0.0.0 --port "$port" --log-level info
