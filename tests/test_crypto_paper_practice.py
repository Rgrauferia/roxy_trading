import pandas as pd

from crypto_paper_practice import (
    build_crypto_paper_practice_candidates,
    close_and_save_crypto_paper_practice_journal,
    close_crypto_paper_practice_journal,
    price_lookup_from_crypto_opportunities,
    record_crypto_paper_practice_candidates,
    score_crypto_paper_practice_journal,
    summarize_crypto_paper_practice,
    summarize_crypto_paper_practice_by_context,
)


def test_build_crypto_paper_practice_candidates_tracks_ready_crypto_setup():
    table = pd.DataFrame(
        [
            {
                "action": "ALERT",
                "symbol": "BTC/USD",
                "market": "crypto",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 100.0,
                "stop": 99.0,
                "target_pct": 0.02,
                "target_price": 102.0,
                "risk_pct": 0.01,
                "strategy_family": "Breakout crypto",
                "timeframe": "1h",
                "data_bucket": "Live real",
                "data_source": "BinanceUS ticker",
                "data_gate": "LIVE_PRICE_OK",
                "por_que": "15m entro en zona.",
            }
        ]
    )

    rows = build_crypto_paper_practice_candidates(table, account_equity=500.0, risk_pct=0.01)

    assert len(rows) == 1
    row = rows.iloc[0]
    assert row["status"] == "READY_FOR_PAPER"
    assert row["symbol"] == "BTC/USD"
    assert row["qty"] == 5.0
    assert row["target_2"] == 102.0
    assert row["target_5"] == 105.0
    assert row["target_10"] == 110.0
    assert row["risk_dollars"] == 5.0
    assert row["data_source"] == "BinanceUS ticker"
    assert row["timeframe"] == "1h"


def test_build_crypto_paper_practice_candidates_blocks_stock_and_watch():
    table = pd.DataFrame(
        [
            {
                "action": "WATCH",
                "symbol": "AAPL",
                "market": "stock",
                "signal": "WATCH",
                "decision": "WAIT",
                "entry": 100.0,
                "stop": 99.0,
                "risk_pct": 0.01,
            }
        ]
    )

    rows = build_crypto_paper_practice_candidates(table)

    assert rows.iloc[0]["status"] == "BLOCKED"
    assert "solo crypto" in rows.iloc[0]["reason"].lower()
    assert "buy/alert" in rows.iloc[0]["reason"].lower()


def test_record_crypto_paper_practice_candidates_dedupes(tmp_path, monkeypatch):
    candidates = build_crypto_paper_practice_candidates(
        pd.DataFrame(
            [
                {
                    "action": "ALERT",
                    "symbol": "ETH/USD",
                    "market": "crypto",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100.0,
                    "stop": 99.0,
                    "risk_pct": 0.01,
                }
            ]
        )
    )
    path = tmp_path / "crypto.csv"

    first = record_crypto_paper_practice_candidates(candidates, path=path)

    def fail_rewrite(*args, **kwargs):
        raise AssertionError("existing crypto journal should not be rewritten")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_rewrite)
    second = record_crypto_paper_practice_candidates(candidates, path=path)

    assert len(first) == 1
    assert len(second) == 1
    assert path.exists()


def test_score_and_summarize_crypto_paper_practice_targets_and_stop():
    journal = pd.DataFrame(
        [
            {
                "ts": "2026-06-15T12:00:00+00:00",
                "practice_id": "btc",
                "symbol": "BTC/USD",
                "market": "crypto",
                "strategy_family": "Breakout crypto",
                "timeframe": "1h",
                "data_bucket": "Live real",
                "data_source": "BinanceUS ticker",
                "data_gate": "LIVE_PRICE_OK",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 5,
                "entry": 100.0,
                "stop": 99.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 102.0,
                "risk_dollars": 5.0,
                "notional": 500.0,
                "rr_to_2pct": 2.0,
                "reason": "ok",
            },
            {
                "ts": "2026-06-15T12:00:00+00:00",
                "practice_id": "eth",
                "symbol": "ETH/USD",
                "market": "crypto",
                "strategy_family": "Breakout crypto",
                "timeframe": "15m",
                "data_bucket": "Live real",
                "data_source": "CoinGecko",
                "data_gate": "LIVE_PRICE_OK",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 5,
                "entry": 100.0,
                "stop": 99.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 102.0,
                "risk_dollars": 5.0,
                "notional": 500.0,
                "rr_to_2pct": 2.0,
                "reason": "ok",
            },
        ]
    )

    scored = score_crypto_paper_practice_journal(journal, price_lookup={"BTCUSD": 105.0, "ETH/USD": 98.5})
    summary = summarize_crypto_paper_practice(scored)
    context = summarize_crypto_paper_practice_by_context(scored)

    by_symbol = {row["symbol"]: row for row in scored.to_dict("records")}
    assert by_symbol["BTC/USD"]["outcome"] == "HIT_5"
    assert by_symbol["ETH/USD"]["outcome"] == "STOP"
    assert summary.iloc[0]["tracked"] == 2
    assert summary.iloc[0]["hit_2_rate"] == 0.5
    assert summary.iloc[0]["stop_rate"] == 0.5
    by_symbol = {row["symbol"]: row for row in context.to_dict("records")}
    assert by_symbol["BTC/USD"]["timeframe"] == "1h"
    assert by_symbol["BTC/USD"]["last_price"] == 105.0


