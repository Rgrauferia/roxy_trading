import os
import tempfile
import sqlite3

from storage import (
    init_db,
    create_account_if_missing,
    get_account_equity,
    open_sim_position,
    close_sim_position_by_symbol,
    snapshot_account_point,
    get_equity_series,
)


def test_account_snapshot_flow(tmp_path):
    dbp = tmp_path / "test_roxy.db"
    init_db(str(dbp))
    user = "tester"
    create_account_if_missing(user, starting_equity=1000.0, path=str(dbp))
    assert get_account_equity(user, path=str(dbp)) == 1000.0

    # open a position on a symbol that has OHLCV
    # insert a last price into ohlcv
    conn = sqlite3.connect(str(dbp))
    cur = conn.cursor()
    cur.execute("INSERT INTO ohlcv (symbol, ts, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)", ("FOO", "2025-01-01T00:00:00", 10, 10, 10, 10, 1))
    conn.commit()
    conn.close()

    pid = open_sim_position(user, "FOO", 2, 9.0, path=str(dbp))
    assert pid is not None

    # snapshot should compute unrealized (last 10 - entry 9) * qty 2 = 2.0
    eq = snapshot_account_point(user, path=str(dbp))
    assert abs(eq - 1002.0) < 1e-6

    # close and ensure realized P&L applied
    pnl = close_sim_position_by_symbol(user, "FOO", 2, 10.0, path=str(dbp))
    assert abs(pnl - 2.0) < 1e-6
    # after close, account equity should include realized pnl
    acct = get_account_equity(user, path=str(dbp))
    assert abs(acct - 1002.0) < 1e-6

    # there should be at least two equity points (initial + snapshot)
    pts = get_equity_series(user, path=str(dbp))
    assert len(pts) >= 2
