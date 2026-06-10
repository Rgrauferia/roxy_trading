from __future__ import annotations

import argparse
import sys
import warnings
from glob import glob
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import notifier
from roxy_paths import alerts_dir, output_dir
from roxy_ai import (
    apply_global_alert_context,
    build_brief,
    build_notification_lines,
    load_memory,
    market_session_status,
    realtime_health_status,
    source_freshness_status,
    write_brief,
)


OUTPUT_DIR = output_dir()
ALERTS_DIR = alerts_dir()


def latest_file(pattern: str, *, directory: Path = OUTPUT_DIR) -> str | None:
    files = glob(str(directory / pattern))
    if not files:
        return None
    files.sort(key=lambda path: Path(path).stat().st_mtime, reverse=True)
    return files[0]


def read_csv(path: str | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Roxy AI 24h watch brief and send opportunity notifications.")
    parser.add_argument("--scan-csv", help="Live scan CSV. Defaults to latest output/ma_live_strategy_*.csv.")
    parser.add_argument("--confluence-csv", help="Confluence CSV. Defaults to latest output/ma_confluence_*.csv.")
    parser.add_argument("--options-csv", help="Options CSV. Defaults to latest output/options_candidates_*.csv.")
    parser.add_argument("--notify", action="store_true", help="Send configured alert notifications.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scan_path = args.scan_csv or latest_file("ma_live_strategy_both_*.csv") or latest_file("ma_live_strategy_*.csv")
    confluence_path = args.confluence_csv or latest_file("ma_confluence_*.csv")
    options_path = args.options_csv or latest_file("options_candidates_*.csv")

    scan_df = read_csv(scan_path)
    confluence_df = read_csv(confluence_path)
    options_df = read_csv(options_path)

    brief = build_brief(
        confluence_df=confluence_df,
        options_df=options_df,
        scan_df=scan_df,
        memory=load_memory(),
    )
    source_files = {
        "scan": scan_path,
        "confluence": confluence_path,
        "options": options_path,
    }
    brief["source_files"] = source_files
    brief["source_freshness"] = source_freshness_status(source_files)
    brief["realtime_health"] = realtime_health_status()
    brief["market_session"] = market_session_status()
    brief = apply_global_alert_context(brief)
    write_brief(brief)

    lines = build_notification_lines(brief)
    if args.notify and lines:
        notifier.notify_if_changed(lines)

    print(f"Roxy AI alerts: {brief.get('alert_count')} | watch: {brief.get('watch_count')}")
    print(f"Brief: {ALERTS_DIR / 'roxy_ai_brief.txt'}")


if __name__ == "__main__":
    main()
