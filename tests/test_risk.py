import os
import tempfile

import storage
from tools.risk import RiskManager
from adapters.paper_trader import SimplePaperTrader
from tools import audit


def setup_temp_db():
    td = tempfile.TemporaryDirectory()
    dbpath = os.path.join(td.name, "roxy.db")
    storage.init_db(dbpath)
    storage.DB_PATH = dbpath
    return td, dbpath


def test_buy_within_limits_records_execution():
    td, db = setup_temp_db()
    try:
        user = "tester"
        pt = SimplePaperTrader(user, starting_equity=10000.0)
        # default risk: max position 10% => $1000 max single position
        pid = pt.buy("TEST", qty=5, price=100.0, confidence=0.9)
        assert isinstance(pid, int)
        rows = audit.list_audit(limit=10, path=db)
        actions = [r[4] for r in rows]
        assert "executed" in actions or any(a == "executed" for a in actions)
    finally:
        td.cleanup()


def test_buy_exceeds_single_position_rejected():
    td, db = setup_temp_db()
    try:
        user = "tester2"
        pt = SimplePaperTrader(user, starting_equity=10000.0)
        # attempt to buy $5000 which exceeds default 10% max position
        try:
            pt.buy("BIG", qty=50, price=100.0, confidence=0.95)
            raised = False
        except RuntimeError as e:
            raised = True
            assert "exceeds max position" in str(e)
        assert raised
        rows = audit.list_audit(limit=10, path=db)
        # should include a rejected pre_check and rejected entry
        acts = [r[4] for r in rows]
        assert "rejected" in acts or any(a == "rejected" for a in acts)
    finally:
        td.cleanup()


def test_confidence_blocks_and_force_overrides():
    td, db = setup_temp_db()
    try:
        user = "tester3"
        pt = SimplePaperTrader(user, starting_equity=10000.0)
        # confidence below default 0.6 should block
        try:
            pt.buy("LOWC", qty=1, price=10.0, confidence=0.5)
            blocked = False
        except RuntimeError:
            blocked = True
        assert blocked
        # force should override
        pid = pt.buy("LOWC", qty=1, price=10.0, confidence=0.5, force=True)
        assert isinstance(pid, int)
    finally:
        td.cleanup()


def test_sell_more_than_held_rejected():
    td, db = setup_temp_db()
    try:
        user = "tester4"
        pt = SimplePaperTrader(user, starting_equity=10000.0)
        # sell without positions should be rejected
        try:
            pt.sell("NOPOS", qty=1, price=10.0)
            raised = False
        except RuntimeError as e:
            raised = True
            assert "exceeds held qty" in str(e) or "not allowed" in str(e)
        assert raised
    finally:
        td.cleanup()
import os

import storage
from tools.risk import RiskManager
from adapters.paper_trader import SimplePaperTrader
from tools import audit


def setup_tmp_db(tmp_path):
    db = str(tmp_path / "roxy_test.db")
    # ensure directory
    os.makedirs(os.path.dirname(db), exist_ok=True)
    # point global DB_PATH to the test DB so modules use it
    storage.DB_PATH = db
    storage.init_db(db)
    return db


def test_risk_basic(tmp_path):
    db = setup_tmp_db(tmp_path)
    user = "tester"
    storage.create_account_if_missing(user, starting_equity=10000.0, path=db)
    rm = RiskManager(max_position_pct=0.1, max_exposure_pct=0.3, min_confidence=0.6)
    ok, reason = rm.check_order(user, "AAPL", qty=1, price=500, side="BUY", confidence=0.7)
    assert ok
    # exceeds single position (1 share * 500 = 500 > 10000*0.1 = 1000?) -> actually allowed
    ok2, reason2 = rm.check_order(user, "AAPL", qty=3, price=500, side="BUY", confidence=0.7)
    assert not ok2


def test_confidence_block(tmp_path):
    db = setup_tmp_db(tmp_path)
    user = "tester2"
    storage.create_account_if_missing(user, 10000.0, path=db)
    rm = RiskManager(min_confidence=0.8)
    ok, reason = rm.check_order(user, "AAPL", qty=1, price=100, side="BUY", confidence=0.7)
    assert not ok and "confidence" in (reason or "")


