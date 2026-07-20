import pytest


def test_paper_trader_imports():
    # very small smoke test: ensure adapter imports and basic API exist
    from adapters.paper_trader import SimplePaperTrader

    pt = SimplePaperTrader("test-user", slippage_pct=0.0, fill_rate=1.0)
    assert hasattr(pt, "buy") and hasattr(pt, "sell")

import os
import tempfile
import shutil
import storage
from adapters.paper_trader import SimplePaperTrader


def test_paper_trader_buy_sell_flow():
    # use a temporary DB for isolation
    tmpdir = tempfile.mkdtemp(prefix="roxy_test_")
    try:
        dbpath = os.path.join(tmpdir, "roxy.db")
        # point storage to temp DB
        old_db = storage.DB_PATH
        storage.DB_PATH = dbpath
        storage.init_db(dbpath)

        user = "testuser"
        pt = SimplePaperTrader(user, starting_equity=10000.0, slippage_pct=0.0, fill_rate=1.0, random_seed=1)

        # initial account equity
        eq0 = storage.get_account_equity(user)
        assert float(eq0) == 10000.0

        # buy 10 @ 100
        pid = pt.buy("TEST", 10, 100.0)
        assert pid is not None

        # position should reflect 10 units
        pos = pt.get_position("TEST")
        assert abs(pos - 10.0) < 1e-6

        # sell 5 @ 110 -> pnl = (110 - 100) * 5 = 50
        pnl = pt.sell("TEST", 5, 110.0)
        assert abs(pnl - 50.0) < 1e-6

        # remaining position should be 5
        pos2 = pt.get_position("TEST")
        assert abs(pos2 - 5.0) < 1e-6

        # check simulated trades recorded
        trades = storage.get_simulated_trades(limit=10)
        assert len(trades) >= 2

        # check account equity updated by realized pnl
        eq1 = storage.get_account_equity(user)
        assert float(eq1) >= float(eq0)

    finally:
        # cleanup and restore
        storage.DB_PATH = old_db
        shutil.rmtree(tmpdir)


def test_paper_trader_rejects_phantom_close_even_with_force(tmp_path):
    old_db = storage.DB_PATH
    try:
        storage.DB_PATH = str(tmp_path / "paper.db")
        storage.init_db(storage.DB_PATH)
        trader = SimplePaperTrader("isolated-user", starting_equity=10000.0)
        trader.buy("aapl", 1, 100.0, force=True, price_source="test_fixture", price_ts="2026-07-19T12:00:00Z")

        with pytest.raises(RuntimeError, match="exceeds held qty"):
            trader.sell("AAPL", 2, 101.0, force=True)

        assert trader.get_position("AAPL") == 1.0
        trades = storage.get_simulated_trades(user="isolated-user")
        assert len(trades) == 1
        assert "price_source=test_fixture" in trades[0][7]
    finally:
        storage.DB_PATH = old_db


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"fill_rate": 0}, "fill_rate"),
        ({"fill_rate": 1.1}, "fill_rate"),
        ({"slippage_pct": -0.1}, "slippage_pct"),
    ],
)
def test_paper_trader_rejects_invalid_execution_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        SimplePaperTrader("invalid-config", **kwargs)
