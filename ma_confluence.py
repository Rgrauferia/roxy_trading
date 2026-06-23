from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from trade_plan import build_trade_plan


ENTRY_SETUPS = {"TREND_CONTINUATION", "PULLBACK", "EARLY_UPTREND"}


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _norm_tf(value: Any) -> str:
    out = str(value or "").strip().lower()
    return "1h" if out == "60m" else out


def _reason_join(reasons: list[str]) -> str:
    return "; ".join(dict.fromkeys(reason for reason in reasons if reason))


def _above(row: pd.Series, column: str, reference: str) -> bool:
    value = _safe_float(row.get(column))
    ref = _safe_float(row.get(reference))
    return bool(value is not None and ref is not None and value > ref)


def _entry_plan(entry: float | None, stop: float | None) -> tuple[float | None, float | None, float | None]:
    if entry is None or stop is None or stop <= 0 or stop >= entry:
        return None, None, None
    risk = entry - stop
    risk_pct = risk / entry
    return risk_pct, entry + risk, entry + 2 * risk


def _timeframe_context(row: pd.Series | None, tf: str) -> dict[str, Any]:
    if row is None:
        return {
            f"htf_{tf}_signal": None,
            f"htf_{tf}_setup": None,
            f"htf_{tf}_score": None,
            f"htf_{tf}_close": None,
        }
    return {
        f"htf_{tf}_signal": row.get("signal"),
        f"htf_{tf}_setup": row.get("setup"),
        f"htf_{tf}_score": _safe_float(row.get("score")),
        f"htf_{tf}_close": _safe_float(row.get("close")),
    }


def _higher_tf_state(rows: dict[str, pd.Series]) -> dict[str, Any]:
    confirmations = 0
    blocks = 0
    scores = []
    reasons: list[str] = []
    context: dict[str, Any] = {}
    for tf in ("2h", "4h"):
        row = rows.get(tf)
        context.update(_timeframe_context(row, tf))
        if row is None:
            continue
        setup = str(row.get("setup", ""))
        signal = str(row.get("signal", ""))
        score = _safe_float(row.get("score")) or 0.0
        scores.append(score)
        bullish = (
            setup in ENTRY_SETUPS
            and signal in {"BUY", "WATCH"}
            and score >= 55
            and _above(row, "close", "sma200")
            and (_above(row, "sma20", "sma40") or _above(row, "sma40", "sma100"))
        )
        bearish = setup == "DOWNTREND" or signal == "AVOID" or not _above(row, "close", "sma200")
        if bullish:
            confirmations += 1
            reasons.append(f"{tf} confirma contexto alcista")
        elif bearish:
            blocks += 1
            reasons.append(f"{tf} no acompana la estructura")
    htf_score = sum(scores) / len(scores) if scores else None
    if confirmations >= 2:
        bias = "CONFIRMED"
    elif confirmations == 1 and blocks == 0:
        bias = "PARTIAL"
    elif blocks > 0:
        bias = "BLOCKED"
    else:
        bias = "NO_DATA"
    return {
        **context,
        "higher_tf_bias": bias,
        "higher_tf_confirmations": confirmations,
        "higher_tf_blocks": blocks,
        "higher_tf_score": htf_score,
        "higher_tf_reasons": reasons,
    }