def test_sell_block(tmp_path):
    db = setup_tmp_db(tmp_path)
    user = "tester3"
    storage.create_account_if_missing(user, 10000.0, path=db)
    # open position 1 share
    storage.open_sim_position(user, "AAPL", qty=1, entry_price=100, path=db)
    rm = RiskManager()
    ok, reason = rm.check_order(user, "AAPL", qty=2, price=110, side="SELL")
    assert not ok


def test_paper_trader_audit(tmp_path):
    db = setup_tmp_db(tmp_path)
    user = "trader1"
    storage.create_account_if_missing(user, 10000.0, path=db)
    pt = SimplePaperTrader(user, starting_equity=10000.0, slippage_pct=0.0, fill_rate=1.0, random_seed=1)
    # successful buy
    pid = pt.buy("AAPL", qty=1, price=100.0, confidence=0.9)
    rows = audit.list_audit(limit=20)
    kinds = [r[4] for r in rows]
    assert "executed" in kinds or any(r[4] == "executed" for r in rows)
import os
import pytest

import storage


def setup_test_db(tmp_path):
    dbp = tmp_path / "roxy_test.db"
    # point storage module to test db
    storage.DB_PATH = str(dbp)
    storage.init_db(storage.DB_PATH)
    return str(dbp)


def test_riskmanager_allows_small_order(tmp_path):
    from tools.risk import RiskManager

    db = setup_test_db(tmp_path)
    user = "test_user"
    storage.create_account_if_missing(user, starting_equity=10000.0, path=db)

    rm = RiskManager(max_position_pct=0.2, max_exposure_pct=0.5, min_confidence=0.5)
    ok, reason = rm.check_order(user, "AAPL", qty=1, price=100.0, side="BUY", confidence=0.9)
    assert ok is True
    assert reason is None


def test_riskmanager_blocks_large_single_position(tmp_path):
    from tools.risk import RiskManager

    db = setup_test_db(tmp_path)
    user = "big_pos"
    storage.create_account_if_missing(user, starting_equity=10000.0, path=db)

    # set very small max position to trigger block
    rm = RiskManager(max_position_pct=0.001, max_exposure_pct=0.5, min_confidence=0.0)
    ok, reason = rm.check_order(user, "TSLA", qty=10, price=100.0, side="BUY")
    assert ok is False
    assert "exceeds max position" in reason


def test_riskmanager_enforces_confidence(tmp_path):
    from tools.risk import RiskManager

    db = setup_test_db(tmp_path)
    user = "conf_user"
    storage.create_account_if_missing(user, starting_equity=10000.0, path=db)

    rm = RiskManager(min_confidence=0.7)
    ok, reason = rm.check_order(user, "AAPL", qty=1, price=50.0, side="BUY", confidence=0.6)
    assert ok is False
    assert "confidence" in reason


def test_simplepapertrader_respects_risk(tmp_path):
    from adapters.paper_trader import SimplePaperTrader

    db = setup_test_db(tmp_path)
    user = "pt_user"
    pt = SimplePaperTrader(user, starting_equity=10000.0, slippage_pct=0.0, fill_rate=1.0, random_seed=42)

    # default RiskManager blocks if order large; try force override
    with pytest.raises(RuntimeError):
        pt.buy("AMZN", qty=200.0, price=100.0)  # too large for default limits

    # force the buy
    pid = pt.buy("AMZN", qty=200.0, price=100.0, force=True)
    assert isinstance(pid, int)


def test_sell_prevents_shorting(tmp_path):
    from adapters.paper_trader import SimplePaperTrader

    db = setup_test_db(tmp_path)
    user = "seller"
    pt = SimplePaperTrader(user, starting_equity=10000.0)

    # selling without holdings should be blocked
    with pytest.raises(RuntimeError):
        pt.sell("NFLX", qty=1.0, price=100.0)
import os
import tempfile

from tools.risk import RiskManager
from adapters.paper_trader import SimplePaperTrader
import storage


def setup_temp_file_db():
    td = tempfile.NamedTemporaryFile(delete=False)
    td.close()
    path = td.name
    # initialize minimal schema expected by storage.ensure_tables if available
    # storage.ensure_tables() should create tables if missing; call with path
    try:
        storage.ensure_tables(path)
    except Exception:
        # best-effort; some environments may already have DB
        pass
    return path


