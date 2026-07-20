from __future__ import annotations

from typing import Any

import pandas as pd

from monetization_readiness import combined_paper_monetization_summary, paper_evidence_records


def _records(frame: pd.DataFrame | None, book: str) -> list[dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    rows = []
    for item in frame.to_dict("records"):
        row = dict(item)
        row["book"] = book
        rows.append(row)
    return rows


def _number(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def build_paper_operations_snapshot(
    alpaca_journal: pd.DataFrame | None,
    crypto_journal: pd.DataFrame | None,
) -> dict[str, Any]:
    raw = _records(alpaca_journal, "Acciones paper") + _records(crypto_journal, "Crypto paper")
    evidence, duplicates_collapsed = paper_evidence_records(raw)
    summary = combined_paper_monetization_summary(alpaca_journal, crypto_journal)
    rows: list[dict[str, Any]] = []
    realized_pnl = 0.0
    realized_count = 0
    for item in evidence:
        entry = _number(item.get("entry"))
        stop = _number(item.get("stop"))
        qty = _number(item.get("qty"))
        notional = _number(item.get("notional"))
        closed_move = _number(item.get("closed_move_pct"))
        if notional is None and entry is not None and qty is not None:
            notional = entry * qty
        risk_dollars = _number(item.get("risk_dollars"))
        if risk_dollars is None and entry is not None and stop is not None and qty is not None:
            risk_dollars = abs(entry - stop) * qty
        side = str(item.get("side") or "buy").strip().lower()
        direction = -1.0 if side in {"sell", "short"} else 1.0
        pnl = closed_move * notional * direction if closed_move is not None and notional is not None else None
        if pnl is not None:
            realized_pnl += pnl
            realized_count += 1
        rows.append(
            {
                "book": item.get("book"),
                "symbol": item.get("symbol"),
                "strategy": item.get("strategy_family"),
                "timeframe": item.get("timeframe"),
                "status": item.get("status"),
                "outcome": item.get("closed_outcome") or item.get("outcome"),
                "opened_at": item.get("ts") or item.get("opened_at"),
                "closed_at": item.get("closed_at"),
                "entry": entry,
                "stop": stop,
                "target": _number(item.get("take_profit") or item.get("target_2")),
                "closed_price": _number(item.get("closed_price")),
                "qty": qty,
                "notional": notional,
                "risk_dollars": risk_dollars,
                "move_pct": closed_move,
                "realized_pnl": pnl,
                "data_source": item.get("data_source"),
                "data_gate": item.get("data_gate"),
                "price_basis": "CLOSED_PAPER_RESULT" if pnl is not None else "ENTRY_PLAN_ONLY",
            }
        )
    rows.sort(key=lambda row: str(row.get("closed_at") or row.get("opened_at") or ""), reverse=True)
    last_activity = max(
        (str(row.get("closed_at") or row.get("opened_at") or "") for row in rows),
        default="",
    )
    return {
        "mode": "PAPER_ONLY",
        "live_orders_enabled": False,
        "valuation": {
            "state": "REALIZED_PAPER_ONLY",
            "unrealized_pnl_available": False,
            "broker_equity_included": False,
            "sources": ["alerts/alpaca_paper_practice.csv", "alerts/crypto_paper_practice.csv"],
        },
        "summary": {
            **summary,
            "duplicates_collapsed": duplicates_collapsed,
            "realized_pnl": realized_pnl if realized_count else None,
            "realized_pnl_count": realized_count,
            "last_activity": last_activity,
        },
        "operations": rows,
    }
