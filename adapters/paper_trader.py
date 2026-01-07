"""Simple paper trader adapter backed by `storage` simulated trades and positions.

Provides a minimal API: `buy`, `sell`, `get_position`, `get_cash` that can be
used by UI and backtesting/execution layers.
"""
from __future__ import annotations

from typing import Dict, Optional
import storage
import random


class SimplePaperTrader:
    """A lightweight paper trader that records trades to `storage` and updates
    simulated accounts/positions.

    Usage:
        pt = SimplePaperTrader(user)
        pt.buy('AAPL', qty=1, price=150.0)
        pt.sell('AAPL', qty=0.5, price=155.0)
    """

    def __init__(self, user: str, starting_equity: float = 10000.0, *, slippage_pct: float = 0.0, fill_rate: float = 1.0, random_seed: Optional[int] = None):
        """Create a SimplePaperTrader.

        - `slippage_pct`: expected slippage as fraction (e.g. 0.001 = 0.1%). Applied multiplicatively to price.
        - `fill_rate`: fraction of requested qty filled (0.0-1.0). 1.0 means full fill.
        - `random_seed`: optional seed for deterministic behavior in tests.
        """
        self.user = user
        self.slippage_pct = float(slippage_pct)
        self.fill_rate = float(fill_rate)
        if random_seed is not None:
            random.seed(random_seed)
        storage.create_account_if_missing(user, starting_equity, path=storage.DB_PATH)

    def buy(self, symbol: str, qty: float, price: float) -> int:
        # simulate execution with slippage and partial fill
        qty = float(qty)
        executed_qty = qty * float(self.fill_rate)
        # slippage positive for buys (worse price)
        exec_price = float(price) * (1.0 + float(self.slippage_pct))

        # record a simulated buy: open position and save trade audit
        pid = storage.open_sim_position(self.user, symbol, executed_qty, exec_price, note="paper_buy", path=storage.DB_PATH)
        storage.save_simulated_trade(self.user, symbol, "BUY", executed_qty, exec_price, note=f"paper_buy:pos={pid}", path=storage.DB_PATH)
        # snapshot account after opening
        try:
            storage.snapshot_account_point(self.user)
        except Exception:
            pass
        return pid

    def sell(self, symbol: str, qty: float, price: float) -> float:
        # attempt to close `qty` using LIFO logic; simulate slippage worsening fills for sells
        qty = float(qty)
        executed_qty = qty * float(self.fill_rate)
        exec_price = float(price) * (1.0 - float(self.slippage_pct))
        pnl = storage.close_sim_position_by_symbol(self.user, symbol, executed_qty, exec_price, path=storage.DB_PATH)
        storage.save_simulated_trade(self.user, symbol, "SELL", executed_qty, exec_price, note=f"paper_sell:pnl={pnl}", path=storage.DB_PATH)
        try:
            storage.snapshot_account_point(self.user)
        except Exception:
            pass
        return float(pnl)

    def get_position(self, symbol: str) -> float:
        rows = storage.get_open_positions(self.user, path=storage.DB_PATH)
        total = 0.0
        for pid, ts_open, usr, sym, pqty, entry_price, note in rows:
            if sym == symbol:
                total += float(pqty)
        return total

    def get_cash(self) -> float:
        try:
            return storage.get_account_equity(self.user, path=storage.DB_PATH)
        except Exception:
            return 0.0