def evaluate_confluence(
    trigger: pd.Series,
    trend: pd.Series,
    *,
    higher_timeframes: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    trigger_score = int(_safe_float(trigger.get("score")) or 0)
    trend_score = int(_safe_float(trend.get("score")) or 0)
    trigger_setup = str(trigger.get("setup", ""))
    trend_setup = str(trend.get("setup", ""))
    trigger_signal = str(trigger.get("signal", ""))
    trigger_raw_signal = str(trigger.get("raw_signal", trigger_signal))
    trend_signal = str(trend.get("signal", ""))

    trigger_close = _safe_float(trigger.get("close"))
    trend_close = _safe_float(trend.get("close"))
    trigger_stop = _safe_float(trigger.get("stop"))
    trigger_extension = _safe_float(trigger.get("dist_sma20_pct"))
    trigger_atr_pct = _safe_float(trigger.get("atr_pct"))
    trigger_relative_volume = _safe_float(trigger.get("relative_volume"))

    trend_bias_ok = (
        trend_setup != "DOWNTREND"
        and trend_signal in {"BUY", "WATCH"}
        and trend_score >= 50
        and _above(trend, "close", "sma200")
        and (_above(trend, "sma20", "sma40") or _above(trend, "sma40", "sma100"))
    )
    trend_confirmed = trend_bias_ok and trend_setup in ENTRY_SETUPS and trend_score >= 55
    trigger_ok = (
        trigger_setup in ENTRY_SETUPS
        and trigger_raw_signal == "BUY"
        and trigger_score >= 70
        and _above(trigger, "close", "sma200")
        and _above(trigger, "sma20", "sma40")
    )
    not_extended = trigger_extension is None or trigger_extension <= 8.0
    backtest_eligible = _safe_bool(trigger.get("backtest_eligible")) and _safe_bool(trend.get("backtest_eligible"))

    score = int(round((trigger_score * 0.55) + (trend_score * 0.45)))
    reasons: list[str] = []
    htf = _higher_tf_state(higher_timeframes or {})

    if trend_confirmed:
        score += 10
        reasons.append("1h confirma setup alcista")
    elif trend_bias_ok:
        score -= 5
        reasons.append("1h tiene sesgo alcista, pero setup no confirmado")
    else:
        score -= 20
        reasons.append("1h no confirma tendencia")

    if trigger_ok:
        score += 10
        reasons.append("15m da gatillo tecnico")
    else:
        score -= 15
        reasons.append("15m aun no da gatillo")

    if backtest_eligible:
        score += 5
        reasons.append("Backtest historico elegible")
    else:
        score -= 20
        reasons.append("Backtest historico no elegible")

    if htf["higher_tf_bias"] == "CONFIRMED":
        score += 8
        reasons.extend(htf["higher_tf_reasons"])
    elif htf["higher_tf_bias"] == "PARTIAL":
        score += 3
        reasons.extend(htf["higher_tf_reasons"])
    elif htf["higher_tf_bias"] == "BLOCKED":
        score -= 12
        reasons.extend(htf["higher_tf_reasons"])
    else:
        reasons.append("2h/4h sin contexto suficiente")

    if not not_extended:
        score -= 10
        reasons.append("15m extendido sobre SMA20")

    score = int(max(0, min(100, score)))

    if trend_confirmed and trigger_ok and backtest_eligible and not_extended and score >= 75:
        signal = "BUY"
        action = "ENTER_LONG"
    elif trend_bias_ok and score >= 55:
        signal = "WATCH"
        action = "WAIT_FOR_TRIGGER"
    elif trigger_setup == "DOWNTREND" or trend_setup == "DOWNTREND":
        signal = "AVOID"
        action = "NO_TRADE_DOWNTREND"
    else:
        signal = "AVOID"
        action = "NO_TRADE"

    risk_pct, target_1r, target_2r = _entry_plan(trigger_close, trigger_stop)
    trade_plan = build_trade_plan(
        signal=signal,
        entry=trigger_close,
        stop=trigger_stop,
        confluence_score=score,
        trend_score=trend_score,
        atr_pct=trigger_atr_pct,
        relative_volume=trigger_relative_volume,
    )
    if signal == "BUY" and trade_plan.get("trade_decision") == "NO_TRADE_RISK_REWARD":
        signal = "WATCH"
        action = "WAIT_FOR_BETTER_RISK"
        reasons.append("Objetivos 2/5/10 no compensan el riesgo actual")

    result = {
        "market": trigger.get("market"),
        "symbol": trigger.get("symbol"),
        "signal": signal,
        "action": action,
        "confluence_score": score,
        "entry_tf": trigger.get("tf"),
        "trend_tf": trend.get("tf"),
        "entry": trigger_close,
        "stop": trigger_stop,
        "risk_pct": risk_pct,
        "target_1r": target_1r,
        "target_2r": target_2r,
        "atr_pct_15m": trigger_atr_pct,
        "relative_volume_15m": trigger_relative_volume,
        "trigger_signal": trigger_signal,
        "trigger_raw_signal": trigger_raw_signal,
        "trigger_setup": trigger_setup,
        "trigger_score": trigger_score,
        "trend_signal": trend_signal,
        "trend_setup": trend_setup,
        "trend_score": trend_score,
        "backtest_eligible": backtest_eligible,
        "backtest_profit_factor": trigger.get("backtest_profit_factor"),
        "backtest_buy_hold_edge_pct": trigger.get("backtest_buy_hold_edge_pct"),
        "backtest_trades": trigger.get("backtest_trades"),
        "close_15m": trigger_close,
        "close_1h": trend_close,
        "reasons": _reason_join(reasons),
    }
    result.update({key: value for key, value in htf.items() if key != "higher_tf_reasons"})
    result.update(trade_plan)
    return result


def build_confluence(
    scan_df: pd.DataFrame,
    *,
    trigger_tf: str = "15m",
    trend_tf: str = "1h",
    higher_tfs: tuple[str, ...] = ("2h", "4h"),
) -> pd.DataFrame:
    if scan_df.empty or not {"market", "symbol", "tf"}.issubset(scan_df.columns):
        return pd.DataFrame()

    data = scan_df.copy()
    data["_tf"] = data["tf"].apply(_norm_tf)
    trigger_tf = _norm_tf(trigger_tf)
    trend_tf = _norm_tf(trend_tf)
    higher_tfs = tuple(_norm_tf(tf) for tf in higher_tfs)

    rows = []
    for (_, _), group in data.groupby(["market", "symbol"], dropna=False):
        trigger_rows = group[group["_tf"] == trigger_tf]
        trend_rows = group[group["_tf"] == trend_tf]
        if trigger_rows.empty or trend_rows.empty:
            continue
        trigger = trigger_rows.sort_values("score", ascending=False).iloc[0]
        trend = trend_rows.sort_values("score", ascending=False).iloc[0]
        higher_rows = {}
        for tf in higher_tfs:
            tf_rows = group[group["_tf"] == tf]
            if not tf_rows.empty:
                higher_rows[tf] = tf_rows.sort_values("score", ascending=False).iloc[0]
        rows.append(evaluate_confluence(trigger, trend, higher_timeframes=higher_rows))

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    rank = {"BUY": 0, "WATCH": 1, "AVOID": 2}
    out["_rank"] = out["signal"].map(rank).fillna(9)
    out = out.sort_values(["_rank", "backtest_eligible", "confluence_score", "symbol"], ascending=[True, False, False, True])
    return out.drop(columns=["_rank"]).reset_index(drop=True)


def build_confluence_summary(df: pd.DataFrame, limit: int = 10) -> dict[str, Any]:
    if df.empty:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "rows": 0,
            "signal_counts": {},
            "buy_count": 0,
            "watch_count": 0,
            "buy": [],
            "watch": [],
        }

    buy = df[df["signal"].eq("BUY")].copy()
    watch = df[df["signal"].eq("WATCH")].copy()
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "rows": int(len(df)),
        "signal_counts": {str(key): int(value) for key, value in df["signal"].value_counts().items()},
        "buy_count": int(len(buy)),
        "watch_count": int(len(watch)),
        "buy": buy.head(limit).to_dict(orient="records"),
        "watch": watch.head(limit).to_dict(orient="records"),
    }


