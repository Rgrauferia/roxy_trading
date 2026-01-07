Roxy Trading Scanner

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