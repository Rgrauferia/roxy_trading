import os

from tools.roxy_ai_watch import latest_live_scan_file


def test_latest_live_scan_file_uses_newest_market_route(tmp_path):
    older_both = tmp_path / "ma_live_strategy_both_20260611_120000.csv"
    newer_crypto = tmp_path / "ma_live_strategy_crypto_20260611_121000.csv"
    older_both.write_text("old")
    newer_crypto.write_text("new")
    os.utime(older_both, (100, 100))
    os.utime(newer_crypto, (200, 200))

    selected = latest_live_scan_file(directory=tmp_path)

    assert selected == str(newer_crypto)
