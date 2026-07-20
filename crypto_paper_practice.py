from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from durable_storage import atomic_write_csv, exclusive_file_lock


DEFAULT_JOURNAL_PATH = Path("alerts/crypto_paper_practice.csv")

PRACTICE_COLUMNS = [
    "ts",
    "practice_id",
    "symbol",
    "market",
    "strategy_family",
    "timeframe",
    "data_bucket",
    "data_source",
    "data_gate",
    "signal",
    "decision",
    "status",
    "closed_at",
    "closed_outcome",
    "closed_price",
    "closed_move_pct",
    "side",
    "qty",
    "entry",
    "stop",
    "target_2",
    "target_5",
    "target_10",
    "take_profit",
    "risk_dollars",
    "notional",
    "rr_to_2pct",
    "reason",
]

SCORED_COLUMNS = PRACTICE_COLUMNS + [
    "current_price",
    "move_pct",
    "hit_2pct",
    "hit_5pct",
    "hit_10pct",
    "stop_hit",
    "outcome",
]


def _text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_float(*values: Any) -> float | None:
    for value in values:
        parsed = _float(value)
        if parsed is not None:
            return parsed
    return None


def _is_crypto(row: Mapping[str, Any]) -> bool:
    symbol = _text(row.get("symbol")).upper()
    market = _text(row.get("market")).lower()
    return market == "crypto" or "/" in symbol or symbol.endswith("USD")


def _is_trade_ready(row: Mapping[str, Any]) -> bool:
    action = _text(row.get("action") or row.get("ai_action")).upper()
    signal = _text(row.get("signal")).upper()
    decision = _text(row.get("decision") or row.get("trade_decision")).upper()
    return action == "ALERT" or (signal == "BUY" and decision.startswith("TRADE_FOR"))


