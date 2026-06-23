Roxy Trading — UI & Voice Assistant Demo

Overview

This document describes the UI improvements and the voice-assistant prototype added to the repository.

What's included

- Streamlit dashboard (`streamlit_app.py`) enhancements:
  - Compact styled header and subtitle
  - `Overview` expander with metrics: accounts, open positions, simulated trades
  - Aggregated equity chart (from snapshot points)
  - `Top Picks` table + bar chart (reads `config.TOP_PICKS_FILE` when present)
  - `SMA Strategy` tab for the SMA 20/40/100/200 workflow, filtered BUY signals, downgraded raw BUY signals and daily report
  - Voice assistant prototype (client-side Web Speech API + simple backend `tools/voice_assistant.py`)

Voice Assistant (prototype)

- The backend stub is in `tools/voice_assistant.py` and implements simple rule-based replies (balance, positions, greetings, help).
- The UI uses a text input and a small client-side HTML widget that attempts to use the Web Speech API for transcription and a client-side TTS call to speak replies.
- This is a local prototype for demos and not suitable for production LLM usage. For a production voice assistant, integrate a secure server-side LLM with authentication and rate limiting.

Run the dashboard locally

1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2. Start Streamlit:

```bash
streamlit run streamlit_app.py
```

3. Open the displayed URL in your browser. The `Overview` panel is expanded by default. The voice assistant expander contains the text input and the browser speech capture buttons.

SMA daily workflow

```bash
.venv/bin/python tools/ma_daily.py
```

The dashboard reads the latest full SMA scan from `output/ma_strategy_both_*.csv` and the daily report files in `alerts/ma_daily_report.txt` and `alerts/ma_daily_summary.json`.

To keep those files updated automatically on macOS:

```bash
.venv/bin/python tools/ma_daily_launchd.py install
.venv/bin/python tools/ma_daily_launchd.py status
```

The default schedule is daily at 18:05 local time. Logs are written to `logs/ma_daily.out` and `logs/ma_daily.err`.

SMA live intraday workflow

```bash
.venv/bin/python tools/ma_live.py --once
.venv/bin/python tools/ma_confluence.py --save
.venv/bin/python tools/options_scan.py --save
.venv/bin/python tools/ma_live_launchd.py install
```

The live workflow scans `15m` and `1h` continuously, includes stock extended-hours candles when available, and writes `alerts/ma_live_report.txt` plus `alerts/ma_live_summary.json`. The confluence workflow specializes this into `1h trend filter + 15m entry trigger`, checks 2%, 5%, and 10% targets against stop risk, and writes `alerts/ma_confluence_report.txt`. The options workflow selects liquid call contracts after an actionable stock confluence plan and writes `alerts/options_report.txt`. The `SMA Strategy` tab can switch between `Live 15m/1h` and `Daily 1d` and includes `Confluence` and `Options` views.

Focused Roxy workflow

- `Centro`: command center by symbol with action, reason, what Roxy is waiting for, entry, stop, targets, platform preview and the anti-noise alert contract.
- `Plan de trade`: full symbol analysis with candlesticks, SMA/EMA lines, Bollinger bands, support/resistance, entry zone, stop zone and 2%/5%/10% targets.
- `Opciones`: contract quality panel with DTE, delta, spread, volume, open interest, break-even, max loss and Greek-data quality (`FULL_GREEKS`, `ESTIMATED_DELTA`, etc.).
- `Roxy Lab`: daily strategy decision summary showing what to promote, tighten, watch or keep collecting.
- `Estudios`: strategy playbooks with real examples detected by Roxy and the same professional chart layers.

Alert rule

Roxy should notify only when the smart gate is complete:

- 1h confirms the higher-timeframe structure.
- 15m gives the entry trigger.
- Volume is at least acceptable.
- Risk to stop is low enough.
- Minimum 2% target is viable.
- Historical filter and memory do not block the setup.

If any condition fails, Roxy keeps the symbol in WATCH/NO_TRADE and shows the blocker instead of sending noise.

Notes and limitations

- Browser speech recognition requires a modern browser (Chrome/Edge) that supports the Web Speech API. If the API isn't available the widget will show a message.
- The text-to-speech used in the UI is the browser's `speechSynthesis` API; this runs entirely on the client.
- The backend voice assistant is a simple rule-based prototype. Replace `tools/voice_assistant.generate_reply()` with an LLM backend if you want conversational intelligence.

Server-side service

`tools/voice_service.py` is a FastAPI scaffold that exposes secure API endpoints including `/v1/assist` and `/v1/webhooks/tradingview`.

Quick run (development):

```bash
# optional: set a token to require API key
export VOICE_API_KEY=changeme
uvicorn tools.voice_service:app --host 127.0.0.1 --port 8000 --reload
```

Request example (curl):

```bash
curl -H "Authorization: Bearer $VOICE_API_KEY" -X POST http://127.0.0.1:8000/v1/assist -d '{"query":"balance","user":"alice"}' -H "Content-Type: application/json"
```

TradingView webhook example:

```bash
export TRADINGVIEW_WEBHOOK_SECRET=changeme-tv
curl -X POST http://127.0.0.1:8000/v1/webhooks/tradingview \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NASDAQ:AAPL","timeframe":"15","signal":"BUY","price":185.25,"passphrase":"changeme-tv"}'
```

The webhook endpoint records analysis confirmations only. It writes to `alerts/tradingview_webhooks.jsonl`, redacts secrets, and never places live orders.

Next steps

- Create a dedicated `ui/prototype` branch and open a PR with screenshots and demo instructions.
- Add e2e tests for key UI flows (login flows, simulate trade, snapshot exports).
- If you want, I can prepare the branch and open the PR now.
