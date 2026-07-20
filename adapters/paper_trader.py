"""Simple paper trader adapter backed by `storage` simulated trades and positions.

Provides a minimal API: `buy`, `sell`, `get_position`, `get_cash` that can be
used by UI and backtesting/execution layers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import storage
from tools.risk import RiskManager
from tools import audit


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
        - `random_seed`: retained for API compatibility; execution is deterministic.
        """
        self.user = user
        self.slippage_pct = float(slippage_pct)
        self.fill_rate = float(fill_rate)
        if self.slippage_pct < 0:
            raise ValueError("slippage_pct must be non-negative")
        if not 0 < self.fill_rate <= 1:
            raise ValueError("fill_rate must be greater than 0 and at most 1")
        storage.create_account_if_missing(user, starting_equity, path=storage.DB_PATH)
        # instantiate default risk manager
        self.risk = RiskManager()

    @staticmethod
    def _validated_order(symbol: str, qty: float, price: float) -> tuple[str, float, float]:
        clean_symbol = str(symbol or "").strip().upper()
        clean_qty = float(qty)
        clean_price = float(price)
        if not clean_symbol:
            raise ValueError("symbol is required")
        if clean_qty <= 0:
            raise ValueError("qty must be positive")
        if clean_price <= 0:
            raise ValueError("price must be positive")
        return clean_symbol, clean_qty, clean_price

    @staticmethod
    def _execution_note(action: str, price_source: str, price_ts: str | None) -> str:
        source = str(price_source or "caller_supplied_unverified").strip() or "caller_supplied_unverified"
        timestamp = str(price_ts or datetime.now(timezone.utc).isoformat()).strip()
        return f"paper_{action};price_source={source};price_ts={timestamp}"

    def buy(
        self,
        symbol: str,
        qty: float,
        price: float,
        confidence: Optional[float] = None,
        force: bool = False,
        *,
        price_source: str = "caller_supplied_unverified",
        price_ts: str | None = None,
    ) -> int:
        symbol, qty, price = self._validated_order(symbol, qty, price)
        # simulate execution with slippage and partial fill
        # perform pre-execution risk checks
        if not force:
            ok, reason = self.risk.check_order(self.user, symbol, qty, price, side="BUY", confidence=confidence)
            # log pre-check
            try:
                audit.log_execution(actor=self.user, strategy=None, action="pre_check", symbol=symbol, qty=qty, price=price, side="BUY", confidence=confidence, risk_allowed=ok, risk_reason=reason)
            except Exception:
                pass
            if not ok:
                # log rejection
                try:
                    audit.log_execution(actor=self.user, strategy=None, action="rejected", symbol=symbol, qty=qty, price=price, side="BUY", confidence=confidence, risk_allowed=ok, risk_reason=reason, note="risk_reject")
                except Exception:
                    pass
                raise RuntimeError(f"Risk check failed: {reason}")
        executed_qty = qty * float(self.fill_rate)
        # slippage positive for buys (worse price)
        exec_price = float(price) * (1.0 + float(self.slippage_pct))

        # record a simulated buy: open position and save trade audit
        provenance = self._execution_note("buy", price_source, price_ts)
        pid = storage.open_sim_position(self.user, symbol, executed_qty, exec_price, note=provenance, path=storage.DB_PATH)
        storage.save_simulated_trade(self.user, symbol, "BUY", executed_qty, exec_price, note=f"{provenance};pos={pid}", path=storage.DB_PATH)
        try:
            audit.log_execution(actor=self.user, strategy=None, action="executed", symbol=symbol, qty=executed_qty, price=exec_price, side="BUY", confidence=confidence, risk_allowed=True, note=f"pos={pid}")
        except Exception:
            pass
        # snapshot account after opening
        try:
            storage.snapshot_account_point(self.user)
        except Exception:
            pass
        return pid

    def sell(
        self,
        symbol: str,
        qty: float,
        price: float,
        confidence: Optional[float] = None,
        force: bool = False,
        *,
        price_source: str = "caller_supplied_unverified",
        price_ts: str | None = None,
    ) -> float:
        symbol, qty, price = self._validated_order(symbol, qty, price)
        held_qty = self.get_position(symbol)
        executed_qty = qty * float(self.fill_rate)
        # `force` may bypass portfolio risk limits, but never creates a phantom
        # close or an implicit short position in this long-only simulator.
        if executed_qty > held_qty + 1e-9:
            raise RuntimeError(f"sell qty {executed_qty} exceeds held qty {held_qty} (shorting not allowed)")
        # perform pre-execution risk checks
        if not force:
            ok, reason = self.risk.check_order(self.user, symbol, qty, price, side="SELL", confidence=confidence)
            # log pre-check
            try:
                audit.log_execution(actor=self.user, strategy=None, action="pre_check", symbol=symbol, qty=qty, price=price, side="SELL", confidence=confidence, risk_allowed=ok, risk_reason=reason)
            except Exception:
                pass
            if not ok:
                try:
                    audit.log_execution(actor=self.user, strategy=None, action="rejected", symbol=symbol, qty=qty, price=price, side="SELL", confidence=confidence, risk_allowed=ok, risk_reason=reason, note="risk_reject")
                except Exception:
                    pass
                raise RuntimeError(f"Risk check failed: {reason}")

        # attempt to close `qty` using LIFO logic; simulate slippage worsening fills for sells
        exec_price = float(price) * (1.0 - float(self.slippage_pct))
        pnl = storage.close_sim_position_by_symbol(self.user, symbol, executed_qty, exec_price, path=storage.DB_PATH)
        provenance = self._execution_note("sell", price_source, price_ts)
        storage.save_simulated_trade(self.user, symbol, "SELL", executed_qty, exec_price, note=f"{provenance};pnl={pnl}", path=storage.DB_PATH)
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
