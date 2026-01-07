"""Simple paper-trading adapter.

This module provides a minimal `PaperTrader` that records simulated orders
to `db/trades.csv` and keeps an in-memory positions map. Useful for testing
strategy behaviour without a real broker.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Dict, List

from logging_config import get_logger

logger = get_logger("execution")

TRADES_FILE = os.path.join("db", "trades.csv")
os.makedirs("db", exist_ok=True)


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

    def __init__(self) -> None:
        self.positions: Dict[str, float] = {}
        # ensure file has header
        if not os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ts", "symbol", "side", "qty", "price"])  # header

    def _record(self, rec: TradeRecord) -> None:
        with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(rec.to_row())

    def buy(self, symbol: str, qty: float, price: float) -> None:
        ts = datetime.utcnow().isoformat()
        logger.info("Paper buy %s qty=%s @ %s", symbol, qty, price)
        self.positions[symbol] = self.positions.get(symbol, 0.0) + float(qty)
        self._record(TradeRecord(ts, symbol, "BUY", qty, price))

    def sell(self, symbol: str, qty: float, price: float) -> None:
        ts = datetime.utcnow().isoformat()
        logger.info("Paper sell %s qty=%s @ %s", symbol, qty, price)
        self.positions[symbol] = self.positions.get(symbol, 0.0) - float(qty)
        self._record(TradeRecord(ts, symbol, "SELL", qty, price))

    def get_position(self, symbol: str) -> float:
        return float(self.positions.get(symbol, 0.0))


__all__ = ["PaperTrader"]