def test_close_crypto_paper_practice_journal_persists_hit_and_stop_outcomes():
    journal = pd.DataFrame(
        [
            {
                "ts": "2026-06-15T12:00:00+00:00",
                "practice_id": "btc",
                "symbol": "BTC/USD",
                "market": "crypto",
                "strategy_family": "Breakout crypto",
                "timeframe": "1h",
                "data_bucket": "Live real",
                "data_source": "BinanceUS ticker",
                "data_gate": "LIVE_PRICE_OK",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 5,
                "entry": 100.0,
                "stop": 99.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 102.0,
                "risk_dollars": 5.0,
                "notional": 500.0,
                "rr_to_2pct": 2.0,
                "reason": "ok",
            },
            {
                "ts": "2026-06-15T12:00:00+00:00",
                "practice_id": "eth",
                "symbol": "ETH/USD",
                "market": "crypto",
                "strategy_family": "Breakout crypto",
                "timeframe": "15m",
                "data_bucket": "Live real",
                "data_source": "CoinGecko",
                "data_gate": "LIVE_PRICE_OK",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 5,
                "entry": 100.0,
                "stop": 99.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 102.0,
                "risk_dollars": 5.0,
                "notional": 500.0,
                "rr_to_2pct": 2.0,
                "reason": "ok",
            },
        ]
    )

    closed = close_crypto_paper_practice_journal(journal, price_lookup={"BTC/USD": 102.5, "ETH/USD": 98.5})
    scored_again = score_crypto_paper_practice_journal(closed)
    by_symbol = {row["symbol"]: row for row in closed.to_dict("records")}
    rescored = {row["symbol"]: row for row in scored_again.to_dict("records")}

    assert by_symbol["BTC/USD"]["status"] == "CLOSED_HIT_2"
    assert by_symbol["BTC/USD"]["closed_outcome"] == "HIT_2"
    assert by_symbol["BTC/USD"]["closed_price"] == 102.5
    assert by_symbol["ETH/USD"]["status"] == "CLOSED_STOP"
    assert by_symbol["ETH/USD"]["closed_outcome"] == "STOP"
    assert rescored["BTC/USD"]["outcome"] == "HIT_2"
    assert rescored["ETH/USD"]["outcome"] == "STOP"


def test_close_and_save_crypto_paper_practice_journal_updates_file(tmp_path):
    candidates = build_crypto_paper_practice_candidates(
        pd.DataFrame(
            [
                {
                    "action": "ALERT",
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100.0,
                    "stop": 99.0,
                    "risk_pct": 0.01,
                }
            ]
        )
    )
    path = tmp_path / "crypto.csv"
    record_crypto_paper_practice_candidates(candidates, path=path)

    closed = close_and_save_crypto_paper_practice_journal(price_lookup={"BTC/USD": 103.0}, path=path)
    reloaded = pd.read_csv(path)

    assert closed.iloc[0]["status"] == "CLOSED_HIT_2"
    assert reloaded.iloc[0]["closed_outcome"] == "HIT_2"


def test_price_lookup_from_crypto_opportunities_keeps_slash_and_plain_symbol_keys():
    lookup = price_lookup_from_crypto_opportunities(
        pd.DataFrame(
            [
                {"symbol": "BTC/USD", "market": "crypto", "current_price": 105.0},
                {"symbol": "AAPL", "market": "stock", "current_price": 200.0},
            ]
        )
    )

    assert lookup == {"BTC/USD": 105.0, "BTCUSD": 105.0}
