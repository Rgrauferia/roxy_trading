from datetime import datetime, timezone

import pandas as pd

from alpaca_paper_practice import close_alpaca_paper_practice_journal
from crypto_paper_practice import close_crypto_paper_practice_journal
from paper_result_closer import close_paper_results_with_live_prices, open_paper_symbols


def test_close_functions_do_not_close_blocked_rows():
    alpaca = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "market": "stock",
                "status": "BLOCKED",
                "closed_outcome": "",
                "entry": 100.0,
                "stop": 98.0,
            }
        ]
    )
    crypto = pd.DataFrame(
        [
            {
                "symbol": "BTC/USD",
                "market": "crypto",
                "status": "BLOCKED",
                "closed_outcome": "",
                "entry": 100.0,
                "stop": 98.0,
            }
        ]
    )

    closed_alpaca = close_alpaca_paper_practice_journal(alpaca, price_lookup={"AAPL": 103.0})
    closed_crypto = close_crypto_paper_practice_journal(crypto, price_lookup={"BTC/USD": 103.0})

    assert closed_alpaca.iloc[0]["status"] == "BLOCKED"
    assert not closed_alpaca.iloc[0]["closed_outcome"]
    assert closed_crypto.iloc[0]["status"] == "BLOCKED"
    assert not closed_crypto.iloc[0]["closed_outcome"]


def test_open_paper_symbols_returns_only_closeable_open_tracks():
    journal = pd.DataFrame(
        [
            {"symbol": "AAPL", "market": "stock", "status": "READY_FOR_PAPER", "entry": 100, "stop": 98},
            {"symbol": "MSFT", "market": "stock", "status": "BLOCKED", "entry": 100, "stop": 98},
            {"symbol": "TSLA", "market": "stock", "status": "CLOSED_HIT_2", "closed_outcome": "HIT_2", "entry": 100, "stop": 98},
            {"symbol": "BTC/USD", "market": "crypto", "status": "READY_FOR_PAPER", "entry": 100, "stop": 98},
        ]
    )

    assert open_paper_symbols(journal, market="stock") == ["AAPL"]
    assert open_paper_symbols(journal, market="crypto") == ["BTC/USD"]


def test_close_paper_results_with_live_prices_updates_both_journals(tmp_path):
    alpaca_path = tmp_path / "alpaca.csv"
    crypto_path = tmp_path / "crypto.csv"
    report_path = tmp_path / "report.json"
    pd.DataFrame(
        [
            {
                "ts": "2026-06-16T00:00:00+00:00",
                "practice_id": "aapl",
                "symbol": "AAPL",
                "market": "stock",
                "strategy_family": "Pullback",
                "status": "READY_FOR_PAPER",
                "closed_outcome": "",
                "entry": 100.0,
                "stop": 98.0,
            },
            {
                "ts": "2026-06-16T00:00:00+00:00",
                "practice_id": "msft-blocked",
                "symbol": "MSFT",
                "market": "stock",
                "strategy_family": "Pullback",
                "status": "BLOCKED",
                "closed_outcome": "",
                "entry": 100.0,
                "stop": 98.0,
            },
        ]
    ).to_csv(alpaca_path, index=False)
    pd.DataFrame(
        [
            {
                "ts": "2026-06-16T00:00:00+00:00",
                "practice_id": "btc",
                "symbol": "BTC/USD",
                "market": "crypto",
                "strategy_family": "Breakout crypto",
                "timeframe": "1h",
                "status": "READY_FOR_PAPER",
                "closed_outcome": "",
                "entry": 100.0,
                "stop": 98.0,
            }
        ]
    ).to_csv(crypto_path, index=False)

    def fake_fetcher(symbol: str, market: str):
        prices = {"AAPL": 102.5, "BTC/USD": 97.5}
        return {
            "price": prices[symbol],
            "freshness": "LIVE",
            "source": "fake-live",
            "source_mode": "TEST",
            "price_timestamp": "2026-06-16T00:01:00+00:00",
        }

    report = close_paper_results_with_live_prices(
        alpaca_path=alpaca_path,
        crypto_path=crypto_path,
        report_path=report_path,
        fetcher=fake_fetcher,
        now=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    alpaca = pd.read_csv(alpaca_path)
    crypto = pd.read_csv(crypto_path)

    assert report["newly_closed_total"] == 2
    assert alpaca.loc[alpaca["symbol"] == "AAPL", "closed_outcome"].iloc[0] == "HIT_2"
    assert alpaca.loc[alpaca["symbol"] == "MSFT", "status"].iloc[0] == "BLOCKED"
    assert crypto.iloc[0]["closed_outcome"] == "STOP"
    assert report_path.exists()
    assert report_path.stat().st_mode & 0o777 == 0o600
    assert alpaca_path.stat().st_mode & 0o777 == 0o600
    assert crypto_path.stat().st_mode & 0o777 == 0o600
