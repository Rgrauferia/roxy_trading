#!/bin/sh
set -eu

mode="${ROXY_SERVICE_MODE:-}"
service="${RENDER_SERVICE_NAME:-}"
python_bin="${PYTHON_BIN:-python}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python3"
fi

if [ "$mode" = "stock-stream" ] || [ "${ROXY_RUN_STOCK_BRIDGE:-0}" = "1" ] || [ "$service" = "roxy-stock-stream" ]; then
  echo "Starting Roxy stock stream bridge on port ${PORT:-8765}"
  exec "$python_bin" -m uvicorn tools.roxy_stock_stream_bridge:app --host 0.0.0.0 --port "${PORT:-8765}"
fi

echo "Starting Roxy Streamlit app on port ${PORT:-3000}"
exec streamlit run streamlit_app.py \
  --server.port "${PORT:-3000}" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false \
  --server.fileWatcherType none
