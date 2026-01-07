# -*- coding: utf-8 -*-
import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

# Reusa tu lógica si la tienes en dashboard/app; si no, usamos helpers simples
try:
    from dashboard import (  # si existe tu dashboard.py v2
        fetch_stocks,
        opportunity_engine,
    )
except Exception:
    fetch_stocks = None
    opportunity_engine = None

# Telegram notifier (ya lo creaste)
try:
    from notifier import notify_if_changed
except Exception:
    notify_if_changed = None

ALERTS_DIR = Path("alerts")
ALERTS_DIR.mkdir(exist_ok=True)

FINNHUB_KEY = os.getenv("FINNHUB_KEY", "").strip()

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

    end = datetime.utcnow().date()
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


def run_weekly(symbols: List[str]) -> Dict[str, Any]:
    results = []
    for sym in symbols:
        if fetch_stocks is None or opportunity_engine is None:
            continue

        df = fetch_stocks(sym, "1d")  # semanal enfocado en daily
        if df is None or df.empty or len(df) < 80:
            continue

        signal, score, reasons, levels = opportunity_engine(df)

        nw = finnhub_news(sym, days=7, limit=6)
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
                "levels": levels,
                "reasons": reasons[:6],
                "news": nw,
            }
        )

    results.sort(key=lambda x: x["rank"], reverse=True)

    top_short = [r for r in results if r["horizon"].startswith("CORTO")][:12]
    top_long = [r for r in results if r["horizon"].startswith("LARGO")][:12]
    top_all = results[:20]

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_scanned": len(symbols),
        "top_all": top_all,
        "top_short": top_short,
        "top_long": top_long,
    }
    return payload


def to_text(payload: Dict[str, Any]) -> str:
    def line(r):
        lvl = r.get("levels") or {}
        return (
            f"{r['symbol']} | {r['signal']} | Score {r['score']} | Rank {r['rank']:.2f} | {r['horizon']} | "
            f"Entry {lvl.get('entry','—'):.2f} TP2 {lvl.get('tp2','—'):.2f}"
            if isinstance(lvl.get("entry"), (int, float)) and isinstance(lvl.get("tp2"), (int, float))
            else f"{r['symbol']} | {r['signal']} | Score {r['score']} | Rank {r['rank']:.2f} | {r['horizon']}"
        )

    out = []
    out.append("🧠 ROXY WEEKLY OPPORTUNITIES\n")
    out.append(f"Generated: {payload.get('generated_at')}")
    out.append(f"Scanned : {payload.get('total_scanned')}\n")

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


def main():
    # si tienes archivo stock_symbols.txt lo usa; si no usa default 100
    syms = safe_list_from_file("stock_symbols.txt")
    if not syms:
        syms = DEFAULT_STOCKS_100

    payload = run_weekly(syms)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jpath = ALERTS_DIR / f"weekly_report_{ts}.json"
    tpath = ALERTS_DIR / f"weekly_report_{ts}.txt"

    jpath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tpath.write_text(to_text(payload), encoding="utf-8")

    # alerta resumida a telegram
    if notify_if_changed:
        # manda solo el TOP 5 del “top_all”
        top = payload.get("top_all", [])[:5]
        alerts = [
            f"WEEKLY {r['symbol']} {r['signal']} | Score {r['score']} | Rank {r['rank']:.2f} | {r['horizon']}"
            for r in top
        ]
        notify_if_changed(alerts)

    print("✅ Weekly report saved:")
    print("  ", jpath)
    print("  ", tpath)


if __name__ == "__main__":
    main()
