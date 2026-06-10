## Roxy Trading — Copilot Agent Guide

Purpose: Give AI coding agents the minimum project-specific context to be productive here.

### Big Picture
- Scanner pipeline: [app.py](app.py) orchestrates scans via [roxy_scanner.py](roxy_scanner.py), exports CSVs to output/ and alerts to alerts/, and can persist to SQLite with [storage.py](storage.py).
- Scheduler: [scanner_service.py](scanner_service.py) loops `app.main()` on `SCAN_INTERVAL_MIN`.
- UI: [streamlit_app.py](streamlit_app.py) reads output/, alerts/, and db/roxy.db to render rankings, charts, and admin tools.
- Backtests: [backtester.py](backtester.py) replays OHLCV using `score_setup()`; writes `backtests` and `equity_points` in db/roxy.db.
- Adapters: Paper trading in [adapters/paper_trader.py](adapters/paper_trader.py); base interfaces in [adapters/broker.py](adapters/broker.py).

### Data Contracts
- Scanner row: `symbol, tf|interval, score, entry, stop, tp1, tp2, rr_tp1, rr_tp2, signal, rank_score`.
- Ranking fallback: If `rank_trades()` is absent, [app.py](app.py) computes `rank_score = W_SCORE*score + W_RRTP2*clip(rr_tp2) + signal_bonus`.
- Alerts/exports:
  - [alerts/top_picks.txt](alerts/top_picks.txt): e.g. `CRYPTO BTC/USD [1h] BUY | Rank 72.3 | RR2 1.8 | Entry 42000.00`.
  - [alerts/latest_summary.json](alerts/latest_summary.json): `{timestamp, top_picks[], alerts[]}`.
  - CSV prefixes in output/: `crypto_tech_*`, `stocks_tech_*`, `stocks_growth_*`.

### Workflows
- Setup: create venv and install deps (see [README.md](README.md)).
- One-off scan: `python app.py` • Scheduled: `python scanner_service.py`.
- UI: `make run-streamlit` (or `streamlit run streamlit_app.py`).
- Backtest: `python backtester.py path/to/ohlcv.csv --name mytest --buy-score 55`.
- Snapshot service (equity points): `docker-compose up -d snapshot` or `python tools/account_snapshot_service.py --interval 5` (see [deployment/snapshot.service](deployment/snapshot.service) and [deployment/snapshot.plist](deployment/snapshot.plist)).
- Make targets: `make test` (pytest -q), `make migrate-db` (runs [tools/db_migration.py](tools/db_migration.py)), `make run-server` (dev voice API in tools.voice_service).

### Config & Integrations
- Config defaults via `getattr` in [app.py](app.py); optional overrides in [config.py](config.py).
- Env toggles: `SCAN_INTERVAL_MIN`, `SNAP_INTERVAL_MIN`, `TG_TOKEN`, `TG_CHAT_ID`, `SLACK_WEBHOOK_URL`, `WEBHOOK_URL`, optional `GROK_API_KEY`, admin `ADMIN_TOKEN`.
- Logging/notify: use [logging_config.py](logging_config.py) for logging; send outbound notifications through [notifier.py](notifier.py) (Telegram/Slack/webhook), not ad‑hoc HTTP.

### Conventions & Patterns
- YFinance gotcha: [roxy_scanner.fetch_stock_ohlcv](roxy_scanner.py) flattens MultiIndex columns—don’t reintroduce MultiIndex.
- DB location: default `db/roxy.db` supports UI and CLI; avoid changing path unless propagating everywhere.
- Large Streamlit file: add new panels behind expanders in [streamlit_app.py](streamlit_app.py) to keep the UI responsive.
- Alerts are content-change gated; append-only behavior is expected for CSVs in output/.

### Extension Points
- New scanners: add `scan_<market>()` in [roxy_scanner.py](roxy_scanner.py) returning the standard columns; wire exports in [app.py](app.py).
- Ranking/filter: implement `rank_trades(df)` or `filter_rr(df)` in [roxy_scanner.py](roxy_scanner.py) to override defaults.
- Execution: extend [adapters/broker.py](adapters/broker.py) or [adapters/paper_trader.py](adapters/paper_trader.py); persist via [storage.py](storage.py) for UI visibility.
- AI signals: see [docs/ai_spec.md](docs/ai_spec.md) for formats/constraints; prompts in [tools/ai_prompts.py](tools/ai_prompts.py); provider hook in [grok_integration.py](grok_integration.py) gated by [grok_control.py](grok_control.py).

If unsure about a change, prefer small, focused edits that respect these contracts so the UI, alerts, and backtests continue to work without additional wiring.