def _pct(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number * 100:.2f}%"


def _yes_no(value: Any) -> str:
    return "yes" if _safe_bool(value) else "no"


def _render_confluence_rows(rows: list[dict[str, Any]], empty: str) -> list[str]:
    if not rows:
        return [empty]
    lines = []
    for row in rows:
        lines.append(
            f"- {row.get('market', '-')} {row.get('symbol', '-')}: {row.get('signal', '-')} "
            f"| action {row.get('action', '-')} | score {row.get('confluence_score', '-')} "
            f"| decision {row.get('trade_decision', '-')} | target {_pct(row.get('recommended_target_pct'))} "
            f"| entry {row.get('entry', '-')} | stop {row.get('stop', '-')} | risk {_pct(row.get('risk_pct'))} "
            f"| 2% {_yes_no(row.get('target_2pct_ok'))} | 5% {_yes_no(row.get('target_5pct_ok'))} "
            f"| 10% {_yes_no(row.get('target_10pct_ok'))} "
            f"| 15m {row.get('trigger_setup', '-')} {row.get('trigger_score', '-')} "
            f"| 1h {row.get('trend_setup', '-')} {row.get('trend_score', '-')} "
            f"| HTF {row.get('higher_tf_bias', '-')} "
            f"2h {row.get('htf_2h_setup', '-')} {row.get('htf_2h_score', '-')} "
            f"4h {row.get('htf_4h_setup', '-')} {row.get('htf_4h_score', '-')} "
            f"| pf {row.get('backtest_profit_factor', '-')}"
        )
    return lines


def render_confluence_report(summary: dict[str, Any], scan_path: str | Path | None = None) -> str:
    lines = [
        "Roxy SMA Specialized Confluence Report",
        f"Generated: {summary.get('generated_at', '-')}",
        f"Rows: {summary.get('rows', 0)}",
    ]
    if scan_path:
        lines.append(f"Source: {scan_path}")
    lines.extend(
        [
            "",
            f"Signals: {summary.get('signal_counts', {})}",
            f"Confluence BUY count: {summary.get('buy_count', 0)}",
            f"Confluence WATCH count: {summary.get('watch_count', 0)}",
            "",
            "Confluence BUY: 1h trend + 15m trigger + historical filter",
        ]
    )
    lines.extend(_render_confluence_rows(summary.get("buy", []), "- No confluence BUY setups."))
    lines.extend(["", "Confluence WATCH"])
    lines.extend(_render_confluence_rows(summary.get("watch", []), "- No confluence WATCH setups."))
    return "\n".join(lines) + "\n"


def write_confluence_report(
    df: pd.DataFrame,
    *,
    scan_path: str | Path | None,
    report_path: str | Path,
    json_path: str | Path | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    summary = build_confluence_summary(df, limit=limit)
    report = render_confluence_report(summary, scan_path=scan_path)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(report, encoding="utf-8")
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary
