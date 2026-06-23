import os

from tools import ma_daily
from tools.ma_daily import cleanup_daily_outputs, extract_saved_scan_path


def test_extract_saved_scan_path():
    output = """
some output
Saved: /tmp/ma_strategy_both_20260606.csv
"""

    assert extract_saved_scan_path(output) == "/tmp/ma_strategy_both_20260606.csv"


def test_extract_saved_scan_path_returns_none_when_missing():
    assert extract_saved_scan_path("No save happened") is None


def test_cleanup_daily_outputs_keeps_recent_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ma_daily, "OUTPUT_DIR", tmp_path)
    old_files = []
    new_files = []
    for prefix in ("ma_strategy_both", "ma_backtest_summary_stocks", "ma_backtest_trades_stocks"):
        old_path = tmp_path / f"{prefix}_20260606_000000.csv"
        new_path = tmp_path / f"{prefix}_20260607_000000.csv"
        old_path.write_text("old")
        new_path.write_text("new")
        os.utime(old_path, (1, 1))
        os.utime(new_path, (2, 2))
        old_files.append(old_path)
        new_files.append(new_path)

    removed = cleanup_daily_outputs(1)

    assert len(removed) == 3
    assert all(not path.exists() for path in old_files)
    assert all(path.exists() for path in new_files)
