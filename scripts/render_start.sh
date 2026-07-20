#!/bin/sh
set -eu

mode="${ROXY_SERVICE_MODE:-}"
service="${RENDER_SERVICE_NAME:-}"
python_bin="${PYTHON_BIN:-python}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin="python3"
fi

# Render mounts persistent state at /var/data. Seed packaged reference data
# only when it is absent; never overwrite a user's watchlists, memory or
# operational history during a deploy.
runtime_data_dir="${ROXY_DATA_DIR:-/var/data/data}"
runtime_alerts_dir="${ROXY_ALERTS_DIR:-/var/data/alerts}"
runtime_output_dir="${ROXY_OUTPUT_DIR:-/var/data/output}"
runtime_db_dir="${ROXY_DB_DIR:-/var/data/db}"
mkdir -p "$runtime_data_dir" "$runtime_alerts_dir" "$runtime_output_dir" "$runtime_db_dir"
if [ -d /app/data ]; then
  cp -R -n /app/data/. "$runtime_data_dir/"
fi

if [ "$mode" = "stock-stream" ] || [ "${ROXY_RUN_STOCK_BRIDGE:-0}" = "1" ] || [ "$service" = "roxy-stock-stream" ] || [ "${PORT:-}" = "8765" ]; then
  echo "Starting Roxy stock stream bridge on port ${PORT:-8765}"
  exec "$python_bin" -u -m tools.roxy_stock_stream_bridge
fi

echo "Starting Roxy Streamlit app on port ${PORT:-3000}"
exec streamlit run streamlit_app.py \
  --server.port "${PORT:-3000}" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false \
  --server.fileWatcherType none
