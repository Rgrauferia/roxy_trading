from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from alpaca_paper_practice import (
    close_alpaca_paper_practice_journal,
    load_alpaca_paper_practice_journal,
)
from crypto_paper_practice import (
    close_crypto_paper_practice_journal,
    load_crypto_paper_practice_journal,
)


DEFAULT_REPORT_PATH = Path("alerts/paper_result_closer.json")
CLOSEABLE_STATUSES = {"READY_FOR_PAPER", "OPEN", "OBSERVING", ""}


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


def _is_open_closeable(row: Mapping[str, Any]) -> bool:
    status = _text(row.get("status")).upper()
    if status.startswith("CLOSED_") or _text(row.get("closed_outcome")):
        return False
    if status not in CLOSEABLE_STATUSES:
        return False
    entry = _float(row.get("entry"))
    stop = _float(row.get("stop"))
    return entry is not None and entry > 0 and stop is not None and stop > 0


def open_paper_symbols(journal: pd.DataFrame, *, market: str) -> list[str]:
    if journal.empty:
        return []
    symbols: set[str] = set()
    for row in journal.to_dict("records"):
        if not _is_open_closeable(row):
            continue
        symbol = _text(row.get("symbol")).upper()
        row_market = _text(row.get("market")).lower()
        if not symbol:
            continue
        if market == "crypto":
            if row_market == "crypto" or "/" in symbol:
                symbols.add(symbol)
        else:
            if row_market != "crypto" and "/" not in symbol:
                symbols.add(symbol)
    return sorted(symbols)


def live_price_lookup_for_symbols(
    symbols: list[str],
    *,
    market: str,
    fetcher: Callable[[str, str], Mapping[str, Any]],
    max_symbols: int = 25,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    lookup: dict[str, float] = {}
    diagnostics: list[dict[str, Any]] = []
    for symbol in symbols[: max(0, int(max_symbols or 0))]:
        try:
            snapshot = dict(fetcher(symbol, market))
        except Exception as exc:
            diagnostics.append(
                {
                    "symbol": symbol,
                    "market": market,
                    "status": "FAIL",
                    "price": None,
                    "source": "fetcher",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        price = _float(snapshot.get("price"))
        status = "OK" if price is not None and price > 0 else "FAIL"
        diagnostics.append(
            {
                "symbol": symbol,
                "market": market,
                "status": status,
                "price": price,
                "freshness": snapshot.get("freshness"),
                "source": snapshot.get("source"),
                "source_mode": snapshot.get("source_mode"),
                "price_timestamp": snapshot.get("price_timestamp"),
                "detail": snapshot.get("latency_note") or snapshot.get("error") or "",
            }
        )
        if status != "OK":
            continue
        lookup[symbol] = float(price)
        if market == "crypto" and "/" in symbol:
            lookup[symbol.replace("/", "")] = float(price)
    return lookup, diagnostics


def _closed_count(journal: pd.DataFrame) -> int:
    if journal.empty or "closed_outcome" not in journal.columns:
        return 0
    return int(journal["closed_outcome"].map(lambda value: bool(_text(value))).sum())


def close_paper_results_with_live_prices(
    *,
    alpaca_path: str | Path = "alerts/alpaca_paper_practice.csv",
    crypto_path: str | Path = "alerts/crypto_paper_practice.csv",
    report_path: str | Path = DEFAULT_REPORT_PATH,
    fetcher: Callable[[str, str], Mapping[str, Any]] | None = None,
    max_symbols: int = 25,
    now: datetime | None = None,
) -> dict[str, Any]:
    if fetcher is None:
        from living_market import build_live_price_snapshot

        fetcher = lambda symbol, market: build_live_price_snapshot(symbol, market)

    current_time = now or datetime.now(timezone.utc)
    alpaca_journal = load_alpaca_paper_practice_journal(alpaca_path)
    crypto_journal = load_crypto_paper_practice_journal(crypto_path)
    before_alpaca = _closed_count(alpaca_journal)
    before_crypto = _closed_count(crypto_journal)

    stock_symbols = open_paper_symbols(alpaca_journal, market="stock")
    crypto_symbols = open_paper_symbols(crypto_journal, market="crypto")
    stock_lookup, stock_diagnostics = live_price_lookup_for_symbols(
        stock_symbols,
        market="stock",
        fetcher=fetcher,
        max_symbols=max_symbols,
    )
    crypto_lookup, crypto_diagnostics = live_price_lookup_for_symbols(
        crypto_symbols,
        market="crypto",
        fetcher=fetcher,
        max_symbols=max_symbols,
    )

    closed_alpaca = (
        close_alpaca_paper_practice_journal(alpaca_journal, price_lookup=stock_lookup, now=current_time)
        if not alpaca_journal.empty
        else alpaca_journal
    )
    closed_crypto = (
        close_crypto_paper_practice_journal(crypto_journal, price_lookup=crypto_lookup, now=current_time)
        if not crypto_journal.empty
        else crypto_journal
    )

    if not closed_alpaca.empty:
        alpaca_output = Path(alpaca_path)
        alpaca_output.parent.mkdir(parents=True, exist_ok=True)
        closed_alpaca.to_csv(alpaca_output, index=False)
    if not closed_crypto.empty:
        crypto_output = Path(crypto_path)
        crypto_output.parent.mkdir(parents=True, exist_ok=True)
        closed_crypto.to_csv(crypto_output, index=False)

    after_alpaca = _closed_count(closed_alpaca)
    after_crypto = _closed_count(closed_crypto)
    report = {
        "generated_at": current_time.isoformat(),
        "paper_only": True,
        "real_orders_enabled": False,
        "stock_symbols_checked": len(stock_symbols[:max_symbols]),
        "crypto_symbols_checked": len(crypto_symbols[:max_symbols]),
        "stock_price_count": len(stock_lookup),
        "crypto_price_count": len(crypto_lookup),
        "alpaca_closed_before": before_alpaca,
        "alpaca_closed_after": after_alpaca,
        "alpaca_newly_closed": max(0, after_alpaca - before_alpaca),
        "crypto_closed_before": before_crypto,
        "crypto_closed_after": after_crypto,
        "crypto_newly_closed": max(0, after_crypto - before_crypto),
        "newly_closed_total": max(0, after_alpaca - before_alpaca) + max(0, after_crypto - before_crypto),
        "diagnostics": stock_diagnostics + crypto_diagnostics,
    }
    output = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


__all__ = [
    "CLOSEABLE_STATUSES",
    "close_paper_results_with_live_prices",
    "live_price_lookup_for_symbols",
    "open_paper_symbols",
]
