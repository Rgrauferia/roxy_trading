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

The Streamlit dashboard includes a Snapshot Service section in the sidebar with:
- a button to run a snapshot now (user-level or all users),
- a Docker Compose hint to run the background service,
- local Start/Stop controls (development) that use `tools/process_manager.py` to spawn the background Python process and write a PID file in `run/snapshot.pid`.

Important: the local process manager is intended for development only. For production use `docker-compose`, `systemd`, or launchd as appropriate.
