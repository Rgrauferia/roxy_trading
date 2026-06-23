from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roxy_paths import data_dir


DEFAULT_NEWSLETTER_PATH = data_dir() / "weekly_newsletters.jsonl"

THEME_RULES: dict[str, dict[str, Any]] = {
    "ai_development": {
        "label": "IA / desarrollo",
        "keywords": ("inteligencia artificial", "ai", "nvidia", "chips", "semiconductor", "software", "cloud"),
        "symbols": ("NVDA", "AMD", "MSFT", "GOOGL", "META", "AMZN", "PLTR", "AVGO", "ARM", "TSM", "ASML", "MU", "SMCI", "CRWD", "NET", "SNOW", "MDB", "NOW", "AI"),
        "note": "Vigilar liderazgo en IA/desarrollo, pero solo operar si 1h confirma y 15m da entrada limpia.",
    },
    "crypto": {
        "label": "Cripto",
        "keywords": ("bitcoin", "ethereum", "crypto", "cripto", "blockchain", "stablecoin", "coinbase"),
        "symbols": ("BTC/USD", "ETH/USD", "SOL/USD", "COIN", "MSTR"),
        "note": "Cripto puede moverse 24h; Roxy debe exigir volumen, estructura y riesgo controlado.",
    },
    "rates_inflation": {
        "label": "Tasas / inflacion",
        "keywords": ("fed", "powell", "tasa", "tasas", "inflacion", "cpi", "pce", "empleo", "jobs", "bonos", "treasury", "yield"),
        "symbols": ("SPY", "QQQ", "IWM", "TLT", "XLF", "GLD", "DXY"),
        "note": "Riesgo macro: bajar agresividad antes de noticias y esperar confirmacion post-evento.",
    },
    "consumer": {
        "label": "Consumo / viajes",
        "keywords": ("bolsillo", "consumo", "consumer", "viajes", "mundial", "turismo", "retail", "familias"),
        "symbols": ("AMZN", "WMT", "COST", "DIS", "NFLX", "ABNB", "UBER", "V", "MA"),
        "note": "Puede afectar consumo y sentimiento; usarlo como contexto sectorial, no como entrada directa.",
    },
    "space_defense": {
        "label": "Espacio / defensa",
        "keywords": ("spacex", "space", "cohete", "satellite", "satelite", "defensa", "aerospace"),
        "symbols": ("TSLA", "RKLB", "LMT", "NOC", "ASTS"),
        "note": "Tema de momentum/noticia: buscar ruptura o pullback tecnico antes de considerar operacion.",
    },
    "global_risk": {
        "label": "Riesgo global",
        "keywords": ("guerra", "geopolit", "china", "mexico", "canada", "elecciones", "oil", "petroleo"),
        "symbols": ("SPY", "QQQ", "IWM", "USO", "XLE", "GLD"),
        "note": "Aumenta riesgo de gaps; priorizar stops claros y evitar perseguir velas extendidas.",
    },
}


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", safe_text(value).lower()).strip()


def extract_tickers(text: str) -> list[str]:
    tickers = re.findall(r"(?<![A-Z])[A-Z]{2,5}(?:/[A-Z]{3})?(?![A-Z])", text)
    ignored = {"USA", "USD", "TLS", "GMAIL", "HTML", "EE", "UU", "EU", "US"}
    return sorted({ticker for ticker in tickers if ticker not in ignored})


