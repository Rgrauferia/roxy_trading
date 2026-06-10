# Roxy AI Trading Assistant Specification

## Goals
- Provide trade signals (entry/exit) with human-readable rationale.
- Support instrument classes: US equities and crypto (configurable).
- Support frequencies: intraday (5m/15m) and daily swing.
- Provide risk-aware position sizing suggestions.

## Success Metrics
- Sharpe ratio > baseline (configurable)
- Max drawdown within limit
- Hit rate and average R:R tracked per signal

## Signal Format
- action: `buy`, `sell`, `hold`, `short`, `cover`
- symbol: ticker string
- price: suggested limit/market
- size_pct: suggested portfolio fraction (0-1)
- stop_loss: absolute price or pct
- take_profit: absolute price or pct
- rationale: human-readable explanation

## Safety Rules
- Never suggest > `max_position_pct` per symbol (default 0.05)
- Respect instrument tradability list
- Require `confidence` threshold for live execution

## Data Inputs
- Recent feature window: last N candles + technical indicators
- Account equity and existing positions
- Market volatility (ATR)

## Interfaces
- `/api/ai/signal` POST: input: symbols list, horizon, context; output: list of signals
- Streamlit UI: single-button "Generate Signals" and backtest quick-run

## Audit & Explainability
- Record inputs, model version, prompt, and generated rationale to `db/ai_runs`
- Provide replay endpoint to re-run prompt with cached features

## Tests
- Unit tests for signal format and constraints
- Backtest integration test applying signals to `backtester.py`

