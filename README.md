Roxy Trading Scanner

[![CI](https://github.com/Rgrauferia/roxy_trading/actions/workflows/ci.yml/badge.svg)](https://github.com/Rgrauferia/roxy_trading/actions/workflows/ci.yml)
![Streamlit smoke](https://github.com/Rgrauferia/roxy_trading/actions/workflows/smoke.yml/badge.svg)

Quick start

1. Create and activate a virtual environment (macOS):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the scanner:

```bash
python app.py
```

What I changed

- Added `requirements.txt` listing runtime and test deps.
- Added this `README.md` with quick setup and run steps.

Next recommended improvements

- Standardize logging using the `logging` module.
- Add basic unit tests for key functions in `roxy_scanner.py`.
- Add a simple GitHub Actions workflow for CI.
- Add type hints and small refactors to improve clarity.

If you want, I can start by standardizing logging across `app.py` and `roxy_scanner.py`.

CI

![CI](https://github.com/<YOUR-USER>/<YOUR-REPO>/actions/workflows/ci.yml/badge.svg)

Backtester
---------

Run a replay backtest on an OHLCV CSV:

```bash
source .venv/bin/activate
python backtester.py path/to/ohlcv.csv --name mytest --buy-score 55
```

Run multiple recent CSVs and aggregate results:

```bash
python tools/batch_backtest.py --limit 5 --buy-score 55
```

Saved backtest metadata is stored in `db/roxy.db` in the `backtests` table.

Moving average strategy
-----------------------

The project now includes a focused SMA 20/40/100/200 scanner for stocks and crypto:

```bash
.venv/bin/python tools/ma_scan.py --market stocks --symbols AAPL,MSFT,NVDA,TSLA --limit 20
.venv/bin/python tools/ma_scan.py --market crypto --symbols BTC/USD,ETH/USD,SOL/USD --crypto-timeframe 1d
.venv/bin/python tools/ma_backtest.py --market stocks --stock-period 5y --min-buy-hold-edge-pct 0 --only-eligible --save
.venv/bin/python tools/ma_scan.py --market both --require-backtest-eligible --limit 30 --save
.venv/bin/python tools/ma_report.py
.venv/bin/python tools/ma_daily.py
.venv/bin/python tools/ma_daily_launchd.py install
.venv/bin/python tools/ma_live.py --once
.venv/bin/python tools/ma_confluence.py --save
.venv/bin/python tools/options_scan.py --save
.venv/bin/python tools/ma_live_launchd.py install
```

See `docs/moving_average_strategy.md` for the signal rules, setups and tunable parameters.

The launchd helper installs the SMA daily workflow at 18:05 local time and writes logs to `logs/ma_daily.out` and `logs/ma_daily.err`.
The live helper installs a continuous 15m/1h scanner with extended-hours stock data and writes logs to `logs/ma_live.out` and `logs/ma_live.err`.
The confluence helper specializes the strategy into `1h trend filter + 15m entry trigger`, then checks whether 2%, 5%, or 10% targets justify the stop risk before marking a trade as actionable.
The options helper selects liquid call contracts only after the underlying stock has an actionable confluence trade plan.

Snapshot service
----------------

The project includes an account snapshot service that records per-user equity points (realized + unrealized) into the SQLite DB. Use one of the following methods to run it:

- Docker Compose (recommended in containerized deployments):

```bash
docker-compose up -d snapshot
```

- Run locally (development):

```bash
# run once
python tools/account_snapshot_service.py --once

# run periodically (every 5 minutes)
python tools/account_snapshot_service.py --interval 5
```

- Systemd (example unit file provided at `deployment/snapshot.service`): copy to `/etc/systemd/system/` and enable:

```bash
sudo cp deployment/snapshot.service /etc/systemd/system/roxy_snapshot.service
sudo systemctl daemon-reload
sudo systemctl enable --now roxy_snapshot.service
```

- macOS launchd: an example plist is available at `deployment/snapshot.plist`.

Streamlit control
-----------------

Use one stable development URL for the web app:

```bash
make dev-web
```

Then keep this page open:

```text
http://localhost:3000
```

`make dev-web` reuses the existing server when `http://localhost:3000` is already healthy; otherwise it installs/reloads the existing Streamlit LaunchAgent on that same port with Streamlit hot reload enabled (`server.runOnSave=true`, `server.fileWatcherType=auto`). Do not start ad-hoc Streamlit servers on new ports during normal development; reuse or restart this same service.

Public cloud deploy
-------------------

To use Roxy from any device without keeping this computer on, deploy the app with the included Render Blueprint:

```text
render.yaml
```

Recommended flow:

1. Push this repo to GitHub.
2. In Render, create a new Blueprint from the repo.
3. Add the required secrets when Render asks for them (`ALPACA_API_KEY`, `ALPACA_API_SECRET`, optional `POLYGON_API_KEY`, alert keys, and webhook secret).
4. Open the public Render URL from any phone, tablet, or computer.

The production container keeps Roxy paper/manual by default:

```text
ROXY_ENABLE_LIVE_BROKER_EXECUTION=0
ALPACA_PAPER=true
ROXY_ALPACA_PAPER_AUTOTRADE=false
```

Runtime memory, alerts, output, and DB files are stored on the Render disk mounted at `/var/data`, using `ROXY_OUTPUT_DIR`, `ROXY_ALERTS_DIR`, `ROXY_DATA_DIR`, and `ROXY_DB_DIR`.

Full steps are documented in `docs/deployment_render.md`.

Living market panel
-------------------

The Dashboard includes `Roxy Live Market`, a paper-only live market pulse that refreshes through the same Streamlit page. It uses real provider calls and shows clear diagnostics instead of silently falling back to demo data:

- stocks: fast yfinance market candles for the live pulse; the existing chart router still uses Alpaca/Polygon when configured and falls back visibly,
- crypto: BinanceUS through `ccxt`,
- news: RSS market/news feeds through `feedparser`,
- IPO/new ticker watch: Nasdaq IPO calendar when reachable plus high-impact ticker extraction from news.

Every opportunity row shows ticker, price timestamp, source, reason, indicators, entry, stop, take profit, risk, confidence, related headline when available, and the paper-only disclaimer. If an API fails, the diagnostics panel shows the failing source and last response so the app does not look empty or stale.

The selected asset price refreshes through the dashboard live loop every `5` seconds. Opportunity scans refresh on a seconds cadence, not on the development audit cadence. If the active provider is public or delayed, Roxy shows the source and latency instead of labeling it as guaranteed realtime.

Actionable live alerts
----------------------

`Alertas Live` classifies each opportunity into an actionable state: `Entra ahora`, `Espera pullback`, `No operar`, `Confirmar externo`, or `Vigilar`. Roxy records the last state per market/ticker in `alerts/entry_proximity_state.json` and only sends a notification when a known opportunity transitions into `Entra ahora`, `Espera pullback`, or `No operar`. The first snapshot is recorded but does not notify, which avoids stale/repeated alert noise.

Optional phone-ready channels:

```bash
PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DISCORD_WEBHOOK_URL=...
SLACK_WEBHOOK_URL=...
WEBHOOK_URL=...
```

Generic `WEBHOOK_URL` receives a structured payload with `message`, `source`, and `metadata` so downstream phone automations can route `actionable_alert_transition` events.

Monetization readiness
----------------------

The `Precision` page includes a commercial readiness panel for the App Store / subscription path. It separates what Roxy can safely sell today from what still needs proof:

- beta-ready positioning: live educational scanner, paper trading lab, opportunities dashboard, alerts, and diagnostics,
- blocked positioning: financial adviser, guaranteed profits, personalized investment advice, or live-money automation,
- required proof before stronger signal claims: closed paper outcomes with entry, stop, target, P&L, and hit/stop rates,
- subscription scenarios: sample gross and net monthly revenue after a 15% store commission assumption.

The readiness logic lives in `monetization_readiness.py` and reads the existing paper journals without enabling real orders. Live execution remains OFF behind the broker guardrails.

Paper result closer
-------------------

Roxy also has a paper-only result closer in `paper_result_closer.py`. It reads open, eligible paper tracks from:

- `alerts/alpaca_paper_practice.csv`
- `alerts/crypto_paper_practice.csv`

Then it fetches live prices through the existing market data route and closes only eligible paper tracks as `CLOSED_HIT_2`, `CLOSED_HIT_5`, `CLOSED_HIT_10`, or `CLOSED_STOP`. Rows marked `BLOCKED` are not closed, even if price later touches a target, because they were never valid paper entries. The audit report is written to:

```text
alerts/paper_result_closer.json
```

The `Precision` page runs this closer on a cached 60-second cadence and shows how many stock/crypto symbols were checked. This improves measured accuracy without enabling live broker execution.

Paper entry capture
-------------------

Roxy records paper practice entries only when a setup is actually ready for paper/manual action and the price is inside the entry zone. The dashboard now captures two cases:

- transition capture: a known setup moves from `Cerca de entrada` to `Entrada en zona`,
- snapshot capture: Roxy starts or refreshes while the setup is already in `Entrada en zona`.

Only `READY_FOR_PAPER` candidates are persisted to the paper journals. Blocked candidates still appear in the UI for diagnosis, but they are not saved as paper tracks.

Paper readiness gaps
--------------------

The Dashboard includes `Por que no esta lista para paper`, a monetization-focused diagnostic table. For each top opportunity it shows the main blocker and missing conditions:

- live data source,
- TradingView confirmation,
- BUY/ALERT or paper trigger,
- plan status,
- entry-zone state,
- entry/stop/target/R:R/risk,
- negative memory, backtest, or event guards.

A fresh TradingView BUY can confirm a WATCH setup for paper/manual tracking only when readiness is at least 70 and the rest of the paper gates are already valid: live source, plan ready, price in zone, stop/target present, R:R valid, and real orders OFF.

TradingView webhooks
--------------------

Roxy reads TradingView confirmations from `alerts/tradingview_webhooks.jsonl` without opening a new web URL. The fixed dashboard remains:

```text
http://localhost:3000
```

For local testing or a webhook bridge, ingest one TradingView-style JSON payload with:

```bash
echo '{"symbol":"NASDAQ:AAPL","timeframe":"15","signal":"BUY","price":185.25,"message":"Pullback 20/40"}' | .venv/bin/python tools/tradingview_webhook_ingest.py
```

The dashboard shows `TradingView Webhooks`, `TV Webhook` in the Trade Decision Card, and `TV Webhook` in `Mejores oportunidades ahora`. Fresh BUY webhooks can raise priority; SELL/AVOID webhooks make Roxy wait. This is confirmation only: live money orders remain OFF behind the existing safety gates.

Authenticated TradingView endpoint
----------------------------------

The webhook ingestion logic supports authenticated HTTP receivers. This does not change the Streamlit dashboard URL and is not started by `make dev-web`.

Configure a dedicated secret:

```bash
export TRADINGVIEW_WEBHOOK_SECRET='use-a-long-random-secret'
```

If you run the admin API/bridge, TradingView can POST JSON to:

```text
POST /tradingview/webhook
```

Start or reuse the fixed local bridge:

```bash
make tradingview-bridge
```

It uses `http://127.0.0.1:8001` and exits immediately if that bridge is already healthy. The main Roxy dashboard still stays at `http://localhost:3000`.

If the existing FastAPI voice/service backend is already running, it exposes the same receiver at:

```text
POST /v1/webhooks/tradingview
GET  /v1/webhooks/tradingview/status
```

The HTTP receivers require `TRADINGVIEW_WEBHOOK_SECRET`; if it is missing, they reject POSTs instead of accepting an open webhook.

Auth options:

- preferred header: `X-TradingView-Secret: <secret>`
- TradingView-compatible payload field: `"passphrase": "<secret>"`
- also accepted: `X-Roxy-TradingView-Secret`, `X-Roxy-Webhook-Secret`, `X-Webhook-Secret`, or `secret`/`webhook_secret`/`roxy_secret` in JSON

Example local bridge test:

```bash
curl -X POST http://127.0.0.1:8001/tradingview/webhook \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Secret: $TRADINGVIEW_WEBHOOK_SECRET" \
  -d '{"symbol":"NASDAQ:AAPL","timeframe":"15","signal":"BUY","price":185.25}'
```

Secrets are redacted before payloads are written to `alerts/tradingview_webhooks.jsonl`. This endpoint records analysis confirmations only; it never places orders.

Public TradingView webhook tunnel
---------------------------------

TradingView requires a public HTTPS webhook URL. Keep the dashboard fixed at `http://localhost:3000`, keep the local bridge fixed at `http://127.0.0.1:8001`, and point a tunnel to the bridge only:

```bash
cloudflared tunnel --url http://127.0.0.1:8001
# or
ngrok http 8001
```

Save the final public HTTPS webhook URL in:

```bash
export TRADINGVIEW_PUBLIC_WEBHOOK_URL='https://your-public-url.example/tradingview/webhook'
```

Check readiness without starting a new server:

```bash
make tradingview-tunnel-check
```

The dashboard shows `Tunnel publico`, `URL TradingView`, and `Comando tunnel` inside `TradingView Webhooks`. This is diagnostic only; Roxy still records analysis confirmations and live broker orders remain OFF.

External market integrations
----------------------------

Roxy can also read external market sources through a safe connector layer:

- Finviz Elite screener export: `ROXY_FINVIZ_EXPORT_URL`
- Crypto.com Exchange public market data: `ROXY_CRYPTOCOM_BASE_URL`, optional `ROXY_CRYPTOCOM_API_KEY` and `ROXY_CRYPTOCOM_API_SECRET`
- TradingView chart/webhook layer: `TRADINGVIEW_WEBHOOK_SECRET`, `TRADINGVIEW_PUBLIC_WEBHOOK_URL`, `ROXY_TRADINGVIEW_WIDGET_ENABLED`
- External confirmation scoring: `ROXY_EXTERNAL_CONFIRMATION_ENABLED`, optional `ROXY_EXTERNAL_CONFIRMATION_REMOTE`

These sources enrich scans and confirmations. The decision engine stores the result in `roxy_decision.external_confirmation` and uses it as a bounded priority adjustment. They do not execute live trades. See `docs/external_market_integrations.md` for setup and security notes.

The Streamlit dashboard includes a Snapshot Service section in the sidebar with:
- a button to run a snapshot now (user-level or all users),
- a Docker Compose hint to run the background service,
- local Start/Stop controls (development) that use `tools/process_manager.py` to spawn the background Python process and write a PID file in `run/snapshot.pid`.

Important: the local process manager is intended for development only. For production use `docker-compose`, `systemd`, or launchd as appropriate.

Broker safety and environment
-----------------------------

Use `.env.example` as the local template. Roxy accepts `ALPACA_API_SECRET` and the legacy alias `ALPACA_SECRET_KEY`; both must match the same paper/live mode as `ALPACA_API_KEY`. For paper mode, keep `ALPACA_PAPER=true` and use `https://paper-api.alpaca.markets`. `ALPACA_DATA_FEED=iex` is the default market-data feed; change it only if the Alpaca account has the required permissions. Template values such as `TU_KEY_PAPER` and `TU_SECRET_PAPER` are classified as `PLACEHOLDER_KEYS`; Roxy skips Alpaca probes, keeps signals unsafe, and asks for real paper credentials instead of reporting a generic auth failure.

Robinhood is exposed only as a manual preview route. Even if `ROXY_ENABLE_LIVE_BROKER_EXECUTION=1` and Robinhood placeholders are configured, Roxy keeps Robinhood in `PREVIEW_ONLY` and never enables live broker order placement.

Autopilot
---------

Roxy Autopilot runs health checks, learning review, and paper-only strategy override proposals:

```bash
.venv/bin/python tools/roxy_autopilot.py --json
.venv/bin/python tools/roxy_autopilot_launchd.py install
```

The LaunchAgent runs every 60 seconds and writes `alerts/roxy_autopilot_status.json`. It is installed with `--apply`, but actual code/config writes still require `ROXY_AUTOPILOT_CODE_WRITE=1` in the service environment. Writes are allowlisted to strategy override/proposal files and real-money trading remains disabled.
