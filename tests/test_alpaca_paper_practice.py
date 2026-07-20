from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from alpaca_paper_practice import (
    build_alpaca_paper_practice_candidates,
    close_and_save_alpaca_paper_practice_journal,
    close_alpaca_paper_practice_journal,
    price_lookup_from_alpaca_opportunities,
    price_lookup_from_alpaca_snapshot,
    record_alpaca_paper_practice_candidates,
    score_alpaca_paper_practice_journal,
    summarize_alpaca_paper_practice,
    summarize_alpaca_paper_practice_by_data_source,
    summarize_alpaca_paper_practice_by_strategy_source,
)


def test_build_alpaca_paper_practice_candidates_tracks_ready_stock_setup():
    table = pd.DataFrame(
        [
            {
                "action": "ALERT",
                "symbol": "AAPL",
                "market": "stock",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 200.0,
                "stop": 198.0,
                "target_pct": 0.05,
                "target_price": 210.0,
                "risk_pct": 0.01,
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "data_gate": "LIVE_PRICE_OK",
                "por_que": "1h confirma y 15m da entrada.",
            }
        ]
    )

    rows = build_alpaca_paper_practice_candidates(table, account_equity=500.0, risk_pct=0.01)

    assert len(rows) == 1
    row = rows.iloc[0]
    assert row["data_bucket"] == "Live real"
    assert row["data_source"] == "Alpaca IEX"
    assert row["data_gate"] == "LIVE_PRICE_OK"
    assert row["status"] == "READY_FOR_PAPER"
    assert row["symbol"] == "AAPL"
    assert row["qty"] == 2
    assert row["target_2"] == 204.0
    assert row["target_5"] == 210.0
    assert row["target_10"] == 220.0
    assert row["risk_dollars"] == 4.0
    assert row["strategy_family"] == "Pullback"
    assert len(row["practice_id"]) == 16


def test_build_alpaca_paper_practice_candidates_blocks_crypto_and_watch():
    table = pd.DataFrame(
        [
            {
                "action": "WATCH",
                "symbol": "BTC/USD",
                "market": "crypto",
                "signal": "WATCH",
                "decision": "WAIT",
                "entry": 60000.0,
                "stop": 59000.0,
                "target_pct": 0.03,
                "risk_pct": 0.01,
                "strategy_family": "Canal alcista",
            }
        ]
    )

    rows = build_alpaca_paper_practice_candidates(table)

    assert rows.iloc[0]["status"] == "BLOCKED"
    assert "solo acciones" in rows.iloc[0]["reason"].lower()
    assert "buy/alert" in rows.iloc[0]["reason"].lower()


def test_record_alpaca_paper_practice_candidates_dedupes_by_practice_id(tmp_path, monkeypatch):
    table = pd.DataFrame(
        [
            {
                "action": "ALERT",
                "symbol": "MSFT",
                "market": "stock",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "entry": 100.0,
                "stop": 99.0,
                "target_pct": 0.02,
                "risk_pct": 0.01,
                "strategy_family": "Cruce de medias",
            }
        ]
    )
    candidates = build_alpaca_paper_practice_candidates(table)
    path = tmp_path / "practice.csv"

    first = record_alpaca_paper_practice_candidates(candidates, path=path)

    def fail_rewrite(*args, **kwargs):
        raise AssertionError("existing practice journal should not be rewritten")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_rewrite)
    second = record_alpaca_paper_practice_candidates(candidates, path=path)

    assert len(first) == 1
    assert len(second) == 1
    assert path.exists()


def test_concurrent_alpaca_records_do_not_lose_candidates(tmp_path):
    path = tmp_path / "practice.csv"

    def record(index):
        candidates = build_alpaca_paper_practice_candidates(
            pd.DataFrame(
                [{
                    "action": "ALERT",
                    "symbol": f"S{index:02d}",
                    "market": "stock",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100.0 + index,
                    "stop": 99.0 + index,
                    "target_pct": 0.02,
                    "risk_pct": 0.01,
                }]
            )
        )
        record_alpaca_paper_practice_candidates(candidates, path=path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record, range(16)))

    stored = pd.read_csv(path)
    assert set(stored["symbol"]) == {f"S{index:02d}" for index in range(16)}
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".practice.csv.lock").stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".practice.csv.*.tmp"))


def test_alpaca_record_preserves_unreadable_journal(tmp_path):
    path = tmp_path / "practice.csv"
    original = b'"unterminated\n'
    path.write_bytes(original)
    candidates = build_alpaca_paper_practice_candidates(
        pd.DataFrame([{"action": "ALERT", "symbol": "AAPL", "entry": 100, "stop": 99}])
    )

    with pytest.raises(pd.errors.ParserError):
        record_alpaca_paper_practice_candidates(candidates, path=path)

    assert path.read_bytes() == original


