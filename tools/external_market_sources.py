"""Safe external market source connectors for Roxy.

These connectors normalize external data without exposing secrets and without
placing orders. They are meant to enrich Roxy's market context, not to execute.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Callable, Iterable, Optional


DEFAULT_CRYPTOCOM_BASE_URL = "https://api.crypto.com/exchange/v1"
DEFAULT_CRYPTOCOM_INSTRUMENTS = ("BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT", "BNB_USDT", "DOGE_USDT")
DEFAULT_FINVIZ_EXPORT_BASE_URL = "https://elite.finviz.com/export/screener"
DEFAULT_FINVIZ_EXPORT_PARAMS = {
    "v": "111",
    "ft": "4",
}
BULLISH_SOURCE_WORDS = {
    "BUY",
    "BULL",
    "BULLISH",
    "BREAKOUT",
    "UPGRADE",
    "ACCUMULATION",
    "MOMENTUM",
    "STRONG",
}
BEARISH_SOURCE_WORDS = {
    "SELL",
    "BEAR",
    "BEARISH",
    "BREAKDOWN",
    "DOWNGRADE",
    "DISTRIBUTION",
    "SHORT",
    "WEAK",
}
FINVIZ_PULSE_SIGNAL_FIELDS = (
    "Signal",
    "signal",
    "Pattern",
    "pattern",
    "Recommendation",
    "recommendation",
    "News",
    "news",
)
FINVIZ_PULSE_RAW_FIELDS = (
    "Company",
    "Sector",
    "Industry",
    "Country",
    "Market Cap",
    "P/E",
    "Forward P/E",
    "PEG",
    "EPS this Y",
    "EPS next Y",
    "Sales past 5Y",
    "EPS past 5Y",
    "Insider Own",
    "Insider Trans",
    "Inst Own",
    "Inst Trans",
    "Float Short",
    "Short Ratio",
    "Perf Week",
    "Perf Month",
    "Perf Quarter",
    "Perf Half Y",
    "Perf Year",
    "Perf YTD",
    "Volatility W",
    "Volatility M",
    "Rel Volume",
    "Avg Volume",
    "Volume",
    "Target Price",
    "RSI (14)",
    "SMA20",
    "SMA50",
    "SMA200",
    "52W High",
    "52W Low",
    "Earnings",
)
FINVIZ_PATTERN_STRATEGIES: dict[str, dict[str, Any]] = {
    "TL SUPP": {
        "family": "Trendline Support",
        "bias": "ARRIBA",
        "playbook": "Comprar solo cerca de la linea de tendencia/soporte si aparece rebote confirmado.",
        "entry_zone": "Cerca de soporte dinamico",
        "target_zone": "Media del canal o resistencia previa",
        "stop_zone": "Debajo de la linea de soporte",
    },
    "TL RESIST": {
        "family": "Trendline Resistance",
        "bias": "ABAJO",
        "playbook": "Vender/evitar compra cerca de resistencia si aparece rechazo; comprar solo si rompe con volumen.",
        "entry_zone": "Rechazo en resistencia o ruptura confirmada",
        "target_zone": "Soporte cercano",
        "stop_zone": "Encima de la linea de resistencia",
    },
    "HORIZONTAL S/R": {
        "family": "Horizontal Support/Resistance",
        "bias": "RANGO",
        "playbook": "Operar rebotes entre soporte y resistencia; no perseguir en la mitad del rango.",
        "entry_zone": "Compra cerca del soporte; venta cerca de resistencia",
        "target_zone": "Lado opuesto del rango",
        "stop_zone": "Fuera del rango confirmado",
    },
    "WEDGE UP": {
        "family": "Rising Wedge",
        "bias": "ABAJO",
        "playbook": "Patron de compresion alcista con riesgo de ruptura bajista; esperar rechazo arriba o ruptura abajo.",
        "entry_zone": "Cerca de resistencia para rechazo o bajo soporte tras ruptura",
        "target_zone": "Base del wedge",
        "stop_zone": "Encima del ultimo maximo dentro del wedge",
    },
    "WEDGE DOWN": {
        "family": "Falling Wedge",
        "bias": "ARRIBA",
        "playbook": "Patron de compresion bajista con posible ruptura alcista; esperar rebote cerca de soporte o breakout.",
        "entry_zone": "Cerca de soporte con rebote o ruptura sobre resistencia",
        "target_zone": "Parte alta del wedge",
        "stop_zone": "Debajo del ultimo minimo dentro del wedge",
    },
    "WEDGE": {
        "family": "Wedge",
        "bias": "COMPRESION",
        "playbook": "Buscar entrada cerca de una linea del wedge y salida antes de la linea contraria; reducir tamano al cerrarse.",
        "entry_zone": "Extremos del wedge, no en el centro",
        "target_zone": "Linea contraria del wedge",
        "stop_zone": "Fuera del wedge",
    },
    "TRIANGLE ASC": {
        "family": "Ascending Triangle",
        "bias": "ARRIBA",
        "playbook": "Preferir compra cerca de soporte ascendente o breakout sobre resistencia horizontal con volumen.",
        "entry_zone": "Soporte ascendente o ruptura sobre techo",
        "target_zone": "Techo del triangulo y extension del breakout",
        "stop_zone": "Debajo del ultimo minimo ascendente",
    },
    "TRIANGLE DESC": {
        "family": "Descending Triangle",
        "bias": "ABAJO",
        "playbook": "Preferir venta/rechazo cerca de resistencia descendente o ruptura bajo soporte horizontal.",
        "entry_zone": "Resistencia descendente o ruptura bajo piso",
        "target_zone": "Piso del triangulo y extension bajista",
        "stop_zone": "Encima del ultimo maximo descendente",
    },
    "CHANNEL UP": {
        "family": "Ascending Channel",
        "bias": "ARRIBA",
        "playbook": "Comprar rebotes cerca de la linea inferior; tomar ganancias cerca de la linea superior.",
        "entry_zone": "Linea inferior del canal",
        "target_zone": "Linea superior del canal",
        "stop_zone": "Debajo de la linea inferior",
    },
    "CHANNEL DOWN": {
        "family": "Descending Channel",
        "bias": "ABAJO",
        "playbook": "Vender/reducir cerca de la linea superior; cubrir o tomar ganancia cerca de la linea inferior.",
        "entry_zone": "Linea superior del canal",
        "target_zone": "Linea inferior del canal",
        "stop_zone": "Encima de la linea superior",
    },
    "CHANNEL": {
        "family": "Price Channel",
        "bias": "RANGO",
        "playbook": "Operar extremos del canal; evitar entradas en el centro.",
        "entry_zone": "Extremo inferior para compra o extremo superior para venta",
        "target_zone": "Extremo contrario del canal",
        "stop_zone": "Fuera del canal",
    },
    "DOUBLE BOTTOM": {
        "family": "Double Bottom",
        "bias": "ARRIBA",
        "playbook": "Esperar confirmacion sobre neckline; compra anticipada solo si el segundo piso rebota con volumen.",
        "entry_zone": "Segundo rebote o ruptura de neckline",
        "target_zone": "Altura del patron proyectada",
        "stop_zone": "Debajo del doble piso",
    },
    "DOUBLE TOP": {
        "family": "Double Top",
        "bias": "ABAJO",
        "playbook": "Esperar rechazo del segundo techo o ruptura bajo neckline.",
        "entry_zone": "Segundo rechazo o ruptura del neckline",
        "target_zone": "Altura del patron proyectada hacia abajo",
        "stop_zone": "Encima del doble techo",
    },
    "MULTIPLE BOTTOM": {
        "family": "Multiple Bottom",
        "bias": "ARRIBA",
        "playbook": "Zona de acumulacion; buscar rebotes repetidos con volumen antes de comprar.",
        "entry_zone": "Zona de soporte repetida",
        "target_zone": "Resistencia del rango",
        "stop_zone": "Debajo del soporte multiple",
    },
    "MULTIPLE TOP": {
        "family": "Multiple Top",
        "bias": "ABAJO",
        "playbook": "Zona de distribucion; evitar compras tardias y buscar rechazo o ruptura bajista.",
        "entry_zone": "Rechazo cerca de techo multiple",
        "target_zone": "Soporte del rango",
        "stop_zone": "Encima del techo multiple",
    },
    "HEAD&SHOULDERS": {
        "family": "Head and Shoulders",
        "bias": "ABAJO",
        "playbook": "Esperar ruptura de neckline; no entrar antes si no hay confirmacion.",
        "entry_zone": "Ruptura o pullback al neckline",
        "target_zone": "Proyeccion cabeza-neckline",
        "stop_zone": "Encima del hombro derecho",
    },
}
FINVIZ_NEWS_SIGNAL_CATEGORIES: dict[str, tuple[str, str]] = {
    "MAJOR NEWS": ("Major News", "Movimiento destacado por noticias importantes en Finviz."),
    "LATEST NEWS": ("Latest News", "Noticia reciente detectada en Finviz."),
    "NEWS": ("News", "Ticker activo en el feed de noticias de Finviz."),
    "EARNINGS AFTER": ("Earnings After", "Reporte de resultados programado despues del cierre."),
    "EARNINGS BEFORE": ("Earnings Before", "Reporte de resultados programado antes de la apertura."),
    "UPGRADES": ("Upgrades", "Analistas mejoraron la calificacion o precio objetivo."),
    "DOWNGRADES": ("Downgrades", "Analistas redujeron la calificacion o precio objetivo."),
    "INSIDER BUYING": ("Insider Buying", "Compras internas reportadas por directivos o insiders."),
    "INSIDER SELLING": ("Insider Selling", "Ventas internas reportadas por directivos o insiders."),
    "UNUSUAL VOLUME": ("Unusual Volume", "Volumen inusual que puede anticipar expansion de volatilidad."),
    "MOST ACTIVE": ("Most Active", "Ticker entre los mas activos del mercado."),
    "LATEST FILINGS": ("Latest Filings", "Nuevo documento o filing disponible."),
}


@dataclass(frozen=True)
class ExternalSourceStatus:
    provider: str
    configured: bool
    mode: str
    status: str
    detail: str
    next_action: str
    present_keys: tuple[str, ...] = ()
    missing_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedMarketRow:
    source: str
    symbol: str
    market: str
    price: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    signal: str = ""
    source_url: str = ""
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Transport = Callable[[str, Optional[bytes], dict[str, str]], str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_secret(value: Any, *, keep: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= keep * 2:
        return "*" * len(text)
    return f"{text[:keep]}...{text[-keep:]}"


def redact_url(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlsplit(value)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = []
    for key, raw in query:
        if key.lower() in {"auth", "token", "api_key", "apikey", "secret", "passphrase"}:
            redacted.append((key, mask_secret(raw)))
        else:
            redacted.append((key, raw))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment)
    )


def _default_transport(url: str, body: bytes | None, headers: dict[str, str]) -> str:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read().decode("utf-8", errors="replace")


def _env_value(env: dict[str, str], *keys: str) -> tuple[str, str]:
    for key in keys:
        value = str(env.get(key) or "").strip()
        if value:
            return value, key
    return "", ""


def _float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text in {"-", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_symbol_for_match(symbol: Any, market: str | None = None) -> str:
    """Normalize symbols so BTC/USD, BTC_USDT and BTCUSDT match safely."""
    text = str(symbol or "").strip().upper()
    if not text:
        return ""
    normalized = "".join(ch for ch in text if ch.isalnum())
    if not normalized:
        return ""
    if (market or "").lower() == "crypto" and normalized.endswith("USD") and not normalized.endswith("USDT"):
        return f"{normalized}T"
    return normalized


def _row_dict(row: NormalizedMarketRow | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, NormalizedMarketRow):
        return row.to_dict()
    return dict(row or {})


def rows_by_symbol(
    rows: Iterable[NormalizedMarketRow | dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        item = _row_dict(row)
        key = normalize_symbol_for_match(item.get("symbol"), item.get("market"))
        if not key:
            continue
        grouped.setdefault(key, []).append(item)
    return grouped


def _opportunity_direction(opportunity: dict[str, Any]) -> str:
    signal = str(opportunity.get("signal") or "").strip().upper()
    decision = str(opportunity.get("trade_decision") or opportunity.get("decision") or "").strip().upper()
    setup = str(opportunity.get("setup") or opportunity.get("trigger_setup") or "").strip().upper()
    option_side = str(opportunity.get("option_side") or opportunity.get("contract_type") or "").strip().upper()
    joined = " ".join(part for part in (signal, decision, setup, option_side) if part)
    if any(token in joined for token in ("SELL", "SHORT", "PUT", "ABAJO", "DOWN", "NO ABOVE")):
        return "ABAJO"
    if any(token in joined for token in ("BUY", "WATCH", "CALL", "LONG", "ARRIBA", "UP", "YES")):
        return "ARRIBA"
    return "SIN_DIRECCION"


def _source_signal_bias(signal: Any) -> str:
    text = str(signal or "").upper()
    if any(word in text for word in BEARISH_SOURCE_WORDS):
        return "ABAJO"
    if any(word in text for word in BULLISH_SOURCE_WORDS):
        return "ARRIBA"
    return "NEUTRAL"


def _raw_get(raw: dict[str, Any] | None, *keys: str) -> Any:
    if not raw:
        return None
    for key in keys:
        if key in raw and raw.get(key) not in (None, ""):
            return raw.get(key)
    lower = {str(key).lower(): value for key, value in raw.items()}
    for key in keys:
        value = lower.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def _first_raw_value(raw: dict[str, Any] | None, keys: Iterable[str]) -> str:
    value = _raw_get(raw, *tuple(keys))
    return str(value or "").strip()


def _safe_row_symbol(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("ticker") or "").strip().upper()


def _finviz_row_signal(row: dict[str, Any]) -> str:
    signal = str(row.get("signal") or "").strip()
    if signal:
        return signal
    return _first_raw_value(row.get("raw") if isinstance(row.get("raw"), dict) else {}, FINVIZ_PULSE_SIGNAL_FIELDS)


def _finviz_pulse_item(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    return {
        "symbol": _safe_row_symbol(row),
        "price": _float(row.get("price")),
        "change_pct": _float(row.get("change_pct")),
        "volume": _float(row.get("volume")),
        "signal": _finviz_row_signal(row),
        "bias": _source_signal_bias(_finviz_row_signal(row)),
        "company": _raw_get(raw, "Company", "company"),
        "sector": _raw_get(raw, "Sector", "sector"),
        "industry": _raw_get(raw, "Industry", "industry"),
        "relative_volume": _float(_raw_get(raw, "Rel Volume", "relative_volume")),
        "perf_week": _float(_raw_get(raw, "Perf Week", "perf_week")),
        "perf_month": _float(_raw_get(raw, "Perf Month", "perf_month")),
    }


def _canonical_finviz_pattern(signal: Any) -> str:
    text = str(signal or "").upper().replace(".", "").replace("/", " ")
    text = " ".join(text.split())
    if not text:
        return ""
    replacements = {
        "TL SUPP": "TL SUPP",
        "TL SUPPORT": "TL SUPP",
        "TL RESIST": "TL RESIST",
        "TL RESISTANCE": "TL RESIST",
        "HORIZONTAL S R": "HORIZONTAL S/R",
        "HORIZONTAL SR": "HORIZONTAL S/R",
        "TRIANGLE ASC": "TRIANGLE ASC",
        "TRIANGLE ASCENDING": "TRIANGLE ASC",
        "TRIANGLE DESC": "TRIANGLE DESC",
        "TRIANGLE DESCENDING": "TRIANGLE DESC",
        "HEAD SHOULDERS": "HEAD&SHOULDERS",
        "HEAD AND SHOULDERS": "HEAD&SHOULDERS",
    }
    if text in replacements:
        return replacements[text]
    for key in sorted(FINVIZ_PATTERN_STRATEGIES, key=len, reverse=True):
        normalized_key = key.replace(".", "").replace("/", " ")
        if normalized_key in text:
            return key
    return text


def _canonical_finviz_news_signal(signal: Any) -> str:
    text = str(signal or "").upper().replace("_", " ").replace("-", " ").replace(".", " ")
    text = " ".join(text.split())
    if not text:
        return ""
    for key in sorted(FINVIZ_NEWS_SIGNAL_CATEGORIES, key=len, reverse=True):
        if key in text:
            return key
    return ""


def _direction_from_pattern_and_change(pattern: dict[str, Any], change_pct: float | None) -> str:
    bias = str(pattern.get("bias") or "").upper()
    if bias == "RANGO":
        return "COMPRAR_SOPORTE_VENDER_RESISTENCIA"
    if bias == "COMPRESION":
        return "ESPERAR_EXTREMO_O_RUPTURA"
    if bias == "ARRIBA":
        return "COMPRAR"
    if bias == "ABAJO":
        return "VENDER_EVITAR_COMPRA"
    if change_pct is not None and change_pct > 0:
        return "COMPRAR_SOLO_SI_CONFIRMA"
    if change_pct is not None and change_pct < 0:
        return "VENDER_SOLO_SI_CONFIRMA"
    return "ESPERAR_CONFIRMACION"


def _pattern_confidence(item: dict[str, Any], pattern: dict[str, Any]) -> int:
    score = 52
    change_pct = abs(_float(item.get("change_pct")) or 0.0)
    rel_volume = _float(item.get("relative_volume"))
    volume = _float(item.get("volume"))
    if change_pct >= 1.0:
        score += 7
    if change_pct >= 3.0:
        score += 6
    if rel_volume is not None and rel_volume >= 1.5:
        score += 8
    elif volume is not None and volume > 0:
        score += 3
    if str(pattern.get("bias") or "").upper() in {"ARRIBA", "ABAJO", "RANGO", "COMPRESION"}:
        score += 5
    return int(max(0, min(94, score)))


def build_finviz_pattern_strategies(
    rows: Iterable[NormalizedMarketRow | dict[str, Any]],
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Translate Finviz pattern labels into Roxy operating playbooks.

    Finviz labels identify the chart pattern. This function converts those
    labels into a structured plan, but leaves exact entry/stop/target as
    conditional until the live chart adapter confirms the lines.
    """
    strategies: list[dict[str, Any]] = []
    for raw_row in rows:
        row = _row_dict(raw_row)
        if str(row.get("market") or "").lower() != "stock" and str(row.get("source") or "") != "Finviz Elite":
            continue
        item = _finviz_pulse_item(row)
        signal = str(item.get("signal") or "").strip()
        canonical = _canonical_finviz_pattern(signal)
        playbook = FINVIZ_PATTERN_STRATEGIES.get(canonical)
        if not playbook:
            continue
        change_pct = _float(item.get("change_pct"))
        confidence = _pattern_confidence(item, playbook)
        action = _direction_from_pattern_and_change(playbook, change_pct)
        strategies.append(
            {
                "symbol": item.get("symbol"),
                "company": item.get("company"),
                "sector": item.get("sector"),
                "price": item.get("price"),
                "change_pct": change_pct,
                "volume": item.get("volume"),
                "relative_volume": item.get("relative_volume"),
                "finviz_signal": signal,
                "canonical_pattern": canonical,
                "strategy_family": playbook["family"],
                "bias": playbook["bias"],
                "action": action,
                "status": "WAIT_LIVE_CHART_CONFIRMATION",
                "confidence": confidence,
                "entry_zone": playbook["entry_zone"],
                "target_zone": playbook["target_zone"],
                "stop_zone": playbook["stop_zone"],
                "playbook": playbook["playbook"],
                "roxy_instruction": (
                    f"{item.get('symbol')}: {playbook['family']}. {playbook['playbook']} "
                    "Confirmar lineas en grafica live antes de operar."
                ),
                "risk_note": "No operar en el centro del patron ni si el precio ya llego tarde al target.",
                "source": "Finviz Elite",
            }
        )
    strategies.sort(key=lambda item: (int(item.get("confidence") or 0), abs(_float(item.get("change_pct")) or 0.0)), reverse=True)
    return strategies[:limit]


