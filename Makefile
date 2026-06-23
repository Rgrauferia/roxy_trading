# Simple deploy hooks
.PHONY: migrate-db run-server run-streamlit dev-web tradingview-bridge tradingview-tunnel-check test

migrate-db:
	python tools/db_migration.py --db db/roxy.db

# convenience
run-server:
	uvicorn tools.voice_service:app --reload --port 8000

run-streamlit:
	streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 3000 --server.headless true --server.runOnSave true --server.fileWatcherType auto --browser.gatherUsageStats false

dev-web:
	.venv/bin/python tools/dev_web.py --port 3000

tradingview-bridge:
	.venv/bin/python tools/tradingview_bridge.py --port 8001

tradingview-tunnel-check:
	.venv/bin/python tools/tradingview_tunnel.py --json

test:
	pytest -q