def test_risk_manager_blocks_large_position():
    rm = RiskManager(max_position_pct=0.01, max_exposure_pct=0.5, min_confidence=0.0)
    user = "test_user_large_pos"
    db = setup_temp_file_db()
    storage.create_account_if_missing(user, starting_equity=10000.0, path=db)
    # order value 1000 > 1% of equity
    ok, reason = rm.check_order(user, "AAPL", qty=10, price=100.0, side="BUY", confidence=None)
    assert not ok
    assert "exceeds max position" in reason
    os.unlink(db)


def test_risk_manager_allows_small_position():
    rm = RiskManager(max_position_pct=0.2, max_exposure_pct=0.5, min_confidence=0.0)
    user = "test_user_small_pos"
    db = setup_temp_file_db()
    storage.create_account_if_missing(user, starting_equity=10000.0, path=db)
    ok, reason = rm.check_order(user, "AAPL", qty=1, price=100.0, side="BUY", confidence=None)
    assert ok
    assert reason is None
    os.unlink(db)


def test_paper_trader_enforces_risk():
    db = setup_temp_file_db()
    user = "trader_user"
    # start with small equity to make checks easier
    trader = SimplePaperTrader(user, starting_equity=1000.0, slippage_pct=0.0, fill_rate=1.0, random_seed=1)
    # try to buy a position larger than default 10% (default max_position_pct=0.1)
    try:
        trader.buy("MSFT", qty=100, price=10.0)
        # if no exception, fail
        assert False, "Expected risk check to raise"
    except RuntimeError as e:
        assert "Risk check failed" in str(e)
import os
import tempfile

import pytest

import storage
from tools.risk import RiskManager
from adapters.paper_trader import SimplePaperTrader


def setup_test_db(tmp_path):
    db_path = tmp_path / "roxy_test.db"
    storage.DB_PATH = str(db_path)
    storage.init_db(storage.DB_PATH)
    return storage.DB_PATH


def test_risk_confidence_and_position_limits(tmp_path):
    db = setup_test_db(tmp_path)
    user = "u_conf"
    storage.create_account_if_missing(user, starting_equity=10000.0)

    # confidence below threshold
    rm = RiskManager(min_confidence=0.8)
    ok, reason = rm.check_order(user, "AAPL", qty=1, price=100.0, side="BUY", confidence=0.5)
    assert not ok
    assert "confidence" in reason.lower()

    # order exceeding single-position limit
    rm = RiskManager(max_position_pct=0.05)
    ok, reason = rm.check_order(user, "AAPL", qty=10, price=100.0, side="BUY")
    assert not ok
    assert "exceeds max position" in reason.lower()

    # existing exposure + new order exceeds total exposure
    rm = RiskManager(max_exposure_pct=0.05)
    # create an existing position with exposure 300
    storage.open_sim_position(user, "AAPL", qty=3, entry_price=100.0)
    ok, reason = rm.check_order(user, "AAPL", qty=3, price=100.0, side="BUY")
    assert not ok
    assert "exceeds max exposure" in reason.lower()


def test_risk_sell_more_than_held(tmp_path):
    db = setup_test_db(tmp_path)
    user = "u_sell"
    storage.create_account_if_missing(user, starting_equity=5000.0)
    # open a single unit
    storage.open_sim_position(user, "TSLA", qty=1, entry_price=200.0)

    rm = RiskManager()
    ok, reason = rm.check_order(user, "TSLA", qty=2, price=210.0, side="SELL")
    assert not ok
    assert "exceeds held qty" in reason.lower() or "shorting" in reason.lower()


def test_paper_trader_enforces_risk(tmp_path):
    db = setup_test_db(tmp_path)
    user = "u_trader"
    pt = SimplePaperTrader(user, starting_equity=10000.0, slippage_pct=0.0, fill_rate=1.0)

    # default RiskManager uses 10% max position; try to buy too large
    with pytest.raises(RuntimeError):
        pt.buy("AMZN", qty=200, price=10.0)  # order value 2000 > 1000 (10%)

    # force should bypass risk
    pid = pt.buy("AMZN", qty=200, price=10.0, force=True)
    assert isinstance(pid, int)
