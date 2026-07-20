from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from durable_storage import atomic_write_csv, atomic_write_text, exclusive_file_lock


def test_atomic_writers_replace_content_privately_without_residue(tmp_path):
    csv_path = tmp_path / "snapshot.csv"
    text_path = tmp_path / "snapshot.json"

    atomic_write_csv(pd.DataFrame([{"symbol": "AAPL", "price": 200.0}]), csv_path)
    atomic_write_text('{"status":"OK"}', text_path)

    assert pd.read_csv(csv_path).to_dict("records") == [{"symbol": "AAPL", "price": 200.0}]
    assert text_path.read_text() == '{"status":"OK"}'
    assert csv_path.stat().st_mode & 0o777 == 0o600
    assert text_path.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_csv_failure_preserves_previous_complete_version(tmp_path, monkeypatch):
    target = tmp_path / "snapshot.csv"
    original = b"symbol,price\nAAPL,200\n"
    target.write_bytes(original)

    def fail_write(*args, **kwargs):
        raise RuntimeError("simulated serialization failure")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_write)
    with pytest.raises(RuntimeError, match="serialization failure"):
        atomic_write_csv(pd.DataFrame([{"symbol": "MSFT", "price": 500.0}]), target)

    assert target.read_bytes() == original
    assert not list(tmp_path.glob(".snapshot.csv.*.tmp"))


def test_exclusive_file_lock_serializes_read_modify_write(tmp_path):
    target = tmp_path / "counter.txt"
    atomic_write_text("0", target)

    def increment(_):
        with exclusive_file_lock(target):
            value = int(target.read_text())
            atomic_write_text(str(value + 1), target)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(increment, range(32)))

    assert target.read_text() == "32"
    assert (tmp_path / ".counter.txt.lock").stat().st_mode & 0o777 == 0o600
