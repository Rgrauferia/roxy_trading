"""Simple paper-trading adapter.

This module provides a minimal, in-memory `PaperTrader` for historical
backtests. It never writes into the operational paper journal unless an
explicit audit path is supplied by the caller.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from roxy_time import utc_now_naive_iso

from logging_config import get_logger

logger = get_logger("execution")

class TradeRecord:
    def __init__(self, ts: str, symbol: str, side: str, qty: float, price: float):
        self.ts = ts
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.price = price

    def to_row(self) -> List[str]:
        return [self.ts, self.symbol, self.side, str(self.qty), str(self.price)]


class PaperTrader:
    """Very small paper trader: market orders only, no fees, FIFO position tracking."""

    def __init__(self, audit_path: str | Path | None = None) -> None:
        self.positions: Dict[str, float] = {}
        self.records: List[TradeRecord] = []
        self.audit_path = Path(audit_path).expanduser() if audit_path else None
        if self.audit_path is not None and not self.audit_path.is_absolute():
            raise ValueError("audit_path must be absolute")
        if self.audit_path is not None:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        if self.audit_path is not None and not self.audit_path.exists():
            with self.audit_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ts", "symbol", "side", "qty", "price"])  # header

    def _record(self, rec: TradeRecord) -> None:
        self.records.append(rec)
        if self.audit_path is not None:
            with self.audit_path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(rec.to_row())

    @staticmethod
    def _order_values(symbol: str, qty: float, price: float) -> tuple[str, float, float]:
        clean_symbol = str(symbol or "").strip().upper()
        clean_qty = float(qty)
        clean_price = float(price)
        if not clean_symbol:
            raise ValueError("symbol is required")
        if clean_qty <= 0 or clean_price <= 0:
            raise ValueError("qty and price must be positive")
        return clean_symbol, clean_qty, clean_price

    def buy(self, symbol: str, qty: float, price: float) -> None:
        symbol, qty, price = self._order_values(symbol, qty, price)
        ts = utc_now_naive_iso()
        logger.info("Paper buy %s qty=%s @ %s", symbol, qty, price)
        self.positions[symbol] = self.positions.get(symbol, 0.0) + float(qty)
        self._record(TradeRecord(ts, symbol, "BUY", qty, price))

    def sell(self, symbol: str, qty: float, price: float) -> None:
        symbol, qty, price = self._order_values(symbol, qty, price)
        held = self.get_position(symbol)
        if qty > held + 1e-9:
            raise ValueError(f"sell qty {qty} exceeds held qty {held}")
        ts = utc_now_naive_iso()
        logger.info("Paper sell %s qty=%s @ %s", symbol, qty, price)
        self.positions[symbol] = self.positions.get(symbol, 0.0) - float(qty)
        self._record(TradeRecord(ts, symbol, "SELL", qty, price))

    def get_position(self, symbol: str) -> float:
        return float(self.positions.get(symbol, 0.0))


__all__ = ["PaperTrader"]