def analyze_newsletter_text(text: str) -> dict[str, Any]:
    raw = safe_text(text)
    normalized = normalize_text(raw)
    themes: list[dict[str, Any]] = []
    symbol_counter: Counter[str] = Counter()
    for key, rule in THEME_RULES.items():
        hits = [kw for kw in rule["keywords"] if kw in normalized]
        if not hits:
            continue
        for symbol in rule["symbols"]:
            symbol_counter[symbol] += len(hits)
        themes.append(
            {
                "theme": key,
                "label": rule["label"],
                "hits": hits[:8],
                "symbols": list(rule["symbols"]),
                "note": rule["note"],
            }
        )
    for ticker in extract_tickers(raw):
        symbol_counter[ticker] += 3
    watchlist = [symbol for symbol, _count in symbol_counter.most_common(30)]
    risk_level = "LOW"
    if any(item["theme"] in {"rates_inflation", "global_risk"} for item in themes):
        risk_level = "MEDIUM"
    if "fed" in normalized or "inflacion" in normalized or "cpi" in normalized or "powell" in normalized:
        risk_level = "HIGH"
    summary = "; ".join(item["label"] for item in themes[:5]) or "Sin tema accionable detectado"
    return {
        "summary": summary,
        "themes": themes,
        "watchlist_symbols": watchlist,
        "risk_level": risk_level,
        "rules": [
            "Usar newsletter como contexto macro/sectorial, no como BUY directo.",
            "Confirmar con estructura 1h, entrada 15m, volumen y riesgo antes de alertar.",
            "Si hay macro de alto impacto, esperar post-noticia o exigir confluencia mas fuerte.",
        ],
    }


def build_newsletter_record(
    *,
    source: str,
    subject: str,
    body: str,
    received_at: str | None = None,
) -> dict[str, Any]:
    analysis = analyze_newsletter_text(body)
    return {
        "ingested_at": now_iso(),
        "received_at": safe_text(received_at) or now_iso(),
        "source": safe_text(source) or "newsletter",
        "subject": safe_text(subject) or "Weekly market newsletter",
        "body_preview": safe_text(body)[:1200],
        "analysis": analysis,
    }


def append_newsletter(record: dict[str, Any], path: str | Path | None = None, *, max_records: int = 100) -> Path:
    target = Path(path or DEFAULT_NEWSLETTER_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = read_newsletters(target)
    fingerprint = f"{record.get('source')}|{record.get('subject')}|{record.get('received_at')}"
    existing = {f"{row.get('source')}|{row.get('subject')}|{row.get('received_at')}" for row in rows}
    if fingerprint not in existing:
        rows.append(record)
    rows = rows[-max_records:]
    target.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""))
    return target


def read_newsletters(path: str | Path | None = None) -> list[dict[str, Any]]:
    target = Path(path or DEFAULT_NEWSLETTER_PATH)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text().splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def newsletter_context(path: str | Path | None = None, *, limit: int = 3) -> dict[str, Any]:
    rows = read_newsletters(path)
    latest = rows[-limit:]
    symbol_counter: Counter[str] = Counter()
    themes: list[str] = []
    market_news: list[dict[str, Any]] = []
    risk = "LOW"
    for row in latest:
        analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
        for symbol in analysis.get("watchlist_symbols") or []:
            symbol_counter[safe_text(symbol)] += 1
        for item in analysis.get("themes") or []:
            if isinstance(item, dict) and item.get("label"):
                themes.append(safe_text(item.get("label")))
        if safe_text(analysis.get("risk_level")) == "HIGH":
            risk = "HIGH"
        elif safe_text(analysis.get("risk_level")) == "MEDIUM" and risk != "HIGH":
            risk = "MEDIUM"
        market_news.append(
            {
                "title": safe_text(row.get("subject")),
                "source": safe_text(row.get("source")),
                "timestamp": safe_text(row.get("received_at")),
                "summary": safe_text(analysis.get("summary")),
            }
        )
    top_symbols = [symbol for symbol, _count in symbol_counter.most_common(25) if symbol]
    unique_themes = list(dict.fromkeys(theme for theme in themes if theme))
    return {
        "configured": bool(rows),
        "path": str(Path(path or DEFAULT_NEWSLETTER_PATH)),
        "count": len(rows),
        "latest_count": len(latest),
        "label": "Newsletter semanal" if rows else "Sin newsletter",
        "detail": ", ".join(unique_themes[:4]) if unique_themes else "No hay newsletters guardadas.",
        "risk_level": risk if rows else "-",
        "themes": unique_themes[:10],
        "watchlist_symbols": top_symbols,
        "market_news": market_news,
        "usage_rule": "Contexto solamente: Roxy no debe comprar por una noticia sin confirmacion tecnica.",
    }
