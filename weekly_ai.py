# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from roxy_time import utc_now

import pandas as pd

# Shared notification layer.
try:
    from notifier import notify_if_changed
except Exception:
    notify_if_changed = None

ALERTS_DIR = Path("alerts")
ALERTS_DIR.mkdir(exist_ok=True)

FINNHUB_KEY = os.getenv("FINNHUB_KEY", "").strip()
WEEKLY_RESEARCH_CONTRACT = "roxy-weekly-research/1.0.0"

DEFAULT_STOCKS_100 = [
    # Mega/large + growth + cyclical (puedes cambiarla)
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "AVGO",
    "NFLX",
    "PLTR",
    "COIN",
    "SHOP",
    "UBER",
    "SNOW",
    "CRWD",
    "PANW",
    "NOW",
    "DDOG",
    "NET",
    "SMCI",
    "ARM",
    "TSM",
    "ASML",
    "INTC",
    "QCOM",
    "ADBE",
    "CRM",
    "ORCL",
    "IBM",
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "VTI",
    "VOO",
    "JPM",
    "BAC",
    "GS",
    "MS",
    "V",
    "MA",
    "PYPL",
    "XOM",
    "CVX",
    "SLB",
    "UNH",
    "LLY",
    "NVO",
    "PFE",
    "MRK",
    "WMT",
    "COST",
    "TGT",
    "KO",
    "PEP",
    "MCD",
    "SBUX",
    "CAT",
    "DE",
    "BA",
    "DIS",
    "CMCSA",
    "T",
    "VZ",
    "NKE",
    "LULU",
    "RIVN",
    "LCID",
    "ABNB",
    "BKNG",
    "MU",
    "TXN",
    "ADI",
    "SQ",
    "SOFI",
    "GE",
    "MMM",
    "GME",
    "AMC",  # meme-ish
    "RIOT",
    "MARA",  # crypto-related
    "F",
    "GM",
    "AXP",
    "BLK",
    "ETSY",
    "ROKU",
    "BABA",
    "JD",
    "PDD",
    "CVNA",
]


def safe_list_from_file(path: str) -> List[str]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(errors="ignore").splitlines():
        s = line.strip().upper()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def finnhub_news(symbol: str, days: int = 7, limit: int = 6) -> List[Dict[str, Any]]:
    if not FINNHUB_KEY:
        return []
    import requests

    end = utc_now().date()
    start = end - timedelta(days=days)
    url = "https://finnhub.io/api/v1/company-news"
    params = {"symbol": symbol, "from": str(start), "to": str(end), "token": FINNHUB_KEY}
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return []
        items = r.json() or []
        # limpia y limita
        out = []
        for it in items[:limit]:
            out.append(
                {
                    "headline": it.get("headline", ""),
                    "source": it.get("source", ""),
                    "url": it.get("url", ""),
                    "datetime": it.get("datetime", 0),
                }
            )
        return out
    except Exception:
        return []


def news_score(news: List[Dict[str, Any]]) -> int:
    """
    Score simple por cantidad de noticias recientes.
    (Luego le metemos sentimiento real cuando quieras.)
    """
    if not news:
        return 0
    n = len(news)
    if n >= 6:
        return 20
    if n >= 4:
        return 14
    if n >= 2:
        return 8
    return 4


def classify_horizon(signal: str, score: int) -> str:
    s = (signal or "").upper()
    # corto plazo si hay momentum alto o señal fuerte
    if s in ("BUY", "PRE-BUY") and score >= 55:
        return "CORTO (horas–días)"
    if score >= 60:
        return "LARGO (semanas–meses)"
    if score >= 40:
        return "MIXTO"
    return "OBSERVAR"


