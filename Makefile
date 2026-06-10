# Simple deploy hooks
.PHONY: migrate-db

migrate-db:
	python tools/db_migration.py --db db/roxy.db

# convenience
run-server:
	uvicorn tools.voice_service:app --reload --port 8000

run-streamlit:
	streamlit run streamlit_app.py

test:
	pytest -q

.PHONY: test
test:
	pytest -q
