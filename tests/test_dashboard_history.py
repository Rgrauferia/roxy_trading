from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from dashboard_history import append_scan_history, compact_scan_history, scan_history_duplicate


def base_row(**overrides):
    row = {
        "ts": "2026-06-10T14:00:00+00:00",
        "market": "stocks",
        "symbol": "AAPL",
        "tf": "1h",
        "signal": "PRE-BUY",
        "score": 72,
        "rr_tp2": 1.8,
        "entry": 210.0,
        "stop": 205.0,
        "tp2": 219.0,
    }
    row.update(overrides)
    return row


def test_scan_history_duplicate_detects_same_sample_inside_live_interval():
    previous = base_row(ts="2026-06-10T14:00:00+00:00")
    current = base_row(ts="2026-06-10T14:00:30+00:00")

    assert scan_history_duplicate(previous, current, min_interval_seconds=55)


def test_scan_history_duplicate_allows_changed_signal_inside_live_interval():
    previous = base_row(ts="2026-06-10T14:00:00+00:00", signal="WAIT")
    current = base_row(ts="2026-06-10T14:00:30+00:00", signal="BUY")

    assert not scan_history_duplicate(previous, current, min_interval_seconds=55)


def test_append_scan_history_skips_recent_duplicate(tmp_path):
    scan_db = tmp_path / "scan_history.csv"

    first = append_scan_history(scan_db, base_row(ts="2026-06-10T14:00:00+00:00"))
    duplicate = append_scan_history(scan_db, base_row(ts="2026-06-10T14:00:30+00:00"))
    stored = pd.read_csv(scan_db)

    assert first["appended"] is True
    assert duplicate == {"appended": False, "reason": "duplicate_recent", "rows": 1}
    assert len(stored) == 1


def test_append_scan_history_appends_after_interval_and_trims(tmp_path):
    scan_db = tmp_path / "scan_history.csv"

    append_scan_history(scan_db, base_row(ts="2026-06-10T14:00:00+00:00", symbol="AAPL"), max_rows=2)
    append_scan_history(scan_db, base_row(ts="2026-06-10T14:01:00+00:00", symbol="AAPL"), max_rows=2)
    result = append_scan_history(scan_db, base_row(ts="2026-06-10T14:02:00+00:00", symbol="MSFT"), max_rows=2)
    stored = pd.read_csv(scan_db)

    assert result["appended"] is True
    assert len(stored) == 2
    assert stored["symbol"].tolist() == ["AAPL", "MSFT"]


def test_append_scan_history_preserves_unreadable_existing_file(tmp_path):
    scan_db = tmp_path / "scan_history.csv"
    original = b'"unterminated\n'
    scan_db.write_bytes(original)

    result = append_scan_history(scan_db, base_row())

    assert result == {
        "appended": False,
        "reason": "unreadable:ParserError",
        "rows": None,
    }
    assert scan_db.read_bytes() == original


def test_append_scan_history_initializes_an_empty_existing_file(tmp_path):
    scan_db = tmp_path / "scan_history.csv"
    scan_db.touch()

    result = append_scan_history(scan_db, base_row())
    stored = pd.read_csv(scan_db)

    assert result == {"appended": True, "reason": "new_sample", "rows": 1}
    assert stored["symbol"].tolist() == ["AAPL"]


def test_compact_scan_history_removes_adjacent_live_duplicates(tmp_path):
    scan_db = tmp_path / "scan_history.csv"
    rows = [
        base_row(ts="2026-06-10T14:00:00+00:00", signal="WAIT"),
        base_row(ts="2026-06-10T14:00:30+00:00", signal="WAIT"),
        base_row(ts="2026-06-10T14:01:00+00:00", signal="BUY"),
    ]
    pd.DataFrame(rows).to_csv(scan_db, index=False)

    result = compact_scan_history(scan_db)
    stored = pd.read_csv(scan_db)

    assert result["compacted"] is True
    assert result["removed_rows"] == 1
    assert stored["signal"].tolist() == ["WAIT", "BUY"]


def test_concurrent_appends_are_serialized_and_atomically_replaced(tmp_path):
    scan_db = tmp_path / "scan_history.csv"

    def append(index):
        return append_scan_history(
            scan_db,
            base_row(
                ts=f"2026-06-10T14:{index:02d}:00+00:00",
                symbol=f"S{index:02d}",
            ),
            max_rows=100,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(append, range(16)))

    stored = pd.read_csv(scan_db)
    assert all(result["appended"] is True for result in results)
    assert len(stored) == 16
    assert set(stored["symbol"]) == {f"S{index:02d}" for index in range(16)}
    assert scan_db.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".scan_history.csv.lock").stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".scan_history.csv.*.tmp"))