def weekly_technical_snapshot(
    symbol: str,
    *,
    history_fetcher: Callable[..., tuple[pd.DataFrame, dict[str, Any]]] | None = None,
    setup_scorer: Callable[[pd.DataFrame], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one weekly research row without importing the legacy Streamlit app."""
    if history_fetcher is None:
        from symbol_detail import fetch_symbol_history_with_source

        history_fetcher = fetch_symbol_history_with_source
    if setup_scorer is None:
        from roxy_scanner import add_indicators, score_setup

        def setup_scorer(frame: pd.DataFrame) -> dict[str, Any]:
            return score_setup(add_indicators(frame))

    frame, source = history_fetcher(
        symbol,
        market="stock",
        timeframe="1d",
        include_extended_hours=False,
    )
    if frame is None or frame.empty or len(frame) < 80:
        return {
            "status": "NO_DATA",
            "symbol": symbol,
            "detail": f"Historial diario insuficiente ({0 if frame is None else len(frame)} filas).",
            "source": source if isinstance(source, dict) else {},
        }
    setup = setup_scorer(frame)
    score = int(max(0, min(100, float(setup.get("score") or 0))))
    signal = "BUY" if score >= 70 else "PRE-BUY" if score >= 55 else "WATCH" if score >= 35 else "AVOID"
    source = dict(source) if isinstance(source, dict) else {}
    fallback = bool(source.get("fallback")) or str(source.get("mode") or "").upper() in {
        "FALLBACK",
        "DELAYED",
        "CACHE",
    }
    return {
        "status": "OK",
        "symbol": symbol,
        "signal": signal,
        "score": score,
        "levels": {key: setup.get(key) for key in ("entry", "stop", "tp1", "tp2")},
        "reasons": list(setup.get("reasons") or [])[:6],
        "source": source,
        "data_provider": source.get("provider") or source.get("label") or "No identificado",
        "data_mode": source.get("mode") or "NO_DATA",
        "data_fallback": fallback,
        # A weekly batch is research. Even premium daily history must pass the
        # live smart-alert gates elsewhere before becoming actionable.
        "alert_eligible": False,
        "usage": "RESEARCH_ONLY_FALLBACK" if fallback else "RESEARCH_ONLY",
    }


def run_weekly(
    symbols: List[str],
    *,
    history_fetcher: Callable[..., tuple[pd.DataFrame, dict[str, Any]]] | None = None,
    setup_scorer: Callable[[pd.DataFrame], dict[str, Any]] | None = None,
    news_fetcher: Callable[..., List[Dict[str, Any]]] = finnhub_news,
) -> Dict[str, Any]:
    results = []
    skipped = []
    for sym in symbols:
        try:
            technical = weekly_technical_snapshot(
                sym,
                history_fetcher=history_fetcher,
                setup_scorer=setup_scorer,
            )
        except Exception as exc:
            skipped.append({"symbol": sym, "status": "ERROR", "detail": type(exc).__name__})
            continue
        if technical.get("status") != "OK":
            skipped.append(technical)
            continue
        signal = str(technical["signal"])
        score = int(technical["score"])
        nw = news_fetcher(sym, days=7, limit=6)
        nscore = news_score(nw)

        # ranking combinado (70% técnica + 30% noticias)
        rank = (0.70 * score) + (0.30 * min(100, nscore * 5))

        results.append(
            {
                "symbol": sym,
                "signal": signal,
                "score": int(score),
                "rank": float(rank),
                "horizon": classify_horizon(signal, score),
                "levels": technical["levels"],
                "reasons": technical["reasons"],
                "news": nw,
                "source": technical["source"],
                "data_provider": technical["data_provider"],
                "data_mode": technical["data_mode"],
                "data_fallback": technical["data_fallback"],
                "alert_eligible": technical["alert_eligible"],
                "usage": technical["usage"],
            }
        )

    results.sort(key=lambda x: x["rank"], reverse=True)

    top_short = [r for r in results if r["horizon"].startswith("CORTO")][:12]
    top_long = [r for r in results if r["horizon"].startswith("LARGO")][:12]
    top_all = results[:20]

    payload = {
        "contract_version": WEEKLY_RESEARCH_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "OK" if results else "NO_DATA",
        "total_scanned": len(symbols),
        "total_analyzed": len(results),
        "total_skipped": len(skipped),
        "skipped": skipped,
        "top_all": top_all,
        "top_short": top_short,
        "top_long": top_long,
    }
    return payload


def to_text(payload: Dict[str, Any]) -> str:
    def line(r):
        lvl = r.get("levels") or {}
        provenance = f"{r.get('data_provider', 'No identificado')} / {r.get('data_mode', 'NO_DATA')} / {r.get('usage', 'RESEARCH_ONLY')}"
        return (
            f"{r['symbol']} | {r['signal']} | Score {r['score']} | Rank {r['rank']:.2f} | {r['horizon']} | "
            f"Entry {lvl.get('entry','—'):.2f} TP2 {lvl.get('tp2','—'):.2f} | {provenance}"
            if isinstance(lvl.get("entry"), (int, float)) and isinstance(lvl.get("tp2"), (int, float))
            else f"{r['symbol']} | {r['signal']} | Score {r['score']} | Rank {r['rank']:.2f} | {r['horizon']} | {provenance}"
        )

    out = []
    out.append("🧠 ROXY WEEKLY OPPORTUNITIES\n")
    out.append(f"Generated: {payload.get('generated_at')}")
    out.append(
        f"Contract: {payload.get('contract_version')} | Status: {payload.get('status')} | "
        f"Scanned: {payload.get('total_scanned')} | Analyzed: {payload.get('total_analyzed')} | "
        f"Skipped: {payload.get('total_skipped')}\n"
    )

    out.append("🏆 TOP ALL (20)")
    for r in payload.get("top_all", [])[:20]:
        out.append("• " + line(r))

    out.append("\n⚡ TOP SHORT (Corto plazo)")
    for r in payload.get("top_short", [])[:12]:
        out.append("• " + line(r))

    out.append("\n🌱 TOP LONG (Largo plazo)")
    for r in payload.get("top_long", [])[:12]:
        out.append("• " + line(r))

    return "\n".join(out)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main():
    # si tienes archivo stock_symbols.txt lo usa; si no usa default 100
    syms = safe_list_from_file("stock_symbols.txt")
    if not syms:
        syms = DEFAULT_STOCKS_100

    payload = run_weekly(syms)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jpath = ALERTS_DIR / f"weekly_report_{ts}.json"
    tpath = ALERTS_DIR / f"weekly_report_{ts}.txt"

    atomic_write_text(jpath, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    atomic_write_text(tpath, to_text(payload))

    # Summarized alert through the configured notifier channels.
    if notify_if_changed:
        # Send only the TOP 5 from top_all.
        top = payload.get("top_all", [])[:5]
        alerts = [
            f"WEEKLY {r['symbol']} {r['signal']} | Score {r['score']} | Rank {r['rank']:.2f} | {r['horizon']}"
            for r in top
            if r.get("alert_eligible") is True
        ]
        if alerts:
            notify_if_changed(alerts)

    print("✅ Weekly report saved:")
    print("  ", jpath)
    print("  ", tpath)


if __name__ == "__main__":
    main()
