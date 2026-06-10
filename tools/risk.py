"""Risk manager utilities for pre-execution checks.

Provides a lightweight RiskManager that enforces simple rules before
allowing paper trades: max position size (pct of equity), max total
exposure (pct of equity), and minimum model confidence threshold.

This is intentionally simple and conservative — it uses position
entry prices for exposure estimation when live market prices aren't
readily available.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import storage


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


class RiskManager:
    """Simple risk manager for pre-execution checks.

    Configurable via env vars:
    - RISK_MAX_POSITION_PCT: max single-position value as fraction of equity (default 0.1)
    - RISK_MAX_EXPOSURE_PCT: max total exposure as fraction of equity (default 0.3)
    - RISK_MIN_CONFIDENCE: minimum model confidence required to auto-execute (default 0.6)
    """

    def __init__(self,
                 max_position_pct: Optional[float] = None,
                 max_exposure_pct: Optional[float] = None,
                 min_confidence: Optional[float] = None):
        self.max_position_pct = max_position_pct if max_position_pct is not None else _env_float("RISK_MAX_POSITION_PCT", 0.1)
        self.max_exposure_pct = max_exposure_pct if max_exposure_pct is not None else _env_float("RISK_MAX_EXPOSURE_PCT", 0.3)
        self.min_confidence = min_confidence if min_confidence is not None else _env_float("RISK_MIN_CONFIDENCE", 0.6)

    def check_order(self, user: str, symbol: str, qty: float, price: float, side: str = "BUY", confidence: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """Check whether an order should be allowed.

        Returns (True, None) when allowed, otherwise (False, reason).
        - For BUY: enforces max single position size and max total exposure.
        - For SELL: ensures enough open quantity exists (no shorting allowed).
        """
        qty = float(qty)
        price = float(price)
        side = (side or "BUY").upper()

        # confidence check (if provided)
        if confidence is not None:
            try:
                c = float(confidence)
            except Exception:
                c = 0.0
            if c < self.min_confidence:
                return False, f"confidence {c:.3f} below minimum {self.min_confidence:.3f}"

        # ensure account exists and fetch equity
        try:
            equity = float(storage.get_account_equity(user))
        except Exception:
            # if account not present, create one with defaults
            storage.create_account_if_missing(user)
            equity = float(storage.get_account_equity(user))

        # compute existing exposure conservatively using entry_price
        existing_exposure = 0.0
        try:
            rows = storage.get_open_positions(user)
            for pid, ts_open, usr, sym, pqty, entry_price, note in rows:
                existing_exposure += float(pqty) * float(entry_price)
        except Exception:
            existing_exposure = 0.0

        new_order_value = qty * price

        if side == "BUY":
            # single position limit
            if new_order_value > equity * self.max_position_pct:
                return False, f"order value {new_order_value:.2f} exceeds max position {self.max_position_pct*100:.1f}% of equity ({equity:.2f})"

            # total exposure limit
            total = existing_exposure + new_order_value
            if total > equity * self.max_exposure_pct:
                return False, f"total exposure {total:.2f} exceeds max exposure {self.max_exposure_pct*100:.1f}% of equity ({equity:.2f})"

            return True, None

        elif side == "SELL":
            # do not allow selling more than held (no shorting)
            pos_qty = 0.0
            try:
                rows = storage.get_open_positions(user)
                for pid, ts_open, usr, sym, pqty, entry_price, note in rows:
                    if sym == symbol:
                        pos_qty += float(pqty)
            except Exception:
                pos_qty = 0.0

            if qty > pos_qty + 1e-9:
                return False, f"sell qty {qty} exceeds held qty {pos_qty} (shorting not allowed)"
            return True, None

        else:
            return False, f"unknown side '{side}'"


__all__ = ["RiskManager"]
