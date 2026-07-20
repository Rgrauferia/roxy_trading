"""LLM-driven auto-execution pipeline.

Provides a simple orchestration: request signals from the LLM agent,
run risk checks, optionally perform dry-run simulations, and (if
enabled) execute via the paper trader. All steps are audited to
`execution_audit` using `tools.audit`.

This is intentionally conservative and synchronous — a production
implementation should enqueue executions and run in a separate worker.
"""
from __future__ import annotations

import os
import logging
from typing import List, Optional, Dict, Any

from tools import audit

logger = logging.getLogger("auto_exec")


def _execution_enabled() -> bool:
    # Fail closed. Local paper mutation requires an explicit operator opt-in.
    v = os.getenv("EXECUTION_ENABLED", "0")
    return v.strip().lower() in ("1", "true", "yes", "on", "paper")


def run_llm_auto_pipeline(user: str, symbols: List[str], horizon: str = "1d", dry_run: bool = True, auto_execute: bool = False) -> Dict[str, Any]:
    """Run LLM -> risk -> (optional) execute pipeline.

    Returns a dict summarizing signals and actions taken.
    - `dry_run=True` will never call the trader; it still runs risk checks and audit logs.
    - `auto_execute=True` will attempt to execute allowed orders when `EXECUTION_ENABLED`.
    """
    out = {"user": user, "signals": [], "executions": []}

    # request signals from local llm_agent implementation
    try:
        from tools.llm_agent import SignalRequest, generate_signals
    except Exception:
        logger.exception("llm_agent not available")
        return {"error": "llm_agent not available"}

    # build request and call generator (synchronous)
    req = SignalRequest(symbols=symbols, horizon=horizon)
    try:
        signals = generate_signals(req)
    except Exception:
        logger.exception("generate_signals failed")
        return {"error": "generate_signals failed"}

    # iterate signals and decide
    try:
        from tools.risk import RiskManager
        from adapters.paper_trader import SimplePaperTrader
    except Exception:
        logger.exception("risk or paper_trader unavailable")
        return {"error": "risk or trader unavailable"}

    rm = RiskManager()
    trader = SimplePaperTrader(user)

    for s in signals:
        try:
            symbol = (s.symbol or "").upper()
            action = (s.action or "hold").upper()
            confidence = float(s.confidence) if s.confidence is not None else None
            size_pct = float(s.size_pct) if s.size_pct is not None else None
            price = float(s.price) if s.price is not None else None

            # determine qty from size_pct if provided, else require price+qty in signal
            if size_pct is not None and price is not None:
                # conservative sizing: percent of equity
                try:
                    from storage import get_account_equity
                    equity = float(get_account_equity(user))
                except Exception:
                    equity = 10000.0
                order_value = equity * float(size_pct)
                qty = order_value / (price if price > 0 else 1.0)
            else:
                # fallback: use size_pct as absolute units if price missing
                qty = float(s.size_pct or 0.0)

            # risk check
            ok, reason = rm.check_order(user, symbol, qty, price or 0.0, side=action, confidence=confidence)

            # audit pre-check
            try:
                audit.log_execution(actor=user, strategy=None, action="pre_check", symbol=symbol, qty=qty, price=price, side=action, confidence=confidence, risk_allowed=ok, risk_reason=reason, note="llm_signal")
            except Exception:
                logger.exception("failed to write pre-check audit")

            sig_out = {"symbol": symbol, "action": action, "qty": qty, "price": price, "confidence": confidence, "risk_allowed": ok, "risk_reason": reason}
            out["signals"].append(sig_out)

            if ok and auto_execute and not dry_run and _execution_enabled():
                try:
                    if action == "BUY":
                        pid = trader.buy(symbol, qty, price or 0.0, confidence=confidence)
                        audit.log_execution(actor=user, strategy=None, action="executed", symbol=symbol, qty=qty, price=price, side=action, confidence=confidence, risk_allowed=True, note=f"pid={pid}")
                        out["executions"].append({"symbol": symbol, "action": action, "qty": qty, "price": price, "pid": pid})
                    elif action == "SELL":
                        pnl = trader.sell(symbol, qty, price or 0.0, confidence=confidence)
                        audit.log_execution(actor=user, strategy=None, action="executed", symbol=symbol, qty=qty, price=price, side=action, confidence=confidence, risk_allowed=True, note=f"pnl={pnl}")
                        out["executions"].append({"symbol": symbol, "action": action, "qty": qty, "price": price, "pnl": pnl})
                except Exception as exc:
                    logger.exception("execution failed")
                    audit.log_execution(actor=user, strategy=None, action="execution_failed", symbol=symbol, qty=qty, price=price, side=action, confidence=confidence, risk_allowed=False, risk_reason=str(exc), note="exec_error")
                    out.setdefault("errors", []).append({"symbol": symbol, "error": str(exc)})

        except Exception as exc:
            logger.exception("processing signal failed")
            out.setdefault("errors", []).append({"symbol": getattr(s, 'symbol', None), "error": str(exc)})

    return out


if __name__ == "__main__":
    # simple CLI demo
    res = run_llm_auto_pipeline(user="dev", symbols=["AAPL", "MSFT"], horizon="1d", dry_run=True, auto_execute=False)
    print(res)
