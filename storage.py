"""Lightweight SQLite persistence for OHLCV, scans and summaries.

This module provides simple functions to initialize a local `db/roxy.db`
and save scan summaries and individual scan rows. It's intentionally
minimal to avoid adding heavy dependencies.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join("db", "roxy.db")
os.makedirs("db", exist_ok=True)


def init_db(path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY,
            ts TEXT,
            summary_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY,
            ts TEXT,
            market TEXT,
            symbol TEXT,
            tf TEXT,
            score REAL,
            signal TEXT,
            entry REAL,
            stop REAL,
            tp1 REAL,
            tp2 REAL,
            rr_tp1 REAL,
            rr_tp2 REAL,
            rank_score REAL,
            reasons TEXT,
            raw_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT,
            ts TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY(symbol, ts)
        )
        """
    )
    # backtest runs
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS backtests (
            id INTEGER PRIMARY KEY,
            name TEXT,
            ts TEXT,
            metrics_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS equity_points (
            id INTEGER PRIMARY KEY,
            backtest_id INTEGER,
            step INTEGER,
            equity REAL,
            FOREIGN KEY(backtest_id) REFERENCES backtests(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sim_trades (
            id INTEGER PRIMARY KEY,
            ts TEXT,
            user TEXT,
            symbol TEXT,
            side TEXT,
            qty REAL,
            price REAL,
            note TEXT
        )
        """
    )
    # open/closed simulated positions for P&L tracking
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sim_positions (
            id INTEGER PRIMARY KEY,
            ts_open TEXT,
            ts_close TEXT,
            user TEXT,
            symbol TEXT,
            qty REAL,
            entry_price REAL,
            close_price REAL,
            pnl REAL,
            note TEXT
        )
        """
    )
    # simple per-user simulated account and equity time-series
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sim_accounts (
            user TEXT PRIMARY KEY,
            created_ts TEXT,
            equity REAL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sim_account_points (
            id INTEGER PRIMARY KEY,
            user TEXT,
            ts TEXT,
            equity REAL
        )
        """
    )
    # user roles for RBAC (simple)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            user TEXT PRIMARY KEY,
            role TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS role_audit (
            id INTEGER PRIMARY KEY,
            actor TEXT,
            target_user TEXT,
            old_role TEXT,
            new_role TEXT,
            ts TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _connect(path: str | None = None):
    if path is None:
        path = DB_PATH
    init_db(path)
    return sqlite3.connect(path)


def save_summary(summary: dict, path: str | None = None) -> None:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    ts = summary.get("timestamp") or datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO summaries (ts, summary_json) VALUES (?, ?)", (ts, json.dumps(summary))
    )
    conn.commit()
    conn.close()


def save_backtest_result(name: str, metrics: dict, path: str | None = None) -> None:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    ts = metrics.get("timestamp") or datetime.utcnow().isoformat()
    cur.execute("INSERT INTO backtests (name, ts, metrics_json) VALUES (?, ?, ?)", (name, ts, json.dumps(metrics)))
    conn.commit()
    backtest_id = cur.lastrowid
    conn.close()
    return backtest_id


def save_equity_series(backtest_id: int, equity_curve: list[float], path: str | None = None) -> None:
    """Persist an equity time-series for a backtest as individual points.

    This makes it easier to query and plot large series without embedding big
    arrays inside the `backtests.metrics_json` blob.
    """
    if not equity_curve:
        return
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    rows = [(backtest_id, i, float(v)) for i, v in enumerate(equity_curve)]
    cur.executemany("INSERT INTO equity_points (backtest_id, step, equity) VALUES (?, ?, ?)", rows)
    conn.commit()
    conn.close()


def save_scan_df(df, market: Optional[str] = None, path: str | None = None) -> None:
    if df is None:
        return
    # pandas import not required here; we only check `.empty`
    if getattr(df, "empty", True):
        return
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    rows = []
    for _, r in df.iterrows():
        ts = datetime.utcnow().isoformat()
        symbol = r.get("symbol")
        tf = r.get("tf") or r.get("interval")
        score = r.get("score")
        signal = r.get("signal")
        entry = r.get("entry")
        stop = r.get("stop")
        tp1 = r.get("tp1")
        tp2 = r.get("tp2")
        rr_tp1 = r.get("rr_tp1")
        rr_tp2 = r.get("rr_tp2")
        rank = r.get("rank_score")
        reasons = r.get("reasons") or r.get("growth_reasons")
        rows.append(
            (
                ts,
                market,
                symbol,
                tf,
                score,
                signal,
                entry,
                stop,
                tp1,
                tp2,
                rr_tp1,
                rr_tp2,
                rank,
                json.dumps(reasons),
                json.dumps(r.dropna().to_dict()),
            )
        )

    sql = (
        "INSERT INTO scans (ts, market, symbol, tf, score, signal, entry, stop, "
        "tp1, tp2, rr_tp1, rr_tp2, rank_score, reasons, raw_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    cur.executemany(sql, rows)
    conn.commit()
    conn.close()


def save_simulated_trade(user: str, symbol: str, side: str, qty: float, price: float, note: str | None = None, path: str | None = None) -> int:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO sim_trades (ts, user, symbol, side, qty, price, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, user, symbol, side, qty, price, note or ""),
    )
    conn.commit()
    last = cur.lastrowid
    conn.close()
    return last


def open_sim_position(user: str, symbol: str, qty: float, entry_price: float, note: str | None = None, path: str | None = None) -> int:
    """Open a simulated position (record only)."""
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO sim_positions (ts_open, user, symbol, qty, entry_price, note) VALUES (?, ?, ?, ?, ?, ?)",
        (ts, user, symbol, qty, entry_price, note or ""),
    )
    conn.commit()
    last = cur.lastrowid
    conn.close()
    return last


def close_sim_position(position_id: int, close_price: float, path: str | None = None) -> float:
    """Close an open simulated position by id and return realized P&L."""
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    # fetch position
    cur.execute("SELECT qty, entry_price FROM sim_positions WHERE id = ? AND ts_close IS NULL", (position_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Position not found or already closed")
    qty, entry = row
    pnl = (float(close_price) - float(entry)) * float(qty)
    cur.execute("UPDATE sim_positions SET ts_close = ?, close_price = ?, pnl = ? WHERE id = ?", (ts, close_price, pnl, position_id))
    conn.commit()
    conn.close()
    return pnl


def close_sim_position_by_symbol(user: str, symbol: str, qty: float, close_price: float, path: str | None = None) -> float:
    """Close one or more positions for a user+symbol using LIFO until qty satisfied.

    Returns total realized P&L for the closed quantity.
    """
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    remaining = float(qty)
    total_pnl = 0.0
    # select open positions for user+symbol in descending id (LIFO)
    cur.execute("SELECT id, qty, entry_price FROM sim_positions WHERE user = ? AND symbol = ? AND ts_close IS NULL ORDER BY id DESC", (user, symbol))
    rows = cur.fetchall()
    for pid, pqty, entry in rows:
        if remaining <= 0:
            break
        take = min(remaining, pqty)
        pnl = (float(close_price) - float(entry)) * float(take)
        # if taking part of position, reduce qty and leave open
        if take < pqty:
            new_qty = float(pqty) - take
            cur.execute("UPDATE sim_positions SET qty = ? WHERE id = ?", (new_qty, pid))
            # insert a closed record for the taken portion
            ts = datetime.utcnow().isoformat()
            cur.execute("INSERT INTO sim_positions (ts_open, ts_close, user, symbol, qty, entry_price, close_price, pnl, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (ts, ts, user, symbol, take, entry, close_price, pnl, "partial-close"))
        else:
            # close entire row
            ts = datetime.utcnow().isoformat()
            cur.execute("UPDATE sim_positions SET ts_close = ?, close_price = ?, pnl = ? WHERE id = ?", (ts, close_price, pnl, pid))
        total_pnl += float(pnl)
        remaining -= take

    conn.commit()
    conn.close()
    if remaining > 0:
        raise ValueError("Not enough open quantity to close the requested amount")

    # update account equity with realized P&L if user has account
    try:
        update_account_equity(user, total_pnl, path=path)
    except Exception:
        # ignore if account not setup
        pass

    return total_pnl


def get_open_positions(user: str | None = None, path: str | None = None):
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    if user:
        cur.execute("SELECT id, ts_open, user, symbol, qty, entry_price, note FROM sim_positions WHERE ts_close IS NULL AND user = ? ORDER BY id DESC", (user,))
    else:
        cur.execute("SELECT id, ts_open, user, symbol, qty, entry_price, note FROM sim_positions WHERE ts_close IS NULL ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_position_history(user: str | None = None, limit: int = 100, path: str | None = None):
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    if user:
        cur.execute("SELECT id, ts_open, ts_close, user, symbol, qty, entry_price, close_price, pnl, note FROM sim_positions WHERE user = ? ORDER BY id DESC LIMIT ?", (user, limit))
    else:
        cur.execute("SELECT id, ts_open, ts_close, user, symbol, qty, entry_price, close_price, pnl, note FROM sim_positions ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def create_account_if_missing(user: str, starting_equity: float = 10000.0, path: str | None = None) -> None:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT equity FROM sim_accounts WHERE user = ?", (user,))
    if cur.fetchone() is None:
        ts = datetime.utcnow().isoformat()
        cur.execute("INSERT INTO sim_accounts (user, created_ts, equity) VALUES (?, ?, ?)", (user, ts, float(starting_equity)))
        cur.execute("INSERT INTO sim_account_points (user, ts, equity) VALUES (?, ?, ?)", (user, ts, float(starting_equity)))
        conn.commit()
    # ensure a role exists (default to 'user')
    cur.execute("SELECT role FROM user_roles WHERE user = ?", (user,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO user_roles (user, role) VALUES (?, ?)", (user, "user"))
        conn.commit()
    conn.close()


def set_user_role(user: str, role: str, actor: str | None = None, path: str | None = None) -> None:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    # fetch old role
    cur.execute("SELECT role FROM user_roles WHERE user = ?", (user,))
    row = cur.fetchone()
    old_role = row[0] if row else None
    cur.execute("INSERT OR REPLACE INTO user_roles (user, role) VALUES (?, ?)", (user, role))
    ts = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO role_audit (actor, target_user, old_role, new_role, ts) VALUES (?, ?, ?, ?, ?)", (actor or "system", user, old_role, role, ts))
    conn.commit()
    conn.close()
    # also append a human-readable audit line to logs/role_audit.log
    try:
        import os
        from pathlib import Path
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        logp = log_dir / "role_audit.log"
        ts = datetime.utcnow().isoformat()
        actor_f = actor or "system"
        # write via rotating logger when available
        try:
            from logging_config import get_audit_logger

            lg = get_audit_logger(str(logp))
            lg.info(f"{actor_f}\t{user}\t{old_role or 'NONE'}\t{role}")
        except Exception:
            with open(logp, "a", encoding="utf-8") as fh:
                fh.write(f"{ts}\t{actor_f}\t{user}\t{old_role or 'NONE'}\t{role}\n")
    except Exception:
        pass


def get_user_role(user: str, path: str | None = None) -> str:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT role FROM user_roles WHERE user = ?", (user,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "user"


def is_admin(user: str | None, path: str | None = None) -> bool:
    if not user:
        return False
    return get_user_role(user, path=path) == "admin"


def list_role_audit(limit: int = 100, path: str | None = None):
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT id, actor, target_user, old_role, new_role, ts FROM role_audit ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_account_equity(user: str, path: str | None = None) -> float:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT equity FROM sim_accounts WHERE user = ?", (user,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise ValueError("Account not found")
    return float(row[0])


def update_account_equity(user: str, delta: float, path: str | None = None) -> float:
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT equity FROM sim_accounts WHERE user = ?", (user,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Account not found")
    new_equity = float(row[0]) + float(delta)
    ts = datetime.utcnow().isoformat()
    cur.execute("UPDATE sim_accounts SET equity = ? WHERE user = ?", (new_equity, user))
    cur.execute("INSERT INTO sim_account_points (user, ts, equity) VALUES (?, ?, ?)", (user, ts, new_equity))
    conn.commit()
    conn.close()
    return new_equity


def get_equity_series(user: str, limit: int = 1000, path: str | None = None):
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT ts, equity FROM sim_account_points WHERE user = ? ORDER BY id ASC LIMIT ?", (user, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def list_accounts(path: str | None = None):
    """Return all accounts with their equity and created_ts."""
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT user, created_ts, equity FROM sim_accounts ORDER BY user ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_last_snapshot(user: str | None = None, path: str | None = None):
    """Return the latest snapshot ts (ISO string) for `user` or the most recent across all users if user is None."""
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    if user:
        cur.execute("SELECT ts, equity FROM sim_account_points WHERE user = ? ORDER BY id DESC LIMIT 1", (user,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    else:
        cur.execute("SELECT user, ts, equity FROM sim_account_points ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {"user": row[0], "ts": row[1], "equity": row[2]}


def get_snapshot_points(user: str | None = None, limit: int = 1000, path: str | None = None):
    """Return list of (user, ts, equity) snapshot points. If `user` is provided, filter by user."""
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    if user:
        cur.execute("SELECT ts, equity FROM sim_account_points WHERE user = ? ORDER BY id ASC LIMIT ?", (user, limit))
        rows = cur.fetchall()
        conn.close()
        return [(user, r[0], r[1]) for r in rows]
    else:
        cur.execute("SELECT user, ts, equity FROM sim_account_points ORDER BY id ASC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]


def snapshot_account_point(user: str, path: str | None = None) -> float:
    """Compute unrealized P&L for user's open positions using latest close prices,
    record a non-persistent snapshot point (does not change sim_accounts.equity),
    and return the computed equity value.
    """
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    # get base (realized) equity
    cur.execute("SELECT equity FROM sim_accounts WHERE user = ?", (user,))
    row = cur.fetchone()
    base_equity = float(row[0]) if row else 0.0

    # sum unrealized across open positions
    cur.execute("SELECT symbol, qty, entry_price FROM sim_positions WHERE user = ? AND ts_close IS NULL", (user,))
    rows = cur.fetchall()
    unreal = 0.0
    for symbol, qty, entry in rows:
        # find latest close for symbol
        cur2 = conn.cursor()
        cur2.execute("SELECT close FROM ohlcv WHERE symbol = ? ORDER BY ts DESC LIMIT 1", (symbol,))
        r2 = cur2.fetchone()
        last = float(r2[0]) if r2 else float(entry)
        unreal += (last - float(entry)) * float(qty)

    snapshot_equity = base_equity + float(unreal)
    ts = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO sim_account_points (user, ts, equity) VALUES (?, ?, ?)", (user, ts, snapshot_equity))
    conn.commit()
    conn.close()
    return snapshot_equity


def get_simulated_trades(limit: int = 100, path: str | None = None):
    if path is None:
        path = DB_PATH
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT id, ts, user, symbol, side, qty, price, note FROM sim_trades ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows
