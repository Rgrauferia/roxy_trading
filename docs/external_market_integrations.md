# Roxy External Market Integrations

Roxy can enrich market context with external sources, but live money execution stays disabled unless a reviewed broker adapter explicitly enables paper or live trading.

## Environment Variables

Configure these in Render or in your local `.env`. Do not commit real values.

```bash
# Finviz Elite screener export CSV URL. This URL can contain an auth token.
ROXY_FINVIZ_EXPORT_URL=

# Crypto.com Exchange. Public market data does not need private keys.
ROXY_CRYPTOCOM_API_KEY=
ROXY_CRYPTOCOM_API_SECRET=
ROXY_CRYPTOCOM_BASE_URL=https://api.crypto.com/exchange/v1
ROXY_EXTERNAL_CONFIRMATION_ENABLED=true
ROXY_EXTERNAL_CONFIRMATION_REMOTE=

# TradingView confirmation and chart layer.
TRADINGVIEW_WEBHOOK_SECRET=
TRADINGVIEW_PUBLIC_WEBHOOK_URL=
ROXY_TRADINGVIEW_WIDGET_ENABLED=true
ROXY_TRADINGVIEW_LIBRARY_URL=
```

Legacy aliases `CRYPTO_COM_API_KEY` and `CRYPTO_COM_API_SECRET` are still accepted.

## Finviz Elite

Finviz is used as a screener/export source for stocks. Paste the full Elite export URL into `ROXY_FINVIZ_EXPORT_URL`.

Roxy redacts `auth`, `token`, `api_key`, `secret`, and `passphrase` values before showing status or logs.

Use Finviz as:

- early opportunity discovery,
- sector/filter context,
- cross-check against Roxy's live provider.
- market-pulse context from screener exports: major movers, unusual volume, pattern tags, upgrades/downgrades, sector pressure, and relative strength.

Do not use Finviz alone as a realtime execution trigger.

### Finviz Market Pulse

Roxy now builds a normalized `market_pulse.finviz` object from the Finviz Elite export rows. This lets the platform show and reason about sections like the screenshots you shared:

- major movers, for example `NVDA +4.21%` or `RIVN -18.12%`,
- pattern/signal tags such as `Wedge Up`, `Channel Up`, `Double Bottom`, `Unusual Volume`, `Upgrades`, or `Downgrades`,
- bullish and bearish watchlists,
- sector counts and sector pressure.

The output is intentionally derived from your configured export CSV instead of scraping the Finviz page. Keep the full export URL only in Render/local environment variables because it can contain an `auth` token.

Example object:

```json
{
  "market_pulse": {
    "finviz": {
      "row_count": 50,
      "major_movers": [],
      "bullish_watchlist": [],
      "bearish_watchlist": [],
      "pattern_signals": [],
      "sector_counts": {}
    }
  }
}
```

Roxy should use this as context, not as final advice. A Finviz bullish tag can raise confidence only when the live chart, entry, stop, target, volume, and risk also agree.

### Finviz Pattern Strategies

Roxy also translates Finviz chart labels into structured operating playbooks. Examples:

- `Channel Up`: buy only near the lower channel line after confirmation; take profit near the upper line; stop below the channel.
- `Channel Down`: sell/reduce near the upper channel line; target the lower line; stop above the channel.
- `Triangle Asc.`: prefer entries near the rising support or on a confirmed breakout over the horizontal roof.
- `Triangle Desc.`: prefer rejection from descending resistance or a confirmed break under support.
- `Wedge`, `Wedge Up`, `Wedge Down`: treat as compression; avoid the middle; act near the edges or after breakout confirmation.
- `Double Bottom`, `Multiple Bottom`: look for support confirmation and neckline break.
- `Double Top`, `Multiple Top`, `Head&Shoulders`: look for rejection or neckline breakdown.
- `TL Supp.`, `TL Resist.`, `Horizontal S/R`: convert trendline/support-resistance labels into support, resistance, stop and target zones.

The generated objects appear under:

```json
{
  "market_pulse": {
    "finviz": {
      "pattern_strategies": [
        {
          "symbol": "AAPL",
          "finviz_signal": "Channel Up",
          "strategy_family": "Ascending Channel",
          "action": "COMPRAR",
          "status": "WAIT_LIVE_CHART_CONFIRMATION",
          "entry_zone": "Linea inferior del canal",
          "target_zone": "Linea superior del canal",
          "stop_zone": "Debajo de la linea inferior"
        }
      ]
    }
  }
}
```

This is intentionally a plan, not automatic execution. Roxy should only upgrade it to `OPERAR AHORA` when the live chart confirms the actual line, current price location, entry, stop, target, volume, risk/reward, and data health.

## Crypto.com Exchange

The connector starts with public market data:

- ticker,
- bid/ask/last price,
- volume,
- change percent when available.

Private keys are stored only for future account-safe integrations. The current connector does not place orders.

## Roxy Decision Confirmation

When Finviz or Crypto.com are configured, Roxy can attach a short-lived external market snapshot to each opportunity before the decision engine ranks it.

The decision engine now stores this under:

- `roxy_decision.external_confirmation.confirmed`
- `roxy_decision.external_confirmation.sources`
- `roxy_decision.external_confirmation.price`
- `roxy_decision.external_confirmation.change_pct`
- `roxy_decision.external_confirmation.score_adjustment`
- `roxy_decision.external_confirmation.reasons`

This means the same AAPL or BTC setup can be upgraded when the external source confirms the direction, or downgraded when the outside data contradicts it. Roxy still requires entry, stop, target, risk, live health, and strategy confirmation before marking a setup as operable.

`ROXY_EXTERNAL_CONFIRMATION_ENABLED=false` disables this layer. `ROXY_EXTERNAL_CONFIRMATION_REMOTE=true` allows remote public fetches even without private Crypto.com credentials.

## What This Unlocks

- Finviz can feed stock-screening candidates by sector, volume, relative strength, patterns, and filters.
- Crypto.com can provide live crypto exchange prices for BTC, ETH, SOL, XRP, BNB, and DOGE.
- TradingView can become the visual confirmation layer and later webhook confirmation layer.
- Roxy can explain whether an opportunity is confirmed, contradicted, or still waiting.
- The signal history can later be backtested by source: Roxy-only vs. Roxy + Finviz vs. Roxy + Crypto.com.
- Voice Roxy can answer: "Que confirma esta oportunidad?" using the same `external_confirmation` object.

## TradingView

TradingView is used for:

- visual chart confirmation,
- alerts/webhook confirmations,
- external chart links.

TradingView webhooks confirm or contradict Roxy setups. They never place orders.

## Security Notes

If a key or secret was shown in a screenshot, rotate it in that provider account and replace it in Render/local environment variables.

Never paste private keys into:

- frontend code,
- Streamlit markdown,
- screenshots,
- `.env.example`,
- tests.

## Local Smoke Test

Run:

```bash
PYTHONPATH=. pytest -q tests/test_external_market_sources.py
```

Optional connector status from Python:

```bash
PYTHONPATH=. python - <<'PY'
from tools.external_market_sources import build_external_market_snapshot
snapshot = build_external_market_snapshot(include_remote=False)
for status in snapshot["statuses"]:
    print(status["provider"], status["status"], status["mode"])
PY
```
