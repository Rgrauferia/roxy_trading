"""Grok/LLM integration stub.

Provides `generate_suggestion(symbol, context)` which calls an external
provider when `GROK_API_KEY` is set. Right now it's a local stub that
returns a templated suggestion. Implement provider calls here.
"""
from __future__ import annotations

import os
from typing import Dict

GROK_API_KEY = os.getenv("GROK_API_KEY", "")


def generate_suggestion(symbol: str, context: Dict) -> Dict:
    """Return a suggestion dict for `symbol`.

    If `GROK_API_KEY` is present, integrate with the real API here.
    The returned dict contains `text`, `confidence` (0-1), and `details`.
    """
    # Placeholder deterministic suggestion based on simple rules
    score = context.get("score") or 0
    signal = context.get("signal", "WATCH")
    if GROK_API_KEY:
        # TODO: call provider API using requests with the key
        pass

    if score >= 55 or signal == "BUY":
        text = f"Recommendation: Consider BUY for {symbol} — technicals positive."
        confidence = min(0.95, 0.5 + (score or 0) / 200)
    elif score >= 35:
        text = f"Recommendation: WATCH {symbol}. Wait for confirmation or pullback."
        confidence = 0.5
    else:
        text = f"Recommendation: AVOID {symbol}. Downtrend or weak setup."
        confidence = 0.35

    return {"text": text, "confidence": float(confidence), "details": {"score": score, "signal": signal}}
