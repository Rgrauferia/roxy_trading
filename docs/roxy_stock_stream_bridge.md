# Roxy Stock Stream Bridge

Roxy can show moving stock prices without exposing market-data keys in the browser by running a small server-side stream bridge.

## What it does

- Reads `ALPACA_API_KEY` and `ALPACA_API_SECRET` only on the server.
- Connects to Alpaca market-data WebSocket when available.
- Emits sanitized Server-Sent Events from `/v1/market/stock-stream`.
- Falls back to Alpaca REST latest trade/quote, then a public delayed quote fallback if streaming is unavailable.
- Keeps the Streamlit UI working even when the bridge is offline.

## Local run

From the project root:

```bash
export ALPACA_API_KEY="your_key"
export ALPACA_API_SECRET="your_secret"
export ALPACA_DATA_FEED="iex"
export ROXY_STOCK_STREAM_URL="http://127.0.0.1:8765/v1/market/stock-stream"
export ROXY_STOCK_STREAM_ALLOWED_ORIGINS="http://127.0.0.1:3000,http://localhost:3000"

python3 -m uvicorn tools.roxy_stock_stream_bridge:app --host 127.0.0.1 --port 8765
```

In another terminal, start Roxy normally:

```bash
streamlit run streamlit_app.py
```

Health check:

```bash
curl http://127.0.0.1:8765/health
```

Stream check:

```bash
curl -N "http://127.0.0.1:8765/v1/market/stock-stream?symbols=AAPL,MSFT,NVDA"
```

## Render

This repository now includes a second Render web service in `render.yaml`:

```text
roxy-stock-stream
```

It uses `Dockerfile.stock-bridge` and exposes:

```text
https://roxy-stock-stream.onrender.com/v1/market/stock-stream
```

The main `roxy-trading` service is already configured to use that URL through:

```text
ROXY_STOCK_STREAM_URL=https://roxy-stock-stream.onrender.com/v1/market/stock-stream
```

In Render, make sure the `roxy-stock-stream` service has these secret env vars:

```text
ALPACA_API_KEY=<secret>
ALPACA_API_SECRET=<secret>
ALPACA_DATA_FEED=iex
```

The main `roxy-trading` service only receives `ROXY_STOCK_STREAM_URL`; it never sends API keys to frontend code.

The bridge rejects wildcard CORS. `ROXY_STOCK_STREAM_ALLOWED_ORIGINS` must contain exact comma-separated `http`/`https` origins. Local startup binds to `127.0.0.1`; a remote deployment must explicitly set `ROXY_STOCK_BRIDGE_HOST=0.0.0.0`. Proxy headers trust loopback only unless `ROXY_STOCK_BRIDGE_TRUSTED_PROXIES` is deliberately changed for a known proxy range.

If you manage Render from a Blueprint, sync/redeploy the blueprint after pushing the repo. If the service is created manually, create a Docker web service named `roxy-stock-stream`, point it to this repo, and use `Dockerfile.stock-bridge`.

For a manually created Render Docker service, verify these exact settings:

```text
Dockerfile Path: ./Dockerfile.stock-bridge
Docker Context Directory: .
Health Check Path: /health
Start Command: leave blank
```

The stock bridge image also includes `scripts/stock_bridge_entrypoint.sh` and
`scripts/render_start.sh`, so the service still boots if Render has an older
manual Start Command pointing to either script. Leaving Start Command blank is
still preferred because the Dockerfile `CMD` is the canonical startup path.

If the manual service accidentally uses the main `Dockerfile`, set this env var on `roxy-stock-stream`:

```text
ROXY_SERVICE_MODE=stock-stream
```

The main Docker image will then start the stock stream bridge instead of Streamlit.

## Market-hours behavior

Stock trades only move quickly when the selected data feed has active market prints. During closed market hours, Roxy should show the last available price and label it as closed/stale instead of simulating fake movement.