def build_finviz_news_feed(
    rows: Iterable[NormalizedMarketRow | dict[str, Any]],
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Build a Finviz-driven news/momentum feed for Roxy actions.

    Finviz exports expose concise labels such as Major News, Upgrades,
    Downgrades, Earnings After, Insider Buying, and Unusual Volume. Roxy turns
    those labels into explainable news cards without scraping protected pages.
    """
    feed: list[dict[str, Any]] = []
    for raw_row in rows:
        row = _row_dict(raw_row)
        is_finviz = str(row.get("source") or "") == "Finviz Elite"
        is_stock = str(row.get("market") or "").lower() == "stock"
        if not (is_finviz or is_stock):
            continue
        item = _finviz_pulse_item(row)
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        canonical = _canonical_finviz_news_signal(item.get("signal"))
        if not canonical:
            continue
        category, detail = FINVIZ_NEWS_SIGNAL_CATEGORIES[canonical]
        change_pct = _float(item.get("change_pct"))
        abs_change = abs(change_pct or 0.0)
        impact = "alto" if canonical in {"MAJOR NEWS", "EARNINGS AFTER", "EARNINGS BEFORE", "UPGRADES", "DOWNGRADES"} or abs_change >= 3.0 else "medio"
        tone = "positive" if change_pct is not None and change_pct > 0 else "negative" if change_pct is not None and change_pct < 0 else "neutral"
        company = str(item.get("company") or symbol).strip()
        feed.append(
            {
                "symbol": symbol,
                "company": company,
                "price": item.get("price"),
                "change_pct": change_pct,
                "volume": item.get("volume"),
                "relative_volume": item.get("relative_volume"),
                "finviz_signal": item.get("signal"),
                "category": category,
                "headline": f"{symbol} aparece en Finviz como {category}",
                "detail": detail,
                "impact": impact,
                "tone": tone,
                "source": "Finviz Elite",
                "timestamp": utc_now_iso(),
            }
        )
    impact_rank = {"alto": 2, "medio": 1, "bajo": 0}
    feed.sort(
        key=lambda item: (
            impact_rank.get(str(item.get("impact") or ""), 0),
            abs(_float(item.get("change_pct")) or 0.0),
            _float(item.get("relative_volume")) or 0.0,
        ),
        reverse=True,
    )
    return feed[:limit]


def build_finviz_market_pulse(
    rows: Iterable[NormalizedMarketRow | dict[str, Any]],
    *,
    major_threshold: float = 2.0,
    limit: int = 12,
) -> dict[str, Any]:
    """Convert Finviz screener rows into the market-pulse cards Roxy can use.

    This intentionally works from exported CSV rows rather than scraping Finviz
    pages. It lets Roxy reason about major movers, signal tags, and sector
    pressure while keeping auth tokens out of logs and frontend code.
    """
    finviz_rows = [
        _row_dict(row)
        for row in rows
        if str(_row_dict(row).get("source") or "") == "Finviz Elite"
        or str(_row_dict(row).get("market") or "").lower() == "stock"
    ]
    pulse_items = [_finviz_pulse_item(row) for row in finviz_rows if _safe_row_symbol(row)]
    sector_counts: dict[str, int] = {}
    for item in pulse_items:
        sector = str(item.get("sector") or "").strip()
        if sector:
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

    major_movers = sorted(
        [item for item in pulse_items if abs(_float(item.get("change_pct")) or 0.0) >= major_threshold],
        key=lambda item: abs(_float(item.get("change_pct")) or 0.0),
        reverse=True,
    )[:limit]
    pattern_signals = [
        item
        for item in pulse_items
        if str(item.get("signal") or "").strip()
        and str(item.get("signal") or "").strip().lower() not in {"-", "none", "n/a"}
    ][:limit]
    bullish = sorted(
        [item for item in pulse_items if (_float(item.get("change_pct")) or 0.0) > 0],
        key=lambda item: _float(item.get("change_pct")) or 0.0,
        reverse=True,
    )[:limit]
    bearish = sorted(
        [item for item in pulse_items if (_float(item.get("change_pct")) or 0.0) < 0],
        key=lambda item: _float(item.get("change_pct")) or 0.0,
    )[:limit]

    news_feed = build_finviz_news_feed(finviz_rows, limit=limit)

    return {
        "version": "finviz-market-pulse-v1",
        "generated_at": utc_now_iso(),
        "source": "Finviz Elite",
        "row_count": len(pulse_items),
        "major_threshold_pct": major_threshold,
        "major_movers": major_movers,
        "bullish_watchlist": bullish,
        "bearish_watchlist": bearish,
        "pattern_signals": pattern_signals,
        "pattern_strategies": build_finviz_pattern_strategies(finviz_rows, limit=limit),
        "news_feed": news_feed,
        "sector_counts": sector_counts,
        "summary": {
            "bullish_count": len([item for item in pulse_items if (_float(item.get("change_pct")) or 0.0) > 0]),
            "bearish_count": len([item for item in pulse_items if (_float(item.get("change_pct")) or 0.0) < 0]),
            "pattern_count": len(pattern_signals),
            "news_count": len(news_feed),
        },
    }


def build_external_confirmation(
    opportunity: dict[str, Any],
    external_rows: Iterable[NormalizedMarketRow | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cross-check an opportunity against configured external market sources.

    This does not fetch remote data. Callers pass rows fetched by the aggregator,
    so the decision engine stays deterministic and fast.
    """
    symbol = str(opportunity.get("symbol") or opportunity.get("ticker") or "").strip().upper()
    market = str(opportunity.get("market") or "").strip().lower()
    if not market:
        market = "crypto" if "/" in symbol or symbol.endswith("USDT") else "stock"
    direction = _opportunity_direction(opportunity)
    key = normalize_symbol_for_match(symbol, market)
    grouped = rows_by_symbol(external_rows or [])
    matches = grouped.get(key, [])
    preferred_source = "Crypto.com Exchange" if market == "crypto" else "Finviz Elite"
    primary = next((row for row in matches if row.get("source") == preferred_source), matches[0] if matches else None)

    confirmation: dict[str, Any] = {
        "version": "external-confirmation-v1",
        "symbol": symbol,
        "market": market,
        "direction": direction,
        "confirmed": False,
        "source_count": len(matches),
        "sources": [str(row.get("source") or "") for row in matches if row.get("source")],
        "price": None,
        "change_pct": None,
        "volume": None,
        "signal": "",
        "bias": "NEUTRAL",
        "pattern_strategy": None,
        "score_adjustment": 0,
        "color": "yellow",
        "reasons": [],
    }

    if not symbol:
        confirmation["reasons"].append("Sin simbolo para comparar contra fuentes externas.")
        return confirmation
    if primary is None:
        confirmation["reasons"].append(f"No hay fila externa disponible para {symbol}.")
        return confirmation

    price = _float(primary.get("price"))
    change_pct = _float(primary.get("change_pct"))
    volume = _float(primary.get("volume"))
    primary_signal = str(primary.get("signal") or "")
    pattern_strategy = None
    pattern_rows = build_finviz_pattern_strategies([primary], limit=1) if market == "stock" else []
    if pattern_rows:
        pattern_strategy = pattern_rows[0]
        primary_signal = primary_signal or str(pattern_strategy.get("finviz_signal") or "")
    bias = _source_signal_bias(primary_signal)
    if pattern_strategy and pattern_strategy.get("bias") in {"ARRIBA", "ABAJO"}:
        bias = str(pattern_strategy.get("bias"))
    confirmation.update(
        {
            "confirmed": True,
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "signal": primary_signal,
            "bias": bias,
            "pattern_strategy": pattern_strategy,
            "color": "green",
        }
    )

    score = 5 if market == "crypto" else 4
    confirmation["reasons"].append(f"{primary.get('source')} confirma que {symbol} esta presente en la fuente externa.")
    if price is not None:
        confirmation["reasons"].append(f"Precio externo observado: {price}.")
    if change_pct is not None:
        if direction == "ARRIBA" and change_pct > 0:
            score += 4
            confirmation["reasons"].append("Cambio externo positivo acompana la direccion alcista.")
        elif direction == "ABAJO" and change_pct < 0:
            score += 4
            confirmation["reasons"].append("Cambio externo negativo acompana la direccion bajista.")
        elif direction != "SIN_DIRECCION" and abs(change_pct) >= 0.15:
            score -= 4
            confirmation["color"] = "yellow"
            confirmation["reasons"].append("El cambio externo contradice parcialmente la direccion de Roxy.")
    if bias in {"ARRIBA", "ABAJO"}:
        if direction == bias:
            score += 3
            confirmation["reasons"].append("La senal textual externa coincide con la direccion de Roxy.")
        elif direction != "SIN_DIRECCION":
            score -= 5
            confirmation["color"] = "red"
            confirmation["reasons"].append("La senal textual externa contradice la direccion de Roxy.")
    if pattern_strategy:
        score += 3
        confirmation["reasons"].append(
            f"Finviz detecta {pattern_strategy.get('strategy_family')}: {pattern_strategy.get('entry_zone')} -> {pattern_strategy.get('target_zone')}."
        )
    if volume is not None and volume > 0:
        score += 1

    confirmation["score_adjustment"] = int(max(-8, min(12, score)))
    return confirmation


def apply_external_market_context(
    opportunity: dict[str, Any],
    external_rows: Iterable[NormalizedMarketRow | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    item = dict(opportunity)
    rows = external_rows
    if rows is None and isinstance(item.get("external_market_rows"), list):
        rows = item.get("external_market_rows")
    if rows is None and isinstance(item.get("_external_market_rows"), list):
        rows = item.get("_external_market_rows")
    confirmation = build_external_confirmation(item, rows)
    item["external_confirmation"] = confirmation
    item["external_source_count"] = confirmation.get("source_count", 0)
    if confirmation.get("confirmed"):
        item["external_price"] = confirmation.get("price")
        item["external_signal"] = confirmation.get("signal")
    return item


def apply_external_market_context_to_opportunities(
    opportunities: Iterable[dict[str, Any]],
    external_rows: Iterable[NormalizedMarketRow | dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return [apply_external_market_context(item, external_rows=external_rows) for item in opportunities]


class FinvizEliteClient:
    """Read Finviz Elite screener export CSV from a user-provided export URL."""

    def __init__(self, export_url: str = "", *, transport: Transport | None = None) -> None:
        self.export_url = export_url.strip()
        self.transport = transport or _default_transport

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, *, transport: Transport | None = None) -> "FinvizEliteClient":
        source = env if env is not None else os.environ
        export_url = str(
            source.get("ROXY_FINVIZ_EXPORT_URL")
            or source.get("FINVIZ_EXPORT_URL")
            or source.get("ROXY_FINVIZ_SCANNER_URL")
            or source.get("FINVIZ_SCANNER_EXPORT_URL")
            or ""
        ).strip()
        token = str(
            source.get("ROXY_FINVIZ_AUTH_TOKEN")
            or source.get("FINVIZ_AUTH_TOKEN")
            or source.get("ROXY_FINVIZ_EXPORT_AUTH")
            or source.get("FINVIZ_EXPORT_AUTH")
            or source.get("ROXY_FINVIZ_TOKEN")
            or source.get("FINVIZ_TOKEN")
            or source.get("FINVIZ_ELITE_TOKEN")
            or source.get("FINVIZ_EXPORT_TOKEN")
            or source.get("FINVIZ_AUTH")
            or source.get("FINVIZ_API_KEY")
            or ""
        ).strip()
        if token.startswith("http://") or token.startswith("https://"):
            export_url = export_url or token
            token = ""
        if token and "auth=" in token:
            parsed_token = urllib.parse.parse_qs(token.lstrip("?"))
            token = str((parsed_token.get("auth") or [""])[0]).strip() or token
        if export_url and "auth=" in export_url and not token:
            parsed_url = urllib.parse.urlparse(export_url)
            parsed_query = urllib.parse.parse_qs(parsed_url.query)
            token = str((parsed_query.get("auth") or [""])[0]).strip()
        if not export_url and token:
            params = dict(DEFAULT_FINVIZ_EXPORT_PARAMS)
            params["auth"] = token
            export_url = f"{DEFAULT_FINVIZ_EXPORT_BASE_URL}?{urllib.parse.urlencode(params)}"
        return cls(export_url, transport=transport)

    def status(self) -> ExternalSourceStatus:
        if not self.export_url:
            return ExternalSourceStatus(
                provider="Finviz Elite",
                configured=False,
                mode="SCREENER_EXPORT",
                status="No configurado",
                detail="Falta el export URL o auth token de Finviz Elite.",
                next_action="Pegar ROXY_FINVIZ_EXPORT_URL completo o un token Finviz en Render/local.",
                missing_keys=("ROXY_FINVIZ_EXPORT_URL", "ROXY_FINVIZ_AUTH_TOKEN", "FINVIZ_EXPORT_AUTH"),
            )
        return ExternalSourceStatus(
            provider="Finviz Elite",
            configured=True,
            mode="SCREENER_EXPORT",
            status="Listo",
            detail=f"Export URL configurado: {redact_url(self.export_url)}",
            next_action="Usar como screener de apoyo; confirmar entradas con proveedor live.",
            present_keys=("ROXY_FINVIZ_EXPORT_URL", "ROXY_FINVIZ_AUTH_TOKEN", "FINVIZ_EXPORT_AUTH"),
        )

    def fetch_screener(self, *, limit: int = 50) -> list[NormalizedMarketRow]:
        if not self.export_url:
            return []
        csv_text = self.transport(self.export_url, None, {"User-Agent": "RoxyTrading/1.0"})
        reader = csv.DictReader(StringIO(csv_text))
        rows: list[NormalizedMarketRow] = []
        for raw in reader:
            symbol = str(raw.get("Ticker") or raw.get("Symbol") or raw.get("ticker") or "").strip().upper()
            if not symbol:
                continue
            normalized_raw = {
                key: raw.get(key)
                for key in FINVIZ_PULSE_RAW_FIELDS
                if key in raw and raw.get(key) not in (None, "")
            }
            normalized_raw.update(
                {
                    "company": raw.get("Company"),
                    "sector": raw.get("Sector"),
                    "industry": raw.get("Industry"),
                    "signal": raw.get("Signal"),
                    "pattern": raw.get("Pattern"),
                    "recommendation": raw.get("Recommendation"),
                }
            )
            rows.append(
                NormalizedMarketRow(
                    source="Finviz Elite",
                    symbol=symbol,
                    market="stock",
                    price=_float(raw.get("Price") or raw.get("price")),
                    change_pct=_float(raw.get("Change") or raw.get("change")),
                    volume=_float(raw.get("Volume") or raw.get("volume")),
                    signal=str(raw.get("Signal") or raw.get("Pattern") or raw.get("Recommendation") or "").strip(),
                    source_url=redact_url(self.export_url),
                    raw=normalized_raw,
                )
            )
            if len(rows) >= limit:
                break
        return rows


class CryptoComClient:
    """Crypto.com Exchange public market-data client.

    Private credentials are accepted for future account integrations, but this
    class only uses public market endpoints. It never places orders.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        *,
        base_url: str = DEFAULT_CRYPTOCOM_BASE_URL,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = base_url.rstrip("/")
        self.transport = transport or _default_transport

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, *, transport: Transport | None = None) -> "CryptoComClient":
        source = env if env is not None else os.environ
        api_key, _ = _env_value(source, "ROXY_CRYPTOCOM_API_KEY", "CRYPTO_COM_API_KEY")
        api_secret, _ = _env_value(source, "ROXY_CRYPTOCOM_API_SECRET", "CRYPTO_COM_API_SECRET")
        base_url = str(source.get("ROXY_CRYPTOCOM_BASE_URL") or DEFAULT_CRYPTOCOM_BASE_URL).strip()
        return cls(api_key, api_secret, base_url=base_url, transport=transport)

    def status(self) -> ExternalSourceStatus:
        present = []
        missing = []
        if self.api_key:
            present.append("ROXY_CRYPTOCOM_API_KEY/CRYPTO_COM_API_KEY")
        else:
            missing.append("ROXY_CRYPTOCOM_API_KEY")
        if self.api_secret:
            present.append("ROXY_CRYPTOCOM_API_SECRET/CRYPTO_COM_API_SECRET")
        else:
            missing.append("ROXY_CRYPTOCOM_API_SECRET")
        return ExternalSourceStatus(
            provider="Crypto.com Exchange",
            configured=bool(self.base_url),
            mode="PUBLIC_MARKET_DATA",
            status="Listo lectura publica" if self.base_url else "No configurado",
            detail="Ticker/candles publicos disponibles. Credenciales privadas quedan guardadas solo para futuras consultas seguras.",
            next_action="Validar tickers publicos; no activar trading real sin adaptador revisado.",
            present_keys=tuple(present),
            missing_keys=tuple(missing),
        )

    def sign_payload(self, method: str, request_id: int, nonce: int, params: dict[str, Any] | None = None) -> str:
        """Return Crypto.com-style HMAC signature for future private endpoints."""
        if not self.api_key or not self.api_secret:
            return ""
        params = params or {}
        params_string = "".join(f"{key}{params[key]}" for key in sorted(params))
        payload = f"{method}{request_id}{self.api_key}{params_string}{nonce}"
        return hmac.new(self.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _endpoint_url(self, method: str) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith(f"/{method}"):
            return base
        return f"{base}/{method}"

    def _post(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = int(time.time() * 1000) % 1_000_000_000
        payload = {"id": request_id, "method": method, "params": params or {}, "nonce": int(time.time() * 1000)}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        response = self.transport(
            self._endpoint_url(method),
            body,
            {"Content-Type": "application/json", "User-Agent": "RoxyTrading/1.0"},
        )
        parsed = json.loads(response)
        if not isinstance(parsed, dict):
            raise ValueError("Crypto.com response is not a JSON object")
        return parsed

    def get_ticker(self, instrument_name: str) -> NormalizedMarketRow | None:
        response = self._post("public/get-ticker", {"instrument_name": instrument_name})
        result = response.get("result") if isinstance(response, dict) else {}
        data = result.get("data") if isinstance(result, dict) else None
        item = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
        if not isinstance(item, dict):
            return None
        symbol = str(item.get("i") or item.get("instrument_name") or instrument_name).replace("_", "/")
        price = (
            _float(item.get("a"))
            or _float(item.get("last"))
            or _float(item.get("k"))
            or _float(item.get("close"))
            or _float(item.get("c"))
        )
        bid = _float(item.get("b") or item.get("bid"))
        ask = _float(item.get("a") or item.get("ask"))
        if price is None and bid is not None and ask is not None:
            price = (bid + ask) / 2
        return NormalizedMarketRow(
            source="Crypto.com Exchange",
            symbol=symbol.upper(),
            market="crypto",
            price=price,
            change_pct=_float(item.get("h") or item.get("change") or item.get("change_pct")),
            volume=_float(item.get("v") or item.get("volume")),
            signal="public/get-ticker",
            raw={key: item.get(key) for key in ("i", "b", "a", "k", "v", "h", "t") if key in item},
        )

    def fetch_tickers(self, instruments: Iterable[str] = DEFAULT_CRYPTOCOM_INSTRUMENTS) -> list[NormalizedMarketRow]:
        rows: list[NormalizedMarketRow] = []
        for instrument in instruments:
            try:
                row = self.get_ticker(str(instrument))
            except Exception:
                row = None
            if row is not None:
                rows.append(row)
        return rows


class TradingViewIntegration:
    """Configuration/status for TradingView charting and webhook confirmations."""

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self.env = env if env is not None else os.environ

    def status(self) -> ExternalSourceStatus:
        webhook_secret = bool(str(self.env.get("TRADINGVIEW_WEBHOOK_SECRET") or "").strip())
        webhook_url = bool(str(self.env.get("TRADINGVIEW_PUBLIC_WEBHOOK_URL") or "").strip())
        widget_enabled = str(self.env.get("ROXY_TRADINGVIEW_WIDGET_ENABLED") or "true").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        configured = webhook_secret or webhook_url or widget_enabled
        missing = []
        if not webhook_secret:
            missing.append("TRADINGVIEW_WEBHOOK_SECRET")
        if not webhook_url:
            missing.append("TRADINGVIEW_PUBLIC_WEBHOOK_URL")
        return ExternalSourceStatus(
            provider="TradingView",
            configured=configured,
            mode="CHARTS_AND_WEBHOOK_CONFIRMATION",
            status="Listo visual/confirmacion" if configured else "No configurado",
            detail="TradingView se usa para graficas y confirmaciones por webhook; no es broker ni ejecuta ordenes.",
            next_action="Configurar webhook publico si quieres confirmaciones automaticas desde alertas.",
            present_keys=tuple(key for key in ("ROXY_TRADINGVIEW_WIDGET_ENABLED",) if widget_enabled),
            missing_keys=tuple(missing),
        )


class ExternalMarketAggregator:
    def __init__(
        self,
        *,
        finviz: FinvizEliteClient | None = None,
        crypto_com: CryptoComClient | None = None,
        tradingview: TradingViewIntegration | None = None,
    ) -> None:
        self.finviz = finviz or FinvizEliteClient.from_env()
        self.crypto_com = crypto_com or CryptoComClient.from_env()
        self.tradingview = tradingview or TradingViewIntegration()

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ExternalMarketAggregator":
        return cls(
            finviz=FinvizEliteClient.from_env(env),
            crypto_com=CryptoComClient.from_env(env),
            tradingview=TradingViewIntegration(env),
        )

    def status(self) -> list[dict[str, Any]]:
        return [self.finviz.status().to_dict(), self.crypto_com.status().to_dict(), self.tradingview.status().to_dict()]

    def fetch_snapshot(self, *, include_remote: bool = True) -> dict[str, Any]:
        rows: list[NormalizedMarketRow] = []
        errors: list[dict[str, str]] = []
        if include_remote:
            try:
                rows.extend(self.finviz.fetch_screener(limit=50))
            except Exception as exc:
                errors.append({"provider": "Finviz Elite", "error": type(exc).__name__})
            try:
                rows.extend(self.crypto_com.fetch_tickers())
            except Exception as exc:
                errors.append({"provider": "Crypto.com Exchange", "error": type(exc).__name__})
        return {
            "generated_at": utc_now_iso(),
            "statuses": self.status(),
            "rows": [row.to_dict() for row in rows],
            "market_pulse": {
                "finviz": build_finviz_market_pulse(rows),
            },
            "errors": errors,
        }


def build_external_market_snapshot(*, include_remote: bool = True, env: dict[str, str] | None = None) -> dict[str, Any]:
    return ExternalMarketAggregator.from_env(env).fetch_snapshot(include_remote=include_remote)
