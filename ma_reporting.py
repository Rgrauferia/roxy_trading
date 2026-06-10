from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "-"
    return f"{number * 100:.2f}%"


def _compact_row(row: pd.Series) -> dict[str, Any]:
    keys = [
        "market",
        "symbol",
        "tf",
        "signal",
        "raw_signal",
        "backtest_eligible",
        "setup",
        "score",
        "close",
        "stop",
        "backtest_total_return_pct",
        "backtest_buy_hold_edge_pct",
        "backtest_profit_factor",
        "backtest_trades",
        "reasons",
    ]
    out = {}
    for key in keys:
        if key in row.index:
            value = row[key]
            if isinstance(value, float) and pd.isna(value):
                value = None
            out[key] = value
    return out


def build_scan_summary(df: pd.DataFrame, limit: int = 10) -> dict[str, Any]:
    if df.empty:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "rows": 0,
            "signal_counts": {},
            "raw_signal_counts": {},
            "buy": [],
            "filtered_buy": [],
            "eligible_watch": [],
        }

    data = df.copy()
    if "raw_signal" not in data.columns:
        data["raw_signal"] = data["signal"]
    if "backtest_eligible" not in data.columns:
        data["backtest_eligible"] = False

    buy = data[data["signal"].eq("BUY")].copy()
    filtered_buy = data[data["raw_signal"].eq("BUY") & data["signal"].ne("BUY")].copy()
    eligible_watch = data[data["backtest_eligible"].astype(bool) & data["signal"].ne("BUY")].copy()

    if "score" in filtered_buy.columns:
        filtered_buy = filtered_buy.sort_values(["score", "symbol"], ascending=[False, True])
    if "score" in eligible_watch.columns:
        eligible_watch = eligible_watch.sort_values(["score", "symbol"], ascending=[False, True])

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "rows": int(len(data)),
        "signal_counts": {str(key): int(value) for key, value in data["signal"].value_counts().items()},
        "raw_signal_counts": {str(key): int(value) for key, value in data["raw_signal"].value_counts().items()},
        "buy_count": int(len(buy)),
        "filtered_buy_count": int(len(filtered_buy)),
        "eligible_watch_count": int(len(eligible_watch)),
        "buy": [_compact_row(row) for _, row in buy.head(limit).iterrows()],
        "filtered_buy": [_compact_row(row) for _, row in filtered_buy.head(limit).iterrows()],
        "eligible_watch": [_compact_row(row) for _, row in eligible_watch.head(limit).iterrows()],
    }


def _render_rows(rows: list[dict[str, Any]], empty: str) -> list[str]:
    if not rows:
        return [empty]

    lines = []
    for row in rows:
        symbol = row.get("symbol", "-")
        market = row.get("market", "-")
        tf = row.get("tf", "-")
        signal = row.get("signal", "-")
        raw_signal = row.get("raw_signal", signal)
        score = row.get("score", "-")
        setup = row.get("setup", "-")
        close = row.get("close", "-")
        pf = row.get("backtest_profit_factor", "-")
        edge = _pct(row.get("backtest_buy_hold_edge_pct"))
        ret = _pct(row.get("backtest_total_return_pct"))
        trades = row.get("backtest_trades", "-")
        lines.append(
            f"- {market} {symbol} {tf}: {signal} (raw {raw_signal}) | setup {setup} | "
            f"score {score} | close {close} | bt ret {ret} | edge {edge} | pf {pf} | trades {trades}"
        )
    return lines


def render_scan_report(summary: dict[str, Any], scan_path: str | Path | None = None) -> str:
    lines = [
        "Roxy SMA 20/40/100/200 Report",
        f"Generated: {summary.get('generated_at', '-')}",
        f"Rows: {summary.get('rows', 0)}",
    ]
    if scan_path:
        lines.append(f"Source: {scan_path}")
    lines.extend(
        [
            "",
            f"Signals: {summary.get('signal_counts', {})}",
            f"Raw signals: {summary.get('raw_signal_counts', {})}",
            f"BUY count: {summary.get('buy_count', len(summary.get('buy', [])))}",
            f"Raw BUY downgraded count: {summary.get('filtered_buy_count', len(summary.get('filtered_buy', [])))}",
            f"Historically eligible non-BUY count: {summary.get('eligible_watch_count', len(summary.get('eligible_watch', [])))}",
            "",
            "BUY after backtest filter",
        ]
    )
    lines.extend(_render_rows(summary.get("buy", []), "- No BUY signals passed the historical filter."))
    lines.extend(["", "Raw BUY downgraded by backtest filter"])
    lines.extend(_render_rows(summary.get("filtered_buy", []), "- No raw BUY signals were downgraded."))
    lines.extend(["", "Historically eligible but not BUY today"])
    lines.extend(_render_rows(summary.get("eligible_watch", []), "- No historically eligible non-BUY symbols."))
    return "\n".join(lines) + "\n"


def write_scan_report(
    df: pd.DataFrame,
    *,
    scan_path: str | Path | None = None,
    report_path: str | Path,
    json_path: str | Path | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    summary = build_scan_summary(df, limit=limit)
    report = render_scan_report(summary, scan_path=scan_path)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(report, encoding="utf-8")
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary
