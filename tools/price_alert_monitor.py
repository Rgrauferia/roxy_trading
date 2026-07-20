from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from living_market import build_live_price_snapshot
from roxy_trader.indicators import IndicatorConfig, add_indicators
from roxy_paths import alerts_dir, data_dir
from roxy_trader.alert_monitor import monitor_price_alerts
from roxy_trader.watchlists import WatchlistStore
from symbol_detail import fetch_symbol_history_with_source


DEFAULT_REPORT_PATH = alerts_dir() / "price_alert_monitor.json"
DEFAULT_WATCHLIST_PATH = data_dir() / "roxy_watchlists.json"


def build_technical_alert_snapshot(
    symbol: str,
    market: str,
    timeframe: str,
    fast_period: int,
    slow_period: int,
) -> dict[str, Any]:
    """Load real candles once and expose only central-engine technical values."""

    history, source = fetch_symbol_history_with_source(
        symbol,
        market=market,
        timeframe=timeframe,
        include_extended_hours=True,
    )
    if history is None or history.empty:
        return {
            "freshness": "NO_DATA",
            "source": str(source.get("label") or source.get("source") or "sin velas"),
            "source_mode": str(source.get("mode") or ""),
            "provider": str(source.get("provider") or ""),
        }
    enriched = add_indicators(
        history,
        config=IndicatorConfig(ema_windows=(int(fast_period), int(slow_period))),
    )
    required = [f"ema{int(fast_period)}", f"ema{int(slow_period)}", "relative_volume"]
    clean = enriched.dropna(subset=required).tail(2)
    if len(clean) < 2:
        return {
            "freshness": "NO_DATA",
            "source": str(source.get("label") or source.get("source") or "velas insuficientes"),
            "source_mode": str(source.get("mode") or ""),
            "provider": str(source.get("provider") or ""),
            "indicator_engine": str(enriched.attrs.get("indicator_engine", {}).get("engine") or ""),
        }
    previous, current = clean.iloc[-2], clean.iloc[-1]
    stamp = None
    pd = None
    if "ts" in clean.columns:
        import pandas as pd

        stamp = pd.to_datetime(current.get("ts"), errors="coerce", utc=True)
    age_seconds = None
    if stamp is not None and pd is not None and not pd.isna(stamp):
        age_seconds = max(0, int((datetime.now(timezone.utc) - stamp.to_pydatetime()).total_seconds()))
    return {
        "previous_fast": float(previous[f"ema{int(fast_period)}"]),
        "previous_slow": float(previous[f"ema{int(slow_period)}"]),
        "current_fast": float(current[f"ema{int(fast_period)}"]),
        "current_slow": float(current[f"ema{int(slow_period)}"]),
        "relative_volume": float(current["relative_volume"]),
        "indicator_engine": str(enriched.attrs.get("indicator_engine", {}).get("engine") or ""),
        "freshness": "FRESH" if age_seconds is not None else "UNKNOWN",
        "age_seconds": age_seconds,
        "source": str(source.get("label") or source.get("source") or ""),
        "source_mode": str(source.get("mode") or ""),
        "provider": str(source.get("provider") or ""),
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _notifier(message: str) -> dict[str, Any]:
    from notifier import send_notification_message

    return send_notification_message(
        message,
        reason="durable_market_alert_triggered",
        header="ROXY · ALERTA DE MERCADO",
        metadata={"producer": "price_alert_monitor"},
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate durable Roxy price and technical alerts with verified data.")
    parser.add_argument("--watchlist-path", default=str(DEFAULT_WATCHLIST_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--lock-path", default=str(alerts_dir() / "price_alert_monitor.lock"))
    parser.add_argument("--max-age-seconds", type=int, default=120)
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--no-fail", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = Path(args.report_path).expanduser()
    lock_path = Path(args.lock_path).expanduser()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        if fcntl is not None:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("Roxy price alert monitor: SKIPPED (another run is active)")
                return 0
        report = monitor_price_alerts(
            WatchlistStore(Path(args.watchlist_path).expanduser()),
            build_live_price_snapshot,
            technical_fetcher=build_technical_alert_snapshot,
            notifier=None if args.no_notify else _notifier,
            max_age_seconds=max(1, int(args.max_age_seconds)),
        )
        atomic_write_json(report_path, report)
    print(
        "Roxy price alert monitor: "
        f"{report.get('status')} | active={report.get('active_alerts')} "
        f"evaluated={report.get('evaluated')} blocked={report.get('blocked')} triggered={report.get('triggered')}"
    )
    print(f"JSON: {report_path}")
    return 0 if args.no_fail or report.get("status") in {"OK", "NO_DATA", "WARNING"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
