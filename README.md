# Roxy

Roxy is a multi-user market-analysis and paper-trading platform. Its active product surface includes stocks and crypto, synchronized charts, a central indicator and strategy engine, opportunities, watchlists, price alerts, backtesting, paper operations, news, an economic calendar, voice control, provider diagnostics, and responsive layouts.

[![CI](https://github.com/Rgrauferia/roxy_trading/actions/workflows/ci.yml/badge.svg)](https://github.com/Rgrauferia/roxy_trading/actions/workflows/ci.yml)
![Streamlit smoke](https://github.com/Rgrauferia/roxy_trading/actions/workflows/smoke.yml/badge.svg)

## Current operating contract

| Area | Current state |
|---|---|
| Crypto prices and candles | Operational through BinanceUS; source and freshness are displayed |
| Stock public fallback | Available through yfinance and always labeled delayed/fallback |
| Premium stock/options data | Blocked until Alpaca credentials validate or Polygon is configured |
| Charts | Operational 15m/1h workspace with indicators, drawings and per-user persistence |
| Watchlists and alerts | Durable and isolated by user; background monitor evaluates verified quotes every 60 seconds |
| Backtesting and operations | Versioned, durable and paper-only; realized paper results are separated from broker equity and unrealized P&L |
| Voice | Managed local service on `127.0.0.1:8010`; uses the visible asset/page/timeframe context |
| Real broker orders | Disabled by design |

Roxy never promotes delayed stock data to realtime and never treats a configured key as a validated connection. The current detailed audit, evidence paths and acceptance status are in [`docs/platform_audit_2026-07-18.md`](docs/platform_audit_2026-07-18.md).

## Quick start

1. Create and activate a virtual environment (macOS):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start or reuse the canonical Streamlit service:

```bash
make dev-web
```

Open `http://localhost:3000`. Normal development uses this single port and its LaunchAgent; do not start additional Streamlit instances on arbitrary ports.

Install or repair the canonical voice service when needed:

```bash
.venv/bin/python tools/voice_live_launchd.py install
.venv/bin/python tools/voice_live_launchd.py status
```

The installer copies the project `.env` to Roxy's owner-only managed LaunchAgent environment and starts Uvicorn with the project `PYTHONPATH`. Its safe default is `127.0.0.1:8010`; the health watchdog also verifies and repairs this service as part of the seven core LaunchAgents.

4. Run the complete regression suite:

```bash
PYTHONPATH=. .venv/bin/pytest -q
```

5. Inspect runtime health:

```bash
curl -fsS http://127.0.0.1:3000/_stcore/health
curl -fsS http://127.0.0.1:8010/health
```

The in-product `Diagnostico` and `Integraciones` pages are authoritative for provider operation, cache age, market state, simulated modes, authentication-storage security and recent watchdog results. The authentication row reports only aggregate policy/status information and never displays account identifiers, hashes or secrets.

The secrets API fails closed when admin credentials are absent. `/api/auth/mock-login` is disabled by default; enabling it requires `ROXY_ENABLE_MOCK_LOGIN=1`, a development/test `ROXY_ENV`, and a loopback client. The legacy permissive admin path has the same three-part guard through `ROXY_ALLOW_INSECURE_DEV_ADMIN=1`. Never enable either flag in production.

OAuth callback results store the one-time Roxy session token only as Fernet ciphertext in `oauth_results`; the legacy plaintext column remains empty and the row is deleted when consumed. The authentication diagnostic counts any legacy plaintext row as an error without printing its contents.

When `VOICE_API_KEY` is absent, voice/profile/knowledge endpoints accept only loopback clients and reject remote clients with HTTP 503. Remote access requires an explicit non-loopback `ROXY_VOICE_BIND_HOST`, `VOICE_API_KEY`, an allowlist in `ROXY_STATE_SYNC_USERS`, and HTTPS declared through `ROXY_VOICE_PUBLIC_BASE_URL=https://...` or a reviewed TLS-terminating proxy with `ROXY_VOICE_TLS_TERMINATED=true`. Do not expose port 8010 directly to a network. AI signal, A/B and automation endpoints never use the local fallback: they always require an admin or managed API key, and managed keys need the corresponding `ai:signal`, `ab:execute` or `auto:execute` scope.

Technical indicators use the versioned `roxy-indicators/1.1.0` engine. Charts, scanners, crypto horizons, feature generation, the legacy dashboard and the Alpaca bot share the same EMA/SMA, Wilder RSI/ATR, MACD, Bollinger and session-VWAP formulas; operational consumers must not implement private variants.

Cache freshness uses the versioned `roxy-cache/1.0.0` contract. Quotes, candles, screeners, news, voice sessions, profiles and identity assets have bounded TTL classes instead of private literals. Per-class `ROXY_CACHE_TTL_*` overrides are clamped to safe limits and surfaced in `Diagnostico`; stale market information must remain labeled rather than appearing live.

API consumption uses the versioned `roxy-api-budget/1.0.0` contract across fourteen market, news, identity, options and voice providers. Its values are conservative Roxy operational budgets, not claims about contractual plan limits. The default `protect` mode keeps normal traffic fail-open but applies a 60-second provider cooldown after a real HTTP 429; `observe` records only and `enforce` also blocks requests when the configured operational budget is exhausted. `Diagnostico` reports current/24-hour requests, errors, HTTP 429 events, locally blocked attempts and active providers; it returns `NO_DATA` without recent telemetry and never prints request URLs, payloads, headers or secrets.

Durable price alerts use `roxy-price-alert-monitor/1.0.0`. The `com.roxy.price-alert-monitor` LaunchAgent evaluates active rules every 60 seconds, deduplicates quote requests across users and writes `alerts/price_alert_monitor.json`. Crypto rules may trigger only from a fresh exchange ticker. Stock rules require fresh Alpaca broker data while the market is open; yfinance fallback is recorded as a degraded state and cannot trigger a rule. A transition is notified once and the diagnostic exposes report age, evaluated/blocked counts and provider gates.

```bash
.venv/bin/python tools/price_alert_monitor.py --no-notify --no-fail
.venv/bin/python tools/price_alert_monitor_launchd.py install
```

Autonomous opportunity synchronization uses `roxy-opportunity-sync/1.0.0`. The existing `ma_live` cycle now writes the broker/exchange-backed, trade-ready subset of each fresh AI brief to the system-managed `Roxy Oportunidades` watchlist and records evidence in `alerts/opportunity_sync.json`. A provider failure preserves the last known list; a healthy scan without a confirmed entry expires the old row into the opportunity archive. Watch-only candidates remain visible in the opportunity desk but are not promoted into an entry list. Voice can read the durable system list even when no opportunity page has populated the browser session.

The voice path resolves one shared opportunity snapshot for local replies, ElevenLabs client tools and Roxy OS metadata. Relative requests keep the visible crypto pair (including symbols such as `LINK/USD`) and fail closed when the requested asset is absent; Roxy never substitutes the first opportunity from another symbol. Spoken opportunity summaries expose market, timeframe, exact entry/stop/target precision, provider, data gate, alert gate and the remaining blocker.

`Diagnostico` also audits the frontend control contract. It reports Streamlit button/link counts and warns when a button is rendered without a conditional consumer, callback or explicit disabled state, or when placeholder/JavaScript links are introduced. The AST result is cached by file modification metadata so normal reruns remain fast.

The same page renders the evidence-backed seven-phase acceptance contract. Generate its durable snapshot with:

```bash
.venv/bin/python tools/platform_acceptance.py
.venv/bin/python tools/personal_task_check.py
.venv/bin/python tools/shopping_list_check.py
.venv/bin/python tools/home_assistant_check.py
.venv/bin/python tools/document_vault_check.py
.venv/bin/python tools/email_check.py
.venv/bin/python tools/device_sync_check.py
.venv/bin/python tools/mobile_client_check.py
.venv/bin/python tools/mobile_gateway.py status
.venv/bin/python tools/mobile_gateway_check.py
.venv/bin/python tools/launchd_recovery.py --service mobile_gateway
```

The command intentionally exits non-zero while the full vision remains `IN_PROGRESS`. Local or market-scoped acceptance is reported as partial and never promoted to unconditional completion; `alerts/platform_phase_acceptance.json` lists the exact evidence and blockers for every phase.

`Tareas` is the first durable personal-work module in the ecosystem phase. It has no demo seeds, isolates records by authenticated user, supports pending/in-progress/completed/archived states, and shares its store with Roxy's calendar/reminder agent. Its per-user revision participates in the device-sync contract. The local HTTPS/Bearer gateway is ready for physical testing, but physical-device use is not accepted until the local CA is trusted and an iPad/phone flow is verified. The diagnostic check validates persistence, lifecycle, voice/text coherence, and desktop/mobile rendering without mutating production user data.

`Compras` follows the same operational rule: no demo items, per-user isolation, quantity/unit/category fields, duplicate consolidation, recoverable purchased/archived states, and one source shared by voice, text and UI. Its revision is synchronized through the same conflict-safe contract as tasks and watchlists; remote transport remains fail-closed for unlisted users or requests without the configured Bearer credential.

`Hogar` integrates Home Assistant through `ROXY_HOME_ASSISTANT_URL` and `ROXY_HOME_ASSISTANT_TOKEN`. Without them it renders `SERVICE_NOT_CONFIGURED`; bad authentication, timeouts and unsafe URL configurations have distinct states. Reading supports common entity domains but strips raw attributes. Writes are limited to light/switch on/off and require `ROXY_HOME_CONTROL_ENABLED=1`, the `smart_home` session permission, an exact entity preview, and a second confirmation. Cameras and locks remain read-only.

`Documentos` is a per-user local vault, not an unrestricted filesystem browser. Imports are limited to 10 MB and an allowlist of document formats; names are sanitized, content is SHA-256 verified, duplicate active content is consolidated, and metadata can be archived/restored. Voice lists metadata only. Object content is encrypted with AES-256-GCM using a separate 32-byte key (`ROXY_DOCUMENT_VAULT_KEY_FILE`, or the private Roxy Application Support key by default); the index stores only a key fingerprint. Legacy plaintext objects migrate atomically, authenticated decryption detects tampering or a wrong key, and the UI reports `LOCAL_ENCRYPTED`, mixed encryption or key mismatch explicitly. Content is read only after `Preparar contenido` and integrity verification.

`Correo` supports fixed, read-only Gmail REST and Microsoft Graph adapters selected with `ROXY_EMAIL_PROVIDER=gmail|outlook`. Gmail uses `ROXY_GMAIL_ACCESS_TOKEN` with `gmail.readonly`; Outlook uses `ROXY_OUTLOOK_ACCESS_TOKEN` with `Mail.Read`. Both request metadata for at most five INBOX messages, never select bodies or attachments, and always return `SEND_DISABLED` for send attempts. Missing OAuth, rejected scopes, rate limits and timeouts are distinct states.

Internal navigation has a separate fail-visible contract. `Rutas de interfaz` scans literal `view`, `module` and `tab` destinations and warns when a link would be normalized into an unrelated page. The stock market map is a registered operational route with a dedicated responsive surface; news fallbacks use the canonical `Noticias` page instead of a hidden stock tab.

Device state synchronization uses `roxy-device-sync/1.1.0` on the canonical FastAPI backend (`GET`/`PUT /v1/state-sync/{user_id}`). Watchlists, alerts, visible UI state, personal tasks and shopping lists carry per-user monotonic revisions; writes require the revision read by the device and return HTTP 409 instead of overwriting a newer edit. Partial requests update only scopes explicitly sent by the client. Autonomous opportunity refreshes and alert telemetry do not churn the manual-edit revision, and system-managed opportunity lists cannot be replaced by clients. Remote access is fail-closed: configure `VOICE_API_KEY`, a non-loopback bind, HTTPS/reverse proxy and the explicit comma-separated `ROXY_STATE_SYNC_USERS` allowlist; without Bearer configuration the route is loopback-only and the UI states that iPad/phone synchronization is unavailable.

`/roxy-mobile` is an installable PWA client for that contract. It reads and edits watchlists, visible UI state, tasks and shopping lists; conflicts force a refresh instead of overwriting. The Bearer token and snapshots stay in memory only, API responses are never service-worker cached, and a non-local HTTP origin is blocked before credentials can be sent.

The isolated mobile gateway binds FastAPI on port 8443 with a private local CA, a LAN certificate, Bearer authentication and the `local_user` allowlist. Its key, token and environment live owner-only under Roxy Application Support, outside the repository and outside the normal voice LaunchAgent. Install or repair it with `.venv/bin/python tools/mobile_gateway.py install`; use `--rotate` only when every linked device can be paired again. On the Mac, open `http://127.0.0.1:8010/roxy-mobile-pair` to see the private pairing instructions and download the iOS/iPadOS `.mobileconfig` profile. Transfer that profile directly to the device, install it, enable full trust for `Roxy Mobile Local CA` under Certificate Trust Settings, then open the HTTPS URL displayed on the pairing page while both devices share the LAN. The profile contains only the public CA—not the Bearer or a private key. Do not send the Bearer credential through email or chat.

After the PWA completes an authenticated state sync from a non-loopback HTTPS client, it records `roxy-mobile-physical-proof/1.0.0`. The proof stores only the allowed user, timestamp and one-way fingerprints for the remote address, current Bearer and CA; it never stores the address or credential. Loopback and HTTP requests are rejected, and rotating the Bearer/CA invalidates old proof automatically. `alerts/mobile_gateway_check.json` remains `READY_FOR_PHYSICAL_TEST / UNVERIFIED` until that real remote flow succeeds, then promotes to `CONNECTED_PHYSICAL / VERIFIED_REMOTE_CLIENT`. A local TLS test is never treated as physical reachability.

The active market/news surfaces are canonical only. The unreachable legacy market and news renderers—including their fixed-equity fallback, prototype suggestions and duplicate paper controls—were removed. `Noticias` is source-backed RSS with cache/source/update status and follows the shared URL/session asset contract: exact ticker/company matches appear first, while unrelated headlines remain explicitly separated as general market context. `Capital` is the sole local simulator and labels paper data, user isolation, broker connectivity and real-order state explicitly. It preserves the selected symbol/market/timeframe and reports `REALIZED_PAPER_ONLY`; it does not infer broker equity or unrealized P&L from entry plans.

Local paper execution fails closed. `EXECUTION_ENABLED` defaults to off and must be explicitly opted in; quantity, price, symbol, fill rate and slippage are validated, a forced sell still cannot exceed the user's holdings, and every simulated fill records its caller-supplied price source/timestamp. The historical `execution.PaperTrader` used by the legacy backtester is memory-only by default and can write an audit CSV only when the caller supplies an explicit absolute path, so backtests cannot contaminate the operational paper journal.

Canonical navigation carries `symbol`, `market` and `tf` across the primary rail, the dashboard quick links, crypto alerts/news transitions and asset cards. The Crypto 20-minute workspace accepts `20m` as an actual selected timeframe instead of silently rewriting it to `1m`; its internal real-data panels may still declare their own source interval separately.

The options workspace is bound to that same selected-underlying contract. A stock opens its own contracts or an explicit no-contract state; a crypto selection does not leak unrelated equity options. Asset identity diagnostics cross-check the current live scans, AI brief, opportunity sync and durable watchlists against cached logo metadata/blobs, reporting coverage and exact missing symbols rather than only a file count.

`Actividad`, `Memoria` and `Notificaciones` are canonical focused routes. Activity is assembled only from the active user's durable alerts, archived opportunities and local paper fills. Memory identifies system-wide paper/backtest evidence and does not present it as private conversational memory. Notifications exposes per-user delivery states plus aggregate channel health without displaying global message content. The macro calendar preserves the selected asset context and its `CALENDAR_EVENTS_ONLY` flag never grants permission for a market signal.

Strategy-engine fixtures remain test-only. The Salto watchdog reports isolated fixture detections together with `fixture_only=true` and `published_market_rows=0`; they never appear as scanner rows, opportunities, prices or live signals.

Additional unreachable SMA, opportunity, stock-search, options and CSS-lock renderers were removed after an AST consumer audit. The compatibility adapter for the active stock terminal remains and is tested. Options chart frames reject non-finite spread/liquidity values and use explicit finite domains, preventing blocked/historical provider data from producing Vega infinite-extent warnings.

`Diagnostico` now enforces a frontend consumer contract. Every top-level function in `streamlit_app.py` must either have an internal name consumer or appear in the explicit external-API allowlist used by tests/watchdog adapters. The check is cached by file metadata and reports the exact uncontracted names when new dead code is introduced.

```bash
.venv/bin/python tools/roxy_ai_watch.py
.venv/bin/python tools/roxy_realtime_check.py --no-fail
```

## Safety defaults

```text
ROXY_ENABLE_LIVE_BROKER_EXECUTION=0
ALPACA_PAPER=true
ROXY_ALPACA_PAPER_AUTOTRADE=false
```

Keep secrets in `.env` or the configured credential vault. `.env`, runtime state, databases, alerts, output, logs and caches are excluded from Git. Do not place credentials in source files.

Session tokens are rotated, stored server-side only as hashes, expire after 30 days by default and are never appended to internal links. Legacy plaintext values are migrated at account-storage load. Use `Cerrar sesion` to revoke the remembered browser session. Client-provided profiles cannot create or recover accounts.

Local passwords require at least 10 characters. New hashes use versioned PBKDF2-SHA256 with 600,000 iterations; legacy hashes are upgraded after a successful login. Repeated failures are throttled persistently without storing the submitted username or email in the attempt table. Account backups and the active SQLite database use owner-only permissions.

## Backtester

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
The crypto scanner loads the BinanceUS market catalog once per run, excludes unsupported pairs before requesting candles, reuses one rate-limited exchange client across all symbols/timeframes, and writes the auditable coverage contract to `alerts/binanceus_symbol_coverage.json`. Every saved crypto row includes `provider_symbol`, `symbol_resolution`, and `data_source`; provider downtime remains explicit instead of being reported as valid coverage.
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

Operational readiness
---------------------

The `Precision` page reports only durable evidence: eligible paper episodes, closed outcomes, deduplicated signals and per-user backtests. Blocked candidates, repeated scanner snapshots and hypothetical revenue scenarios do not count toward accuracy or readiness. Live execution remains OFF behind the broker guardrails.

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

Runtime and dependency security
-------------------------------

The operational environment uses Python 3.12 and Streamlit 1.59. `alerts/dependency_audit.json` is consumed by Diagnostics, which distinguishes actionable runtime vulnerabilities from documented build-only findings. CCXT 4.5.67 currently requires Setuptools 82.0.1, so its source-distribution-only advisory remains an explicit build exception; no actionable runtime vulnerability is present. The inactive Python 3.9 rollback was removed from the project after migration verification; all LaunchAgents use `.venv`.

Output maintenance and runtime backups use local directories by default (`output/maintenance_archive` and `output/runtime_backups`). External storage is opt-in through `ROXY_OUTPUT_ARCHIVE_DIR`, `ROXY_RUNTIME_BACKUP_TARGET_DIR`, and `ROXY_EXTERNAL_DISK_PATH`; this prevents a mounted but unresponsive volume from freezing normal health checks. The backup supervisor identifies daemon processes independently from `screen`, accepts a fresh heartbeat from an orphaned session, and deduplicates multiple workers before starting another one.

The Streamlit dashboard includes a Snapshot Service section in the sidebar with:
- a button to run a snapshot now (user-level or all users),
- a Docker Compose hint to run the background service,
- local Start/Stop controls (development) that use `tools/process_manager.py` to spawn the background Python process and write a PID file in `run/snapshot.pid`.

Important: the local process manager is intended for development only. For production use `docker-compose`, `systemd`, or launchd as appropriate.

Broker safety and environment
-----------------------------

Use `.env.example` as the local template. Roxy accepts `ALPACA_API_SECRET` and the legacy alias `ALPACA_SECRET_KEY`; both must match the same paper/live mode as `ALPACA_API_KEY`. For paper mode, keep `ALPACA_PAPER=true` and use `https://paper-api.alpaca.markets`. `ALPACA_DATA_FEED=iex` is the default market-data feed; change it only if the Alpaca account has the required permissions. Template values such as `TU_KEY_PAPER` and `TU_SECRET_PAPER` are classified as `PLACEHOLDER_KEYS`; Roxy skips Alpaca probes, keeps signals unsafe, and asks for real paper credentials instead of reporting a generic auth failure.

The project `.env`, optional `.env.local`, and `~/Library/Application Support/RoxyTrading/.env` must be owner-only (`chmod 600`). `Diagnostico` verifies every present source without reading or displaying values. Present credentials are not considered connected: an Alpaca `AUTH_INVALID` result keeps paper orders off until a later account probe succeeds. ElevenLabs follows the same rule and enables the local browser voice fallback when its configured key is rejected.

Use the prompt-based setup command to rotate a supported provider. Secrets are read with `getpass`, never accepted as command-line arguments, validated before persistence, written atomically to both owner-only environments and propagated by restarting only the consumer LaunchAgents after successful authentication:

```bash
.venv/bin/python tools/provider_credential_setup.py alpaca
.venv/bin/python tools/provider_credential_setup.py elevenlabs
.venv/bin/python tools/provider_credential_setup.py home_assistant
.venv/bin/python tools/provider_credential_setup.py gmail
.venv/bin/python tools/provider_credential_setup.py outlook
```

Home Assistant validation performs a read-only `/api/` authentication check and always writes `ROXY_HOME_CONTROL_ENABLED=0`; controls still require the separate permission and confirmation flow. Gmail requires a token with `gmail.readonly`; Outlook requires `Mail.Read`. Both email adapters validate identity/profile metadata only and keep sending disabled. These commands accept access tokens, not refresh-token automation, so expiration remains visible as `AUTH_INVALID` and requires rotation until a complete OAuth refresh flow is configured.

Rejected credentials are not saved by default. `--save-unverified` is an explicit recovery override for provider outages and should not be used to bypass an authentication failure. The mobile HTTPS gateway loads the same owner-only managed provider environment before its isolated gateway environment; the latter overrides the remote Bearer. No provider secret or Bearer is embedded in the LaunchAgent.

After an ElevenLabs 401/403, Roxy opens an owner-only authentication circuit for six hours. Repeated renders use the local fallback without sending the same rejected key again. Rotating the key changes its non-secret fingerprint and bypasses the old circuit immediately; `ROXY_ELEVENLABS_AUTH_RETRY_SECONDS` can shorten or extend the retry window within the enforced 60-second to 24-hour bounds.

Robinhood is exposed only as a manual preview route. Even if `ROXY_ENABLE_LIVE_BROKER_EXECUTION=1` and Robinhood placeholders are configured, Roxy keeps Robinhood in `PREVIEW_ONLY` and never enables live broker order placement.

Autopilot
---------

Roxy Autopilot runs health checks, learning review, and paper-only strategy override proposals:

```bash
.venv/bin/python tools/roxy_autopilot.py --json
.venv/bin/python tools/roxy_autopilot_launchd.py install
```

The LaunchAgent runs every 60 seconds and writes `alerts/roxy_autopilot_status.json`. It is installed with `--apply`, but actual code/config writes still require `ROXY_AUTOPILOT_CODE_WRITE=1` in the service environment. Writes are allowlisted to strategy override/proposal files and real-money trading remains disabled.

Responsive route validation
---------------------------

The canonical desktop, iPad and phone surfaces can be validated end to end against the running dashboard:

```bash
.venv/bin/python tools/responsive_route_matrix.py
```

The matrix covers Actions, Charts, Watchlists, Crypto 20m, News, Calendar, stock Options, crypto Options, Portfolio, Activity, Memory, Notifications, Roxy and Diagnostics at three viewports. It requires visible route content, persisted symbol/market/timeframe, no horizontal overflow, no blocking browser errors, no empty chart extents and initial content within the 15-second cold-load SLO. The atomic report is written to `alerts/responsive_route_matrix.json`; screenshots are stored under `output/playwright/responsive_matrix/`. A complete, fresh 42/42 report—including average, p95 and maximum initial-content timing—is exposed as `Matriz responsive` on the Diagnostics page.

Weekly research report
----------------------

`weekly_ai.py` uses the normalized stock-history route and the central indicator engine. It no longer imports or executes the legacy Streamlit dashboard. Every result includes provider, data mode and fallback state; the batch is always `RESEARCH_ONLY`, and yfinance rows are `RESEARCH_ONLY_FALLBACK`. Weekly rankings never bypass Roxy's live smart-alert gates or become actionable notifications directly.

Asset identity cache
--------------------

Stocks/ETFs and crypto use `asset_identity.py`, an allowlisted disk cache with provider, source and fallback metadata. The current 25-symbol crypto scan universe is covered by CoinGecko IDs and official CDN images; cached images are embedded as data URIs so browser cards do not break when the upstream host is unavailable. CoinGecko rate limits fall back to the verified CDN URL for known assets, never to a letter-in-a-circle. Unknown assets use the neutral market icon and remain marked `DEGRADED`.

Macro calendar state
--------------------

Roxy synchronizes the official U.S. Bureau of Economic Analysis release schedule and Federal Reserve FOMC meeting calendar into `data/macro_events.csv`; it never inserts demonstration events. Run or inspect the source-backed refresh with:

```bash
PYTHONPATH=. .venv/bin/python tools/macro_calendar_sync.py
PYTHONPATH=. .venv/bin/python tools/macro_calendar_launchd.py status
```

The installed LaunchAgent refreshes every six hours and preserves the previous valid cache if either required source fails. `NOT_CONFIGURED` means no calendar, `NO_DATA` means zero valid rows, `DELAYED` means a stale/unsourced cache, and `CONNECTED` means the official source snapshot is current. Event coverage is separate: no event in the next 24 hours does not make a fresh source disconnected. Diagnostics exposes calendar data, the versioned sync report and the recurring service independently. BLS/CPI/NFP are not claimed as integrated: the official BLS schedule endpoint currently rejects this environment's automated retrieval with HTTP 403.

Unified voice context
---------------------

Roxy voice commands use the same selected symbol, timeframe, opportunity snapshot and durable watchlist state as the visible platform. Commands such as “explícame esta oportunidad”, “agrégala a mi watchlist” and “cambia a la gráfica de una hora” are resolved locally against verified platform context before any generic assistant response. A new session falls back to the central AI brief when the autonomous opportunity watchlist is empty; it does not invent a replacement opportunity. System-managed watchlists remain read-only, so voice additions are redirected to `Principal` with explicit feedback. ElevenLabs configuration and runtime health remain separate: an HTTP 401 runtime check is shown as `AUTH_INVALID`, while local platform commands continue to work.

Visual strategy engine
----------------------

`roxy_trader/operational_strategies.py` is the central, versioned detector for price structures. It uses the shared indicator engine and returns source-backed reasons plus chart geometry. The current contract covers 20 families including trends, EMA9/21 crosses, breakouts, retests, consolidation, triangles, wedges, support/resistance, volume surges, RSI divergences and RSI extreme zones. RSI extremes and EMA crosses remain confirmation states rather than automatic trade recommendations. The 15m/1h workspace displays a compact `ESTRUCTURAS REALES` strip and draws only the highest-priority verified geometry to control chart noise. Diagnostics reports engine version, family coverage and central-indicator dependency.

Reproducible backtesting
------------------------

The Backtesting page runs the versioned moving-average engine only against normalized provider OHLCV; it has no simulated-data fallback. Every durable run stores source metadata, exact strategy/execution parameters, engine versions and a SHA-256 input-contract hash. Execution uses next-open entries, fees, slippage and gap-aware stops. Risk metrics annualize according to stock/crypto market hours and timeframe. With at least 450 candles, Roxy also reports an anchored 70/30 chronological split without parameter refitting and keeps crossing-boundary trades out of both segments. Provider REST data is labeled as REST, not streaming. Version 2.2 reuses one central indicator pass across the run. The active equity curve uses the local Lightweight Charts bundle with crosshair, zoom and pan; legacy batch comparisons load only after explicit opt-in and use finite Plotly inputs. This keeps historical CSVs clearly separated from the durable current run and removes empty Vega-domain warnings from initial render. Diagnostics exposes the reproducibility, execution, performance, storage and equity-runtime contracts independently of strategy performance.

Operational frontend payloads
-----------------------------

Authenticated market and trading routes exclude Academy/login-only CSS and do not load the bundled Three.js universe. The stylesheet is stored as three exact, cached resources in `assets/styles/`: the shared base, Academy/auth additions and the responsive tail. Operational pages concatenate base + responsive; Login and Academy concatenate all three in the original order. The internal `Recursos visuales frontend` diagnostic fails explicitly if a chunk is missing, truncated or structurally invalid. Login retains its complete styles; Academy retains its dedicated visual system and loads WebGL only after useful learning markup. The progressive WebGL runtime lives in `assets/runtime/roxy_three_universe_runtime.js.html`; its loader validates the local Three.js bundle and safely serializes the vendor source before insertion. The Academy market example is a real, explicitly delayed daily close with a four-second request bound and is never described as streaming. Use `tools/dashboard_render_probe.py` and `tools/responsive_route_matrix.py` to verify useful-content timing, route state, browser errors and responsive overflow after global style changes.

The heavy voice runtime is scoped to its actual consumers: Dashboard, Alerts, Asset, Options, Studies, Roxy AI and the explicit stock/crypto workspaces. Its browser runtime lives in `assets/runtime/roxy_elevenlabs_assistant.js.html`; the loader validates its three interpolation markers and escapes script-significant characters in all JSON context before insertion. Diagnostics exposes this independently as `Runtime frontend de voz`. Passkey setup is scoped to Integrations, Roxy AI and Diagnostics. A signed diagnostic session may add `profile_startup=1` to capture `alerts/frontend_startup_profile.json` and `.pstats`; ordinary users cannot activate the profiler.

The professional Lightweight Charts browser surface is likewise isolated in `assets/runtime/roxy_live_candle_chart.html`. Its loader validates the payload marker, bundled vendor marker, chart root, crosshair, drawing and streaming contracts before rendering. Both chart data and the local vendor source use script-safe JSON serialization, and `Runtime frontend de graficas` reports template and bundle integrity independently from provider health.

The stock-specific professional fallback chart is isolated in `assets/runtime/roxy_actions_pro_chart.html`. Its loader validates the chart DOM, crosshair, quote synchronization and marker counts; payload/vendor interpolation is script-safe and the generated DOM id must match a strict allowlist. Diagnostics exposes this contract as `Runtime grafica profesional de acciones`.

The durable Backtesting equity surface is isolated in `assets/runtime/roxy_backtest_equity_chart.html`. It normalizes and bounds real persisted equity points, uses the same local Lightweight Charts vendor, exposes crosshair/zoom/pan without a remote dependency, and validates payload/vendor serialization through `Runtime curva de equity backtest`. Historical comparison charts remain available behind the explicit `Cargar comparación histórica legacy` switch, so they do not delay the default route.

The stock quote bridge runtime lives separately in `assets/runtime/roxy_stock_live_runtime.js.html`, and the server-pushed quote applicator lives in `assets/runtime/roxy_stock_server_refresh.js.html`. Their cached loaders validate stream/snapshot/payload markers, EventSource, snapshot fallback, quote events, market/provider badges and trade-state updates. Configured URLs and quote payloads use the same script-safe serializer. `Runtime frontend stock live` reports both resources independently from whether a premium stock provider is currently authenticated.

The synchronized dual-chart workspace accepts stock and crypto context, but its stock quote/WebSocket runtime is mounted only when the visible rows are actual stocks. Crypto pairs never enter Yahoo/stock symbol refreshes, and the terminal venue label reflects `CRYPTO` instead of a stock exchange.

The Actions overview does not advertise a chart vendor or provider that is not actually in use. Its provider badge is updated from the same quote event as the visible price and carries source plus open/closed market state. Empty Futures/FX cards are omitted until a verified provider supplies rows; they are not rendered as permanent placeholders. User-facing copy is account-neutral and avoids hard-coded names or invented product versions.

The Actions terminal presentation is stored in `assets/runtime/roxy_actions_reference_terminal.html` instead of a monolithic Python `f-string`. Its cached loader requires 33 unique slots and the complete terminal structure before rendering; missing, duplicated or unexpected slots fail explicitly. Data gathering, durable state and provider decisions remain in Python, while the visual resource can be reviewed independently. Diagnostics exposes this as `Presentacion terminal de Acciones`.

Professional chart targets are explicit-only. The chart and its level table share `explicit_chart_target_rows()`, which accepts persisted/provider/engine target fields and records their source. An entry without a supplied target no longer creates silent +2%, +5% or +10% objectives, nor derives R/R or “target reached” state from them. `Contrato de datos de graficas` also guards against local rolling/EMA calculations inside renderers; indicator columns remain owned by the central engine.

Professional chart trade geometry is direction-aware. `chart_trade_direction()` normalizes explicit LONG/SHORT vocabulary and uses stop/target geometry only as a fallback. Risk and reward areas, active-target selection, live distances and R/R now preserve SHORT semantics (stop above entry, target below) instead of assuming every setup is LONG. The chart data-contract diagnostic fails if this directional contract is removed.

Crypto chart streaming preserves the requested timeframe. BinanceUS 30m uses native 30m klines; 20m is explicitly derived from real 5m REST/WebSocket klines in the browser, with source-candle replacement to prevent cumulative WebSocket updates from double-counting volume. The payload exposes source interval, target interval, derivation and stream mode, and the runtime diagnostic guards the complete aggregation contract. Selecting 20m or 30m keeps that timeframe in the synchronized entry chart instead of falling back to 15m or 1h.

The Home chart exposes the complete canonical timeframe catalog (1m, 5m, 15m, 20m, 30m, 1h, 2h, 4h, daily and weekly) in real, loading and no-history states. Controls wrap on narrow screens instead of being clipped. Indicator labels match the actual central series: EMA9, SMA20, SMA40, Bollinger Bands and volume; the UI no longer calls SMA lines EMA lines.

The interactive Lightweight Charts surface supports EMA50 and EMA200 in addition to EMA9/20/21. Missing EMA columns are produced by the shared Python indicator function before serialization; JavaScript only renders the supplied values. Both long EMAs are optional, saved with chart settings and enabled by the Complete preset. The iframe's quick timeframe controls also cover all ten canonical periods, and diagnostics guard these controls together with the runtime resource.

Every live chart payload now runs one shared `add_central_indicators()` pass. It carries versioned RSI14, MACD/signal/histogram, ATR14/ATR%, session VWAP, average volume and relative volume alongside moving averages and Bollinger Bands. VWAP is a configurable intraday overlay; the runtime footer publishes current RSI, MACD histogram, ATR, VWAP and RVol and never substitutes browser-side formulas. The existing professional oscillator chart continues to draw RSI and MACD panels from these same columns.

The Lightweight Charts runtime renders synchronized RSI14 and MACD 12/26/9 panels beneath price/volume. RSI has a fixed 0–100 scale with 30/70 levels; MACD includes the main line, signal and signed histogram. Main-chart visible-range changes propagate to both panels, and RSI/MACD visibility is persisted through the same checkboxes and Clean/Complete/Naked presets. Mobile stacks the panels inside the chart iframe without overflowing the page.

Live charts expose session state and active-candle timing without treating a wall-clock schedule as provider confirmation. Crypto charts show a 24h countdown based on the latest real candle and requested interval. Intraday stock charts distinguish scheduled premarket, regular and after-hours, the provider's regular-market flag, and the observed session of the latest candle. Closed or stale data shows an explicit closed/waiting-provider state instead of recycling a fictitious countdown; extended-hours history remains requested for supported stock intervals.

Each intraday stock candle also carries an explicit New York session phase. The renderer preserves green/red directional fills and uses only a blue border/wick for premarket and an amber border/wick for after-hours, with a visible legend. This stock-only treatment is absent from 24h crypto charts and does not modify OHLCV or indicator values.

`Escala auto` now controls the actual Lightweight Charts price-scale mode: enabled uses Roxy's robust visible-candle range, while disabled leaves the axis manual across live ticks. The visible time window is validated and saved locally per symbol/timeframe; explicit chart synchronization stores the same viewport in the versioned server-side chart state so another device can restore it together with indicators and drawings.

Durable alerts now share one versioned monitor for price, true EMA crossing events and relative-volume thresholds. Technical rules are evaluated only from normalized, fresh OHLCV plus the central indicator engine; unsupported public stock fallbacks remain explicitly blocked. The chart workspace, Alerts page and voice commands all create rules against the same selected symbol/timeframe and durable watchlist state. A price-only refresh cannot masquerade as an EMA/RVol evaluation, and Diagnostics exposes the `roxy-durable-alert-monitor/2.0.0` contract independently from current provider availability.

New alert rules also carry an explicit lifetime. Due rules become `Expirada` before any provider request and remain auditable until manual archive. Triggered rules use durable notification delivery states: `PENDING`, `RETRY_PENDING`, `DELIVERED` and `DELIVERY_FAILED`; failed channels retry in later monitor cycles without re-fetching price or recalculating the original trigger. Legacy triggered records are never replayed implicitly. The Alerts page and Diagnostics expose expiry, delivery attempts, pending work and permanent failures instead of treating activation as proof that a notification was delivered.

EMA-cross alerts are configurable end to end. The full Alerts panel and the chart workspace accept fast/slow periods, the durable store validates and persists them, the recurring monitor requests those exact series from the central indicator engine, and voice commands parse the same pair. Button labels and saved-rule labels reflect the selected periods, so custom EMA12/34 rules do not silently run as EMA9/21.

Device synchronization treats alert-monitor telemetry as server-authoritative. A valid remote snapshot can add an active rule or explicitly archive one, but it cannot roll `DELIVERED` back to `PENDING`, erase a trigger/expiry, or replace verified source and monitor fields with stale device state. Incoming alert identity is normalized and unsupported rule types are discarded before persistence.

Voice opportunity context is freshness- and module-bound. A visible session table expires after ten minutes or immediately when the user changes modules; autonomous watchlists and the AI brief have the same freshness gate. Brief rows that have not passed the trade-ready contract are called `watch_candidate` everywhere—including Python replies, ElevenLabs instructions, browser fallback and crypto headings. Their scan close is preserved as `current_price` with an explicit normalized-scan basis, source and data state, and their score is labeled as a watch score rather than trade confidence.

Opportunity targets are explicit-only. The central normalizer no longer injects silent +2%, +5% or +10% levels; it derives a price only from a supplied target percentage or an explicit `TRADE_FOR_*PCT` decision and records that basis. Scan-only WATCH candidates carry `MISSING_EXPLICIT_TARGET` and `WATCH_ONLY_INCOMPLETE`. Voice calls their entry/stop scan references and states that no complete executable level set exists.
