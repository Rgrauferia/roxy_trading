"""DB reporting helpers for roxy_trading.

Usage:
  python tools/report.py top-symbols
  python tools/report.py trades-summary

`top-symbols` shows most-scanned symbols and average score.
`trades-summary` reads `db/trades.csv` (if present) and shows buy/sell counts and net qty per symbol.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Dict, List


DB = Path("db/roxy.db")
TRADES = Path("db/trades.csv")


def top_symbols(limit: int = 20) -> List[Dict]:
    if not DB.exists():
        print("No DB found at db/roxy.db")
        return []
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    cur.execute(
        (
            "SELECT symbol, COUNT(*) as cnt, AVG(score) as avg_score, AVG(rr_tp2) as avg_rr_tp2 "
            "FROM scans GROUP BY symbol ORDER BY cnt DESC LIMIT ?"
        ),
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    out = []
    for sym, cnt, avg_score, avg_rr in rows:
        out.append({"symbol": sym, "count": cnt, "avg_score": avg_score, "avg_rr_tp2": avg_rr})
    return out


def trades_summary() -> Dict[str, Dict]:
    if not TRADES.exists():
        print("No trades.csv found at db/trades.csv")
        return {}
    buys = Counter()
    sells = Counter()
    net_qty = defaultdict(float)
    with TRADES.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sym = r.get("symbol")
            side = r.get("side")
            qty = float(r.get("qty") or 0)
            if side == "BUY":
                buys[sym] += 1
                net_qty[sym] += qty
            elif side == "SELL":
                sells[sym] += 1
                net_qty[sym] -= qty
    out = {}
    syms = set(list(buys.keys()) + list(sells.keys()))
    for s in syms:
        out[s] = {"buys": buys[s], "sells": sells[s], "net_qty": net_qty[s]}
    return out


def print_top_symbols():
    rows = top_symbols()
    if not rows:
        print("No scan rows found.")
        return
    print(f"{'Symbol':10} {'Count':6} {'AvgScore':8} {'AvgRR2':8}")
    for r in rows:
        print(f"{r['symbol']:10} {r['count']:6d} {r['avg_score'] or 0:8.2f} {r['avg_rr_tp2'] or 0:8.2f}")


def print_trades_summary():
    s = trades_summary()
    if not s:
        return
    print(f"{'Symbol':10} {'Buys':6} {'Sells':6} {'NetQty':8}")
    for sym, v in s.items():
        print(f"{sym:10} {v['buys']:6d} {v['sells']:6d} {v['net_qty']:8.2f}")


def list_backtests():
    db = Path("db/roxy.db")
    if not db.exists():
        print("No DB found at db/roxy.db")
        return
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute("SELECT id, name, ts, metrics_json FROM backtests ORDER BY ts DESC LIMIT 50")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("No backtests found")
        return
    print(f"{'ID':4} {'Name':20} {'TS':25} {'Trades':6} {'WinRate':8} {'PnL':10}")
    for id_, name, ts, metrics_json in rows:
        try:
            m = json.loads(metrics_json)
            trades = m.get("trades", 0)
            win_rate = m.get("win_rate", 0.0)
            pnl = m.get("realized_pnl", 0.0)
        except Exception:
            trades = win_rate = pnl = "?"
        print(f"{id_:4d} {name:20} {ts:25} {trades:6} {win_rate:8.2f} {pnl:10.2f}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/report.py [top-symbols|trades-summary]")
        raise SystemExit(1)
    cmd = sys.argv[1]
    if cmd == "top-symbols":
        print_top_symbols()
    elif cmd == "trades-summary":
        print_trades_summary()
    elif cmd == "list-backtests":
        list_backtests()
    else:
        print("Unknown command")


if __name__ == "__main__":
    main()