def test_score_and_summarize_alpaca_paper_practice_targets_and_stop():
    journal = pd.DataFrame(
        [
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "a",
                "symbol": "AAPL",
                "market": "stock",
                "strategy_family": "Pullback",
                "signal": "BUY",
                "decision": "TRADE_FOR_5PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 2,
                "entry": 100.0,
                "stop": 97.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 105.0,
                "risk_dollars": 6.0,
                "notional": 200.0,
                "rr_to_2pct": 0.6667,
                "reason": "ok",
            },
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "b",
                "symbol": "TSLA",
                "market": "stock",
                "strategy_family": "Canal bajista",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 1,
                "entry": 200.0,
                "stop": 196.0,
                "target_2": 204.0,
                "target_5": 210.0,
                "target_10": 220.0,
                "take_profit": 204.0,
                "risk_dollars": 4.0,
                "notional": 200.0,
                "rr_to_2pct": 1.0,
                "reason": "ok",
            },
        ]
    )

    scored = score_alpaca_paper_practice_journal(journal, price_lookup={"AAPL": 106.0, "TSLA": 195.0})
    summary = summarize_alpaca_paper_practice(scored)

    by_symbol = {row["symbol"]: row for row in scored.to_dict("records")}
    assert by_symbol["AAPL"]["outcome"] == "HIT_5"
    assert by_symbol["AAPL"]["hit_2pct"] is True
    assert by_symbol["TSLA"]["outcome"] == "STOP"
    by_strategy = {row["strategy_family"]: row for row in summary.to_dict("records")}
    assert by_strategy["Pullback"]["hit_2_rate"] == 1.0
    assert by_strategy["Canal bajista"]["stop_rate"] == 1.0


def test_close_alpaca_paper_practice_journal_persists_hit_and_stop_outcomes():
    journal = pd.DataFrame(
        [
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "hit",
                "symbol": "AAPL",
                "market": "stock",
                "strategy_family": "Pullback",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 2,
                "entry": 100.0,
                "stop": 97.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 102.0,
                "risk_dollars": 6.0,
                "notional": 200.0,
                "rr_to_2pct": 0.6667,
                "reason": "ok",
            },
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "stop",
                "symbol": "MSFT",
                "market": "stock",
                "strategy_family": "Breakout",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 1,
                "entry": 200.0,
                "stop": 196.0,
                "target_2": 204.0,
                "target_5": 210.0,
                "target_10": 220.0,
                "take_profit": 204.0,
                "risk_dollars": 4.0,
                "notional": 200.0,
                "rr_to_2pct": 1.0,
                "reason": "ok",
            },
        ]
    )

    closed = close_alpaca_paper_practice_journal(journal, price_lookup={"AAPL": 102.5, "MSFT": 195.0})
    scored_again = score_alpaca_paper_practice_journal(closed)

    by_symbol = {row["symbol"]: row for row in closed.to_dict("records")}
    rescored = {row["symbol"]: row for row in scored_again.to_dict("records")}
    assert by_symbol["AAPL"]["status"] == "CLOSED_HIT_2"
    assert by_symbol["AAPL"]["closed_outcome"] == "HIT_2"
    assert by_symbol["MSFT"]["status"] == "CLOSED_STOP"
    assert by_symbol["MSFT"]["closed_outcome"] == "STOP"
    assert rescored["AAPL"]["outcome"] == "HIT_2"
    assert rescored["MSFT"]["outcome"] == "STOP"


def test_close_and_save_alpaca_paper_practice_journal_updates_file(tmp_path):
    candidates = build_alpaca_paper_practice_candidates(
        pd.DataFrame(
            [
                {
                    "action": "ALERT",
                    "symbol": "AAPL",
                    "market": "stock",
                    "signal": "BUY",
                    "decision": "TRADE_FOR_2PCT",
                    "entry": 100.0,
                    "stop": 97.0,
                    "target_pct": 0.02,
                    "risk_pct": 0.01,
                    "strategy_family": "Pullback",
                }
            ]
        )
    )
    path = tmp_path / "alpaca_practice.csv"
    record_alpaca_paper_practice_candidates(candidates, path=path)

    closed = close_and_save_alpaca_paper_practice_journal(price_lookup={"AAPL": 103.0}, path=path)
    reloaded = pd.read_csv(path)

    assert closed.iloc[0]["status"] == "CLOSED_HIT_2"
    assert reloaded.iloc[0]["closed_outcome"] == "HIT_2"


def test_summarize_alpaca_paper_practice_by_data_source_tracks_live_vs_fallback():
    journal = pd.DataFrame(
        [
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "live",
                "symbol": "AAPL",
                "market": "stock",
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "data_gate": "LIVE_PRICE_OK",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 2,
                "entry": 100.0,
                "stop": 97.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 102.0,
                "risk_dollars": 6.0,
                "notional": 200.0,
                "rr_to_2pct": 0.6667,
                "reason": "ok",
            },
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "fallback",
                "symbol": "MSFT",
                "market": "stock",
                "strategy_family": "Pullback",
                "data_bucket": "Fallback",
                "data_source": "yfinance 1m",
                "data_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 1,
                "entry": 200.0,
                "stop": 196.0,
                "target_2": 204.0,
                "target_5": 210.0,
                "target_10": 220.0,
                "take_profit": 204.0,
                "risk_dollars": 4.0,
                "notional": 200.0,
                "rr_to_2pct": 1.0,
                "reason": "ok",
            },
        ]
    )

    scored = score_alpaca_paper_practice_journal(journal, price_lookup={"AAPL": 103.0, "MSFT": 195.0})
    summary = summarize_alpaca_paper_practice_by_data_source(scored)

    by_bucket = {row["data_bucket"]: row for row in summary.to_dict("records")}
    assert by_bucket["Live real"]["hit_2_rate"] == 1.0
    assert by_bucket["Live real"]["stop_rate"] == 0.0
    assert by_bucket["Live real"]["tone"] == "buy"
    assert by_bucket["Fallback"]["hit_2_rate"] == 0.0
    assert by_bucket["Fallback"]["stop_rate"] == 1.0
    assert by_bucket["Fallback"]["tone"] == "avoid"


def test_summarize_alpaca_paper_practice_by_strategy_source_tracks_combination():
    journal = pd.DataFrame(
        [
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "pullback-live",
                "symbol": "AAPL",
                "market": "stock",
                "strategy_family": "Pullback",
                "data_bucket": "Live real",
                "data_source": "Alpaca IEX",
                "data_gate": "LIVE_PRICE_OK",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 2,
                "entry": 100.0,
                "stop": 97.0,
                "target_2": 102.0,
                "target_5": 105.0,
                "target_10": 110.0,
                "take_profit": 102.0,
                "risk_dollars": 6.0,
                "notional": 200.0,
                "rr_to_2pct": 0.6667,
                "reason": "ok",
            },
            {
                "ts": "2026-06-11T12:00:00+00:00",
                "practice_id": "pullback-fallback",
                "symbol": "MSFT",
                "market": "stock",
                "strategy_family": "Pullback",
                "data_bucket": "Fallback",
                "data_source": "yfinance 1m",
                "data_gate": "NO_TRADE_FROM_PUBLIC_PRICE",
                "signal": "BUY",
                "decision": "TRADE_FOR_2PCT",
                "status": "READY_FOR_PAPER",
                "side": "buy",
                "qty": 1,
                "entry": 200.0,
                "stop": 196.0,
                "target_2": 204.0,
                "target_5": 210.0,
                "target_10": 220.0,
                "take_profit": 204.0,
                "risk_dollars": 4.0,
                "notional": 200.0,
                "rr_to_2pct": 1.0,
                "reason": "ok",
            },
        ]
    )

    scored = score_alpaca_paper_practice_journal(journal, price_lookup={"AAPL": 103.0, "MSFT": 195.0})
    summary = summarize_alpaca_paper_practice_by_strategy_source(scored)

    by_combo = {
        (row["strategy_family"], row["data_bucket"], row["data_source"]): row
        for row in summary.to_dict("records")
    }
    assert by_combo[("Pullback", "Live real", "Alpaca IEX")]["hit_2_rate"] == 1.0
    assert by_combo[("Pullback", "Live real", "Alpaca IEX")]["tone"] == "buy"
    assert by_combo[("Pullback", "Fallback", "yfinance 1m")]["stop_rate"] == 1.0
    assert by_combo[("Pullback", "Fallback", "yfinance 1m")]["tone"] == "avoid"


def test_price_lookup_from_alpaca_snapshot_uses_open_positions_current_price():
    snapshot = {"positions": [{"symbol": "AAPL", "current": 205.25}, {"symbol": "MSFT", "current_price": "300.50"}]}

    assert price_lookup_from_alpaca_snapshot(snapshot) == {"AAPL": 205.25, "MSFT": 300.5}


def test_price_lookup_from_alpaca_opportunities_uses_stock_prices_only():
    rows = pd.DataFrame(
        [
            {"symbol": "AAPL", "market": "stock", "current_price": 205.25},
            {"symbol": "SPY", "market": "etf", "latest_price": "530.50"},
            {"symbol": "BTC/USD", "market": "crypto", "current_price": 65000.0},
        ]
    )

    assert price_lookup_from_alpaca_opportunities(rows) == {"AAPL": 205.25, "SPY": 530.5}