def _practice_id(row: Mapping[str, Any]) -> str:
    raw = "|".join(
        [
            _text(row.get("symbol")).upper(),
            _text(row.get("strategy_family")),
            _text(row.get("timeframe")),
            f"{_float(row.get('entry')) or 0:.6f}",
            f"{_float(row.get('stop')) or 0:.6f}",
            f"{_float(row.get('take_profit')) or 0:.6f}",
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build_crypto_paper_practice_candidates(
    table: pd.DataFrame,
    *,
    account_equity: float = 500.0,
    risk_pct: float = 0.01,
    max_risk_pct: float = 0.035,
    min_target_pct: float = 0.02,
    limit: int = 10,
) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame(columns=PRACTICE_COLUMNS)

    risk_budget = max(0.0, float(account_equity or 0.0) * float(risk_pct or 0.0))
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []

    for item in table.to_dict("records"):
        symbol = _text(item.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        market = _text(item.get("market")).lower() or "crypto"
        entry = _float(item.get("entry"))
        stop = _float(item.get("stop"))
        target_pct = _float(item.get("target_pct") or item.get("recommended_target_pct"))
        target_price = _float(item.get("target_price") or item.get("recommended_target_price"))
        risk_value = _float(item.get("risk_pct"))
        signal = _text(item.get("signal")).upper()
        decision = _text(item.get("decision") or item.get("trade_decision")).upper()
        strategy = _text(item.get("strategy_family") or item.get("setup") or item.get("trigger"))
        timeframe = _text(item.get("timeframe") or item.get("tf") or "-")
        data_bucket = _text(item.get("data_bucket") or item.get("data_state") or "Sin contrato")
        data_source = _text(item.get("data_source") or item.get("Fuente") or "-")
        data_gate = _text(item.get("data_gate") or item.get("chart_data_gate") or item.get("live_price_gate") or "-")

        blockers: list[str] = []
        if not _is_crypto(item):
            blockers.append("Crypto paper practice solo crypto")
        if not _is_trade_ready(item):
            blockers.append("falta BUY/ALERT confirmado")
        if entry is None or entry <= 0:
            blockers.append("falta entrada")
        if stop is None or stop <= 0:
            blockers.append("falta stop")
        if entry is not None and stop is not None and abs(entry - stop) <= 0:
            blockers.append("stop invalido")
        if target_price is None and entry is not None and target_pct is not None:
            target_price = entry * (1.0 + target_pct)
        if target_pct is not None and target_pct < min_target_pct:
            blockers.append("target menor a 2%")
        if risk_value is not None and risk_value > max_risk_pct:
            blockers.append("riesgo mayor a 3.5%")

        qty = 0.0
        risk_dollars = 0.0
        notional = 0.0
        rr_to_2pct = None
        target_2 = target_5 = target_10 = None
        if entry is not None and entry > 0:
            target_2 = entry * 1.02
            target_5 = entry * 1.05
            target_10 = entry * 1.10
        if entry is not None and stop is not None and entry > 0 and stop > 0:
            unit_risk = abs(entry - stop)
            if unit_risk > 0:
                qty = risk_budget / unit_risk if risk_budget > 0 else 0.0
                rr_to_2pct = (entry * 0.02) / unit_risk
                risk_dollars = qty * unit_risk
                notional = qty * entry
                if qty <= 0:
                    blockers.append("riesgo no cabe en cuenta")

        status = "READY_FOR_PAPER" if not blockers else "BLOCKED"
        take_profit = target_price or target_2
        reason = _text(item.get("por_que") or item.get("raw_reason") or item.get("reason") or strategy)
        if blockers:
            reason = "; ".join(dict.fromkeys(blockers))

        row = {
            "ts": now,
            "symbol": symbol,
            "market": market,
            "strategy_family": strategy or "Sin clasificar",
            "timeframe": timeframe or "-",
            "data_bucket": data_bucket or "Sin contrato",
            "data_source": data_source or "-",
            "data_gate": data_gate or "-",
            "signal": signal,
            "decision": decision,
            "status": status,
            "side": "buy",
            "qty": round(max(qty, 0.0), 8),
            "entry": round(entry, 6) if entry is not None else None,
            "stop": round(stop, 6) if stop is not None else None,
            "target_2": round(target_2, 6) if target_2 is not None else None,
            "target_5": round(target_5, 6) if target_5 is not None else None,
            "target_10": round(target_10, 6) if target_10 is not None else None,
            "take_profit": round(take_profit, 6) if take_profit is not None else None,
            "risk_dollars": round(risk_dollars, 4),
            "notional": round(notional, 4),
            "rr_to_2pct": round(rr_to_2pct, 4) if rr_to_2pct is not None else None,
            "reason": reason,
        }
        row["practice_id"] = _practice_id(row)
        rows.append(row)
        if len(rows) >= limit:
            break

    return pd.DataFrame(rows, columns=PRACTICE_COLUMNS)


def load_crypto_paper_practice_journal(path: str | Path = DEFAULT_JOURNAL_PATH) -> pd.DataFrame:
    journal_path = Path(path)
    if not journal_path.exists():
        return pd.DataFrame(columns=PRACTICE_COLUMNS)
    try:
        data = pd.read_csv(journal_path)
    except Exception:
        return pd.DataFrame(columns=PRACTICE_COLUMNS)
    for column in PRACTICE_COLUMNS:
        if column not in data.columns:
            data[column] = None
    return data[PRACTICE_COLUMNS]


def _load_crypto_journal_for_update(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=PRACTICE_COLUMNS)
    data = pd.read_csv(path)
    for column in PRACTICE_COLUMNS:
        if column not in data.columns:
            data[column] = None
    return data[PRACTICE_COLUMNS]


def record_crypto_paper_practice_candidates(
    candidates: pd.DataFrame,
    *,
    path: str | Path = DEFAULT_JOURNAL_PATH,
) -> pd.DataFrame:
    if candidates.empty:
        return load_crypto_paper_practice_journal(path)
    journal_path = Path(path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(journal_path):
        existing = _load_crypto_journal_for_update(journal_path)
        frames = [frame for frame in [existing, candidates[PRACTICE_COLUMNS]] if not frame.empty]
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PRACTICE_COLUMNS)
        combined = combined.drop_duplicates(subset=["practice_id"], keep="first").reset_index(drop=True)
        if not existing.empty and combined["practice_id"].astype(str).tolist() == existing["practice_id"].astype(str).tolist():
            return existing[PRACTICE_COLUMNS]
        atomic_write_csv(combined, journal_path)
        return combined[PRACTICE_COLUMNS]


def score_crypto_paper_practice_journal(
    journal: pd.DataFrame,
    *,
    price_lookup: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    if journal.empty:
        return pd.DataFrame(columns=SCORED_COLUMNS)
    prices = {str(key).upper(): _float(value) for key, value in dict(price_lookup or {}).items()}
    rows: list[dict[str, Any]] = []
    for item in journal.to_dict("records"):
        symbol = _text(item.get("symbol")).upper()
        entry = _float(item.get("entry"))
        stop = _float(item.get("stop"))
        closed_outcome = _text(item.get("closed_outcome")).upper()
        closed_price = _float(item.get("closed_price"))
        current = prices.get(symbol)
        if current is None and "/" in symbol:
            current = prices.get(symbol.replace("/", ""))
        if current is None and closed_price is not None:
            current = closed_price
        move_pct = None
        hit_2 = hit_5 = hit_10 = stop_hit = False
        outcome = "OBSERVING"
        if closed_outcome in {"HIT_2", "HIT_5", "HIT_10", "STOP"}:
            outcome = closed_outcome
            hit_2 = closed_outcome in {"HIT_2", "HIT_5", "HIT_10"}
            hit_5 = closed_outcome in {"HIT_5", "HIT_10"}
            hit_10 = closed_outcome == "HIT_10"
            stop_hit = closed_outcome == "STOP"
        if entry is not None and entry > 0 and current is not None:
            move_pct = (current - entry) / entry
            if not closed_outcome:
                hit_2 = move_pct >= 0.02
                hit_5 = move_pct >= 0.05
                hit_10 = move_pct >= 0.10
                stop_hit = stop is not None and current <= stop
                if stop_hit:
                    outcome = "STOP"
                elif hit_10:
                    outcome = "HIT_10"
                elif hit_5:
                    outcome = "HIT_5"
                elif hit_2:
                    outcome = "HIT_2"
                else:
                    outcome = "OPEN"
        row = dict(item)
        row.update(
            {
                "current_price": round(current, 6) if current is not None else None,
                "move_pct": round(move_pct, 6) if move_pct is not None else None,
                "hit_2pct": bool(hit_2),
                "hit_5pct": bool(hit_5),
                "hit_10pct": bool(hit_10),
                "stop_hit": bool(stop_hit),
                "outcome": outcome,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=SCORED_COLUMNS)


def close_crypto_paper_practice_journal(
    journal: pd.DataFrame,
    *,
    price_lookup: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> pd.DataFrame:
    if journal.empty:
        return pd.DataFrame(columns=PRACTICE_COLUMNS)
    current_time = now or datetime.now(timezone.utc)
    scored = score_crypto_paper_practice_journal(journal, price_lookup=price_lookup)
    closed_outcomes = {"HIT_2", "HIT_5", "HIT_10", "STOP"}
    rows: list[dict[str, Any]] = []
    for item in scored.to_dict("records"):
        row = {column: item.get(column) for column in PRACTICE_COLUMNS}
        status = _text(row.get("status")).upper()
        outcome = _text(item.get("outcome")).upper()
        already_closed = status.startswith("CLOSED_") or bool(_text(row.get("closed_outcome")))
        closeable = status in {"READY_FOR_PAPER", "OPEN", "OBSERVING", ""}
        if closeable and not already_closed and outcome in closed_outcomes:
            row["status"] = f"CLOSED_{outcome}"
            row["closed_at"] = current_time.isoformat()
            row["closed_outcome"] = outcome
            row["closed_price"] = item.get("current_price")
            row["closed_move_pct"] = item.get("move_pct")
        rows.append(row)
    return pd.DataFrame(rows, columns=PRACTICE_COLUMNS)


def close_and_save_crypto_paper_practice_journal(
    *,
    price_lookup: Mapping[str, Any] | None = None,
    path: str | Path = DEFAULT_JOURNAL_PATH,
    now: datetime | None = None,
) -> pd.DataFrame:
    journal_path = Path(path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(journal_path):
        journal = _load_crypto_journal_for_update(journal_path)
        closed = close_crypto_paper_practice_journal(journal, price_lookup=price_lookup, now=now)
        if closed.empty:
            return closed
        atomic_write_csv(closed, journal_path)
        return closed


def price_lookup_from_crypto_opportunities(opportunities: pd.DataFrame | list[Mapping[str, Any]] | None) -> dict[str, float]:
    if isinstance(opportunities, pd.DataFrame):
        records = opportunities.to_dict("records")
    else:
        records = list(opportunities or [])
    lookup: dict[str, float] = {}
    for row in records:
        if not isinstance(row, Mapping) or not _is_crypto(row):
            continue
        symbol = _text(row.get("symbol") or row.get("Ticker")).upper()
        current = _first_float(
            row.get("current_price"),
            row.get("latest_price"),
            row.get("last_price"),
            row.get("last"),
            row.get("price"),
        )
        if not symbol or current is None:
            continue
        lookup[symbol] = current
        if "/" in symbol:
            lookup[symbol.replace("/", "")] = current
    return lookup


def summarize_crypto_paper_practice(scored: pd.DataFrame) -> pd.DataFrame:
    columns = ["strategy_family", "tracked", "ready", "hit_2_rate", "hit_5_rate", "hit_10_rate", "stop_rate", "open", "tone"]
    if scored.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for strategy, group in scored.groupby("strategy_family", dropna=False):
        tracked = len(group)
        ready = int((group["status"] == "READY_FOR_PAPER").sum()) if "status" in group else 0
        observed = group[group["outcome"].isin(["OPEN", "HIT_2", "HIT_5", "HIT_10", "STOP"])]
        denominator = max(len(observed), 1)
        hit_2_rate = float(group["hit_2pct"].sum()) / denominator
        hit_5_rate = float(group["hit_5pct"].sum()) / denominator
        hit_10_rate = float(group["hit_10pct"].sum()) / denominator
        stop_rate = float(group["stop_hit"].sum()) / denominator
        tone = "buy" if hit_2_rate > stop_rate and ready > 0 else "avoid" if stop_rate > hit_2_rate else "watch"
        rows.append(
            {
                "strategy_family": _text(strategy) or "Sin clasificar",
                "tracked": int(tracked),
                "ready": int(ready),
                "hit_2_rate": round(hit_2_rate, 4),
                "hit_5_rate": round(hit_5_rate, 4),
                "hit_10_rate": round(hit_10_rate, 4),
                "stop_rate": round(stop_rate, 4),
                "open": int((group["outcome"] == "OPEN").sum()),
                "tone": tone,
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["hit_2_rate", "stop_rate", "ready"], ascending=[False, True, False]
    )


def summarize_crypto_paper_practice_by_context(scored: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "symbol",
        "timeframe",
        "strategy_family",
        "data_source",
        "tracked",
        "ready",
        "hit_2_rate",
        "hit_5_rate",
        "hit_10_rate",
        "stop_rate",
        "open",
        "last_price",
        "tone",
    ]
    if scored.empty:
        return pd.DataFrame(columns=columns)
    data = scored.copy()
    for column, default in {
        "symbol": "-",
        "timeframe": "-",
        "strategy_family": "Sin clasificar",
        "data_source": "-",
    }.items():
        if column not in data.columns:
            data[column] = default
    rows: list[dict[str, Any]] = []
    group_cols = ["symbol", "timeframe", "strategy_family", "data_source"]
    for (symbol, timeframe, strategy, source), group in data.groupby(group_cols, dropna=False):
        tracked = len(group)
        ready = int((group["status"] == "READY_FOR_PAPER").sum()) if "status" in group else 0
        observed = group[group["outcome"].isin(["OPEN", "HIT_2", "HIT_5", "HIT_10", "STOP"])]
        denominator = max(len(observed), 1)
        hit_2_rate = float(group["hit_2pct"].sum()) / denominator
        hit_5_rate = float(group["hit_5pct"].sum()) / denominator
        hit_10_rate = float(group["hit_10pct"].sum()) / denominator
        stop_rate = float(group["stop_hit"].sum()) / denominator
        last_price = None
        if "current_price" in group.columns:
            current_values = pd.to_numeric(group["current_price"], errors="coerce").dropna()
            if not current_values.empty:
                last_price = float(current_values.iloc[-1])
        tone = "buy" if hit_2_rate > stop_rate and ready > 0 else "avoid" if stop_rate > hit_2_rate else "watch"
        rows.append(
            {
                "symbol": _text(symbol) or "-",
                "timeframe": _text(timeframe) or "-",
                "strategy_family": _text(strategy) or "Sin clasificar",
                "data_source": _text(source) or "-",
                "tracked": int(tracked),
                "ready": int(ready),
                "hit_2_rate": round(hit_2_rate, 4),
                "hit_5_rate": round(hit_5_rate, 4),
                "hit_10_rate": round(hit_10_rate, 4),
                "stop_rate": round(stop_rate, 4),
                "open": int((group["outcome"] == "OPEN").sum()),
                "last_price": round(last_price, 6) if last_price is not None else None,
                "tone": tone,
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["hit_2_rate", "stop_rate", "tracked"], ascending=[False, True, False]
    )


__all__ = [
    "DEFAULT_JOURNAL_PATH",
    "PRACTICE_COLUMNS",
    "SCORED_COLUMNS",
    "build_crypto_paper_practice_candidates",
    "close_and_save_crypto_paper_practice_journal",
    "close_crypto_paper_practice_journal",
    "load_crypto_paper_practice_journal",
    "price_lookup_from_crypto_opportunities",
    "record_crypto_paper_practice_candidates",
    "score_crypto_paper_practice_journal",
    "summarize_crypto_paper_practice",
    "summarize_crypto_paper_practice_by_context",
]
