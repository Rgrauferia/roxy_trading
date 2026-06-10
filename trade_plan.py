from __future__ import annotations

from typing import Any


TARGET_PCTS = (0.02, 0.05, 0.10)
MIN_REWARD_R = {0.02: 1.0, 0.05: 1.5, 0.10: 2.0}
MIN_TARGET_SCORE = {0.02: 60, 0.05: 72, 0.10: 85}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _risk_level(risk_pct: float | None) -> str:
    if risk_pct is None:
        return "UNKNOWN"
    if risk_pct <= 0.015:
        return "LOW"
    if risk_pct <= 0.03:
        return "MEDIUM"
    return "HIGH"


def _target_key(target_pct: float) -> str:
    return f"target_{int(target_pct * 100)}pct"


def _target_score(
    *,
    base_score: int,
    target_pct: float,
    reward_r: float | None,
    bars_to_target: float | None,
    relative_volume: float | None,
    trend_score: int,
) -> int:
    score = base_score
    if reward_r is None:
        return 0
    if reward_r >= MIN_REWARD_R[target_pct] + 1:
        score += 10
    elif reward_r < MIN_REWARD_R[target_pct]:
        score -= 30

    if bars_to_target is not None:
        if bars_to_target <= 4:
            score += 12
        elif bars_to_target <= 8:
            score += 6
        elif bars_to_target > 24:
            score -= 15

    if relative_volume is not None:
        if relative_volume >= 1.5:
            score += 10
        elif relative_volume >= 1.1:
            score += 5
        elif relative_volume < 0.7:
            score -= 12

    if target_pct == 0.05:
        score -= 5
    elif target_pct == 0.10:
        score -= 15
        if trend_score < 75:
            score -= 15

    return int(max(0, min(100, score)))


def build_trade_plan(
    *,
    signal: str,
    entry: Any,
    stop: Any,
    confluence_score: int,
    trend_score: int,
    atr_pct: Any = None,
    relative_volume: Any = None,
) -> dict[str, Any]:
    entry_value = _safe_float(entry)
    stop_value = _safe_float(stop)
    atr_pct_value = _safe_float(atr_pct)
    rel_vol_value = _safe_float(relative_volume)

    risk_pct = None
    if entry_value is not None and stop_value is not None and 0 < stop_value < entry_value:
        risk_pct = (entry_value - stop_value) / entry_value

    out: dict[str, Any] = {
        "risk_pct": risk_pct,
        "risk_level": _risk_level(risk_pct),
        "recommended_target_pct": None,
        "recommended_target_price": None,
        "trade_decision": "NO_TRADE" if signal == "AVOID" else "WAIT",
        "exit_plan": "Wait for a valid BUY setup before entering.",
    }

    feasible_targets: list[tuple[float, float]] = []
    for target_pct in TARGET_PCTS:
        key = _target_key(target_pct)
        target_price = entry_value * (1.0 + target_pct) if entry_value is not None else None
        reward_r = target_pct / risk_pct if risk_pct and risk_pct > 0 else None
        bars_to_target = target_pct / atr_pct_value if atr_pct_value and atr_pct_value > 0 else None
        target_score = _target_score(
            base_score=confluence_score,
            target_pct=target_pct,
            reward_r=reward_r,
            bars_to_target=bars_to_target,
            relative_volume=rel_vol_value,
            trend_score=trend_score,
        )
        is_feasible = (
            signal == "BUY"
            and reward_r is not None
            and reward_r >= MIN_REWARD_R[target_pct]
            and target_score >= MIN_TARGET_SCORE[target_pct]
        )
        if target_pct == 0.10 and (trend_score < 75 or (rel_vol_value is not None and rel_vol_value < 1.1)):
            is_feasible = False
        out[f"{key}_price"] = target_price
        out[f"{key}_reward_r"] = reward_r
        out[f"{key}_bars_est"] = bars_to_target
        out[f"{key}_score"] = target_score
        out[f"{key}_ok"] = bool(is_feasible)
        if is_feasible:
            feasible_targets.append((target_pct, target_price or 0.0))

    if signal == "BUY":
        if feasible_targets:
            target_pct, target_price = feasible_targets[-1]
            out["recommended_target_pct"] = target_pct
            out["recommended_target_price"] = target_price
            out["trade_decision"] = f"TRADE_FOR_{int(target_pct * 100)}PCT"
            out["exit_plan"] = (
                f"Take profit near {target_price:.4f}; exit immediately if price hits stop "
                f"{stop_value:.4f}." if stop_value is not None else "Take profit at target; stop is not available."
            )
        else:
            out["trade_decision"] = "NO_TRADE_RISK_REWARD"
            out["exit_plan"] = "BUY setup exists, but 2/5/10 percent targets do not justify the current stop risk."
    elif signal == "WATCH":
        out["trade_decision"] = "WAIT"
        out["exit_plan"] = "Watch only. Enter after confluence turns BUY; do not front-run the signal."

    return out
