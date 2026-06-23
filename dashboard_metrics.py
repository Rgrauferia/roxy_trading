from __future__ import annotations

from typing import Iterable

import pandas as pd


TIMEFRAME_ORDER = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}

TARGET_COLUMNS = [
    ("2%", "target_2pct_ok"),
    ("5%", "target_5pct_ok"),
    ("10%", "target_10pct_ok"),
]


def _empty(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _sort_timeframes(df: pd.DataFrame, column: str = "tf") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    out = df.copy()
    out["_tf_order"] = out[column].map(TIMEFRAME_ORDER).fillna(9999)
    out = out.sort_values(["_tf_order", column]).drop(columns=["_tf_order"])
    return out.reset_index(drop=True)


def _bool_value(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _bool_series(series: pd.Series) -> pd.Series:
    return series.map(_bool_value)


def _numeric_frame(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def signal_counts_by_timeframe(scan_df: pd.DataFrame) -> pd.DataFrame:
    """Return signal counts split by timeframe for dashboard charts."""
    required = {"tf", "signal"}
    if scan_df.empty or not required.issubset(scan_df.columns):
        return _empty(["tf", "signal", "count"])

    counts = (
        scan_df[list(required)]
        .fillna("Unknown")
        .groupby(["tf", "signal"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    return _sort_timeframes(counts)


def setup_counts_by_timeframe(scan_df: pd.DataFrame) -> pd.DataFrame:
    """Return setup counts split by timeframe for dashboard charts."""
    required = {"tf", "setup"}
    if scan_df.empty or not required.issubset(scan_df.columns):
        return _empty(["tf", "setup", "count"])

    counts = (
        scan_df[list(required)]
        .fillna("Unknown")
        .groupby(["tf", "setup"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    return _sort_timeframes(counts)


def score_distribution(scan_df: pd.DataFrame) -> pd.DataFrame:
    if scan_df.empty or "score" not in scan_df.columns:
        return _empty(["score", "signal", "tf", "symbol"])
    keep = [col for col in ["score", "signal", "tf", "symbol"] if col in scan_df.columns]
    out = _numeric_frame(scan_df[keep], ["score"]).dropna(subset=["score"])
    return out.reset_index(drop=True)


def target_ladder_counts(confluence_df: pd.DataFrame) -> pd.DataFrame:
    """Count how many setups pass each target filter."""
    rows = []
    for label, column in TARGET_COLUMNS:
        count = 0
        if not confluence_df.empty and column in confluence_df.columns:
            count = int(_bool_series(confluence_df[column]).sum())
        rows.append({"target": label, "count": count})
    return pd.DataFrame(rows, columns=["target", "count"])


def trade_decision_counts(confluence_df: pd.DataFrame) -> pd.DataFrame:
    if confluence_df.empty or "trade_decision" not in confluence_df.columns:
        return _empty(["trade_decision", "count"])
    return (
        confluence_df[["trade_decision"]]
        .fillna("Unknown")
        .groupby("trade_decision", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )


def risk_score_points(confluence_df: pd.DataFrame) -> pd.DataFrame:
    required = {"risk_pct", "confluence_score"}
    if confluence_df.empty or not required.issubset(confluence_df.columns):
        return _empty(["risk_pct", "risk_display_pct", "confluence_score", "signal", "symbol", "trade_decision"])

    keep = [
        col
        for col in ["market", "symbol", "signal", "trade_decision", "risk_level", "risk_pct", "confluence_score"]
        if col in confluence_df.columns
    ]
    out = _numeric_frame(confluence_df[keep], ["risk_pct", "confluence_score"]).dropna(
        subset=["risk_pct", "confluence_score"]
    )
    out["risk_display_pct"] = out["risk_pct"] * 100
    return out.reset_index(drop=True)


def option_quality_points(options_df: pd.DataFrame) -> pd.DataFrame:
    required = {"option_score", "spread_pct"}
    if options_df.empty or not required.issubset(options_df.columns):
        return _empty(["option_score", "spread_pct", "spread_display_pct", "symbol", "contractSymbol"])

    keep = [
        col
        for col in [
            "symbol",
            "contractSymbol",
            "option_decision",
            "option_score",
            "spread_pct",
            "breakeven_pct",
            "dte",
            "volume",
            "openInterest",
        ]
        if col in options_df.columns
    ]
    out = _numeric_frame(
        options_df[keep],
        ["option_score", "spread_pct", "breakeven_pct", "dte", "volume", "openInterest"],
    ).dropna(subset=["option_score", "spread_pct"])
    out["spread_display_pct"] = out["spread_pct"] * 100
    if "breakeven_pct" in out.columns:
        out["breakeven_display_pct"] = out["breakeven_pct"] * 100
    return out.reset_index(drop=True)


def option_expiry_counts(options_df: pd.DataFrame) -> pd.DataFrame:
    if options_df.empty or "expiry" not in options_df.columns:
        return _empty(["expiry", "count"])
    return (
        options_df[["expiry"]]
        .fillna("Unknown")
        .groupby("expiry", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("expiry")
        .reset_index(drop=True)
    )


def best_confluence_candidate(confluence_df: pd.DataFrame) -> dict:
    """Pick the row that deserves the most attention in the decision brief."""
    if confluence_df.empty:
        return {}

    out = _numeric_frame(
        confluence_df.copy(),
        ["confluence_score", "recommended_target_pct", "risk_pct", "entry", "stop", "recommended_target_price"],
    )
    if "signal" not in out.columns:
        out["signal"] = ""
    if "trade_decision" not in out.columns:
        out["trade_decision"] = ""

    trade_text = out["trade_decision"].fillna("").astype(str)
    signal_text = out["signal"].fillna("").astype(str)
    out["_action_rank"] = (
        trade_text.str.startswith("TRADE_FOR").astype(int) * 3
        + signal_text.eq("BUY").astype(int) * 2
        + signal_text.eq("WATCH").astype(int)
    )
    out["_target_rank"] = out.get("recommended_target_pct", pd.Series(0, index=out.index)).fillna(0)
    out["_score_rank"] = out.get("confluence_score", pd.Series(0, index=out.index)).fillna(0)
    best = out.sort_values(["_action_rank", "_score_rank", "_target_rank"], ascending=False).iloc[0]
    clean = best.drop(labels=[col for col in ["_action_rank", "_score_rank", "_target_rank"] if col in best.index])
    return clean.to_dict()
