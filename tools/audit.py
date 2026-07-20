"""Execution audit helpers for observability and compliance.

Provides a small abstraction to persist structured execution/audit
events into the local SQLite DB so they can be queried by UIs or
exported to observability pipelines.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import storage
from roxy_time import utc_now_naive_iso


def _connect(path: Optional[str] = None):
    p = path or storage.DB_PATH
    return sqlite3.connect(p, check_same_thread=False)


def ensure_table(path: Optional[str] = None) -> None:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            actor TEXT,
            strategy TEXT,
            action TEXT,
            symbol TEXT,
            qty REAL,
            price REAL,
            side TEXT,
            confidence REAL,
            risk_allowed INTEGER,
            risk_reason TEXT,
            note TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_execution(
    actor: str | None,
    strategy: str | None,
    action: str,
    symbol: str | None = None,
    qty: float | None = None,
    price: float | None = None,
    side: str | None = None,
    confidence: float | None = None,
    risk_allowed: bool | None = None,
    risk_reason: str | None = None,
    note: str | None = None,
    path: Optional[str] = None,
) -> int:
    """Insert a single execution audit row and return its id."""
    ensure_table(path=path)
    conn = _connect(path)
    cur = conn.cursor()
    ts = utc_now_naive_iso()
    cur.execute(
        """
        INSERT INTO execution_audit (
            ts, actor, strategy, action, symbol, qty, price, side, confidence, risk_allowed, risk_reason, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            actor or "",
            strategy or "",
            action,
            symbol or "",
            float(qty) if qty is not None else None,
            float(price) if price is not None else None,
            side or "",
            float(confidence) if confidence is not None else None,
            1 if risk_allowed else 0 if risk_allowed is not None else None,
            risk_reason or "",
            note or "",
        ),
    )
    conn.commit()
    last = cur.lastrowid
    conn.close()
    return last


def list_audit(limit: int = 100, path: Optional[str] = None):
    ensure_table(path=path)
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT id, ts, actor, strategy, action, symbol, qty, price, side, confidence, risk_allowed, risk_reason, note FROM execution_audit ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


__all__ = ["ensure_table", "log_execution", "list_audit"]
