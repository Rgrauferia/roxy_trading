from pathlib import Path

import pytest

from execution import PaperTrader


def test_backtest_trader_is_memory_only_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    trader = PaperTrader()
    trader.buy("aapl", 1, 100)
    trader.sell("AAPL", 1, 101)

    assert trader.get_position("AAPL") == 0
    assert len(trader.records) == 2
    assert not (tmp_path / "db" / "trades.csv").exists()


def test_backtest_trader_requires_explicit_absolute_audit_path(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        PaperTrader(audit_path="db/trades.csv")

    audit_path = tmp_path / "isolated" / "trades.csv"
    trader = PaperTrader(audit_path=audit_path)
    trader.buy("TEST", 2, 10)

    assert audit_path.exists()
    assert "TEST,BUY,2.0,10.0" in audit_path.read_text(encoding="utf-8")


def test_backtest_trader_rejects_implicit_short():
    trader = PaperTrader()
    with pytest.raises(ValueError, match="exceeds held qty"):
        trader.sell("TEST", 1, 10)
