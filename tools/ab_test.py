"""A/B testing (canary) framework for routing strategy executions.

This module allows creating named A/B tests with weighted variants,
assigning incoming signals/orders to a variant deterministically (by
user or key), routing execution through the paper trader under the
assigned variant, and persisting results for P&L comparison.

Design notes:
- Tables: `ab_tests`, `ab_variants`, `ab_assignments`, `ab_results`.
- Deterministic assignment uses a SHA256 hash of `test_name|key`.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import storage


DB_PATH = storage.DB_PATH


def _connect(path: Optional[str] = None):
    return sqlite3.connect(path or DB_PATH, check_same_thread=False)


def ensure_tables(path: Optional[str] = None) -> None:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ab_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            ts TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ab_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            name TEXT,
            weight REAL,
            ts TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ab_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            key TEXT,
            actor TEXT,
            variant TEXT,
            ts TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER,
            action TEXT,
            symbol TEXT,
            qty REAL,
            price REAL,
            side TEXT,
            result_type TEXT,
            result_value REAL,
            exec_audit_id INTEGER,
            note TEXT,
            ts TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def create_test(name: str, variants: Dict[str, float], description: Optional[str] = None, path: Optional[str] = None) -> int:
    """Create an A/B test and its variants. `variants` maps name->weight."""
    ensure_tables(path=path)
    conn = _connect(path)
    cur = conn.cursor()
    ts = _now_iso()
    cur.execute("INSERT OR IGNORE INTO ab_tests (name, description, ts) VALUES (?, ?, ?)", (name, description or "", ts))
    conn.commit()
    cur.execute("SELECT id FROM ab_tests WHERE name = ?", (name,))
    row = cur.fetchone()
    test_id = row[0]
    # delete existing variants for idempotent create
    cur.execute("DELETE FROM ab_variants WHERE test_id = ?", (test_id,))
    for vname, weight in variants.items():
        cur.execute("INSERT INTO ab_variants (test_id, name, weight, ts) VALUES (?, ?, ?, ?)", (test_id, vname, float(weight), ts))
    conn.commit()
    conn.close()
    return test_id


def list_tests(path: Optional[str] = None) -> List[Tuple]:
    ensure_tables(path=path)
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, ts FROM ab_tests ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def _load_variants(test_id: int, path: Optional[str] = None) -> List[Tuple[str, float]]:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT name, weight FROM ab_variants WHERE test_id = ?", (test_id,))
    rows = cur.fetchall()
    conn.close()
    return [(r[0], float(r[1])) for r in rows]


def _choose_weighted(variants: List[Tuple[str, float]], key: str) -> str:
    # deterministic choice by hashing key to [0,1)
    h = hashlib.sha256(key.encode("utf-8")).digest()
    # use first 8 bytes as uint64
    val = int.from_bytes(h[:8], "big") / float(2**64)
    total = sum(w for _, w in variants)
    if total <= 0:
        # fallback equal weights
        idx = int((val * len(variants)) % len(variants))
        return variants[idx][0]
    threshold = val * total
    cum = 0.0
    for name, weight in variants:
        cum += weight
        if threshold <= cum:
            return name
    return variants[-1][0]


def assign_variant(test_name: str, key: Optional[str] = None, actor: Optional[str] = None, path: Optional[str] = None) -> Tuple[int, str]:
    """Assign a variant for `test_name` using `key` (or actor) deterministically.

    Returns (assignment_id, variant_name).
    """
    ensure_tables(path=path)
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM ab_tests WHERE name = ?", (test_name,))
    row = cur.fetchone()
    if not row:
        raise ValueError("test not found")
    test_id = row[0]
    variants = _load_variants(test_id, path=path)
    if not variants:
        raise ValueError("no variants for test")
    assign_key = key or (actor or "")
    composed = f"{test_name}|{assign_key}"
    variant = _choose_weighted(variants, composed)
    ts = _now_iso()
    cur.execute("INSERT INTO ab_assignments (test_id, key, actor, variant, ts) VALUES (?, ?, ?, ?, ?)", (test_id, assign_key, actor or "", variant, ts))
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid, variant


def route_and_execute(
    test_name: str,
    actor: str,
    symbol: str,
    side: str,
    qty: float,
    price: float,
    confidence: Optional[float] = None,
    key: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict:
    """Assign variant and execute the order via `SimplePaperTrader`.

    Returns a dict with assignment/result metadata.
    """
    from adapters.paper_trader import SimplePaperTrader
    from tools import audit

    ensure_tables(path=path)
    # assign
    aid, variant = assign_variant(test_name, key=key or actor, actor=actor, path=path)

    trader = SimplePaperTrader(actor)
    result = None
    exec_audit_id = None
    note = f"ab_test:{test_name}:{variant}"
    try:
        if side.upper() == "BUY":
            pid = trader.buy(symbol, qty, price, confidence=confidence)
            result = {"result_type": "position", "result_value": pid}
        else:
            pnl = trader.sell(symbol, qty, price, confidence=confidence)
            result = {"result_type": "pnl", "result_value": float(pnl)}
        # log executed audit (audit.log_execution is also called inside trader)
        try:
            exec_audit_id = audit.log_execution(actor=actor, strategy=variant, action="ab_executed", symbol=symbol, qty=qty, price=price, side=side, confidence=confidence, risk_allowed=True, note=note)
        except Exception:
            exec_audit_id = None

    except Exception as exc:
        # record rejection or error
        try:
            exec_audit_id = audit.log_execution(actor=actor, strategy=variant, action="ab_error", symbol=symbol, qty=qty, price=price, side=side, confidence=confidence, risk_allowed=False, risk_reason=str(exc), note=note)
        except Exception:
            pass
        result = {"result_type": "error", "result_value": str(exc)}

    # persist result
    conn = _connect(path)
    cur = conn.cursor()
    ts = _now_iso()
    cur.execute(
        "INSERT INTO ab_results (assignment_id, action, symbol, qty, price, side, result_type, result_value, exec_audit_id, note, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            aid,
            side.upper(),
            symbol,
            float(qty),
            float(price),
            side.upper(),
            result.get("result_type"),
            float(result.get("result_value")) if isinstance(result.get("result_value"), (int, float)) else None,
            exec_audit_id,
            note,
            ts,
        ),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()

    out = {
        "test": test_name,
        "variant": variant,
        "assignment_id": aid,
        "result_id": rid,
        "exec_audit_id": exec_audit_id,
        "result": result,
    }
    return out


__all__ = ["ensure_tables", "create_test", "list_tests", "assign_variant", "route_and_execute"]
