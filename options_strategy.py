from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import math
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from roxy_trader.api_budget import observe_api_call

import pandas as pd


@dataclass(frozen=True)
class OptionSelectionConfig:
    min_dte: int = 7
    max_dte: int = 45
    min_volume: int = 50
    min_open_interest: int = 100
    max_spread_pct: float = 0.18
    max_otm_pct: float = 0.08
    max_itm_pct: float = 0.08
    min_score: int = 70
    min_call_delta: float = 0.30
    max_call_delta: float = 0.70
    min_put_delta: float = -0.70
    max_put_delta: float = -0.30
    max_breakeven_buffer_pct: float = 0.02


TRADIER_DEFAULT_BASE_URL = "https://api.tradier.com/v1"


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    number = _safe_float(value)
    return int(number) if number is not None else 0


def _safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def _parse_expiry(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _spread_pct(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    return (ask - bid) / mid if mid > 0 else None


def _option_data_source(row: pd.Series) -> str:
    for key in ("data_source", "source", "provider"):
        value = row.get(key)
        if value is not None and not pd.isna(value) and str(value).strip():
            return str(value).strip()
    return "Yahoo/basic"


def _option_side_from_contract(contract: Any) -> str:
    text = _safe_text(contract).upper()
    if len(text) >= 9 and text[-9] in {"C", "P"}:
        return "call" if text[-9] == "C" else "put"
    tail = text[-10:]
    if "C" in tail:
        return "call"
    if "P" in tail:
        return "put"
    return "call"


def _option_side_from_row(row: dict[str, Any]) -> str:
    explicit = _safe_text(row.get("option_type") or row.get("side") or row.get("type")).lower()
    if explicit in {"call", "calls", "c"}:
        return "call"
    if explicit in {"put", "puts", "p"}:
        return "put"
    return _option_side_from_contract(row.get("contractSymbol") or row.get("contract"))


def _metric_check(label: str, passed: bool, value: Any, rule: str, *, severity: str = "hard") -> dict[str, Any]:
    return {
        "label": label,
        "passed": bool(passed),
        "value": value,
        "rule": rule,
        "severity": severity,
    }


def _contracts_by_risk(max_loss_per_contract: float | None, risk_budget: float) -> int:
    if max_loss_per_contract is None or max_loss_per_contract <= 0 or risk_budget <= 0:
        return 0
    return max(0, int(math.floor(risk_budget / max_loss_per_contract)))


def _option_delta_ok(delta: float | None, side: str, config: OptionSelectionConfig) -> bool:
    if delta is None:
        return False
    if side == "put":
        return config.min_put_delta <= delta <= config.max_put_delta
    return config.min_call_delta <= delta <= config.max_call_delta


def analyze_option_contract(
    row: dict[str, Any] | pd.Series,
    *,
    account_equity: float = 500.0,
    risk_pct: float = 0.01,
    target_pct: float | None = None,
    config: OptionSelectionConfig | None = None,
) -> dict[str, Any]:
    """Convert a scored contract into an actionable options brief."""
    cfg = config or OptionSelectionConfig()
    data = row.to_dict() if isinstance(row, pd.Series) else dict(row or {})
    side = _option_side_from_row(data)
    side_label = "Call" if side == "call" else "Put"
    score = _safe_float(data.get("option_score")) or 0.0
    option_decision = _safe_text(data.get("option_decision")).upper()
    dte = _safe_float(data.get("dte"))
    bid = _safe_float(data.get("bid"))
    ask = _safe_float(data.get("ask"))
    mid = _safe_float(data.get("mid"))
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / 2.0
    spread_dollars = _safe_float(data.get("spread_dollars"))
    if spread_dollars is None and bid is not None and ask is not None:
        spread_dollars = ask - bid
    spread_pct = _safe_float(data.get("spread_pct"))
    if spread_pct is None:
        spread_pct = _spread_pct(bid, ask)
    volume = _safe_float(data.get("volume")) or 0.0
    open_interest = _safe_float(data.get("openInterest") or data.get("open_interest")) or 0.0
    delta = _safe_float(data.get("delta"))
    gamma = _safe_float(data.get("gamma"))
    theta = _safe_float(data.get("theta"))
    vega = _safe_float(data.get("vega"))
    implied_volatility = _safe_float(data.get("impliedVolatility") or data.get("iv"))
    strike = _safe_float(data.get("strike"))
    underlying_price = _safe_float(data.get("underlying_price"))
    breakeven_price = _safe_float(data.get("breakeven_price"))
    if breakeven_price is None and strike is not None and ask is not None:
        breakeven_price = strike + ask if side == "call" else strike - ask
    breakeven_pct = _safe_float(data.get("breakeven_pct"))
    if breakeven_pct is None and breakeven_price is not None and underlying_price and underlying_price > 0:
        breakeven_pct = (breakeven_price / underlying_price) - 1.0
    max_loss_per_contract = _safe_float(data.get("max_loss_per_contract"))
    if max_loss_per_contract is None and ask is not None:
        max_loss_per_contract = ask * 100.0

    effective_target_pct = target_pct if target_pct is not None else _safe_float(data.get("target_pct"))
    risk_budget = max(0.0, float(account_equity or 0.0) * float(risk_pct or 0.0))
    contracts = _contracts_by_risk(max_loss_per_contract, risk_budget)
    risk_multiple = (
        max_loss_per_contract / risk_budget
        if max_loss_per_contract is not None and risk_budget > 0
        else None
    )
    full_greeks = all(value is not None for value in (delta, gamma, theta, vega))
    reported_or_estimated = _safe_text(data.get("greek_quality")).upper()
    greeks_available = delta is not None and reported_or_estimated != "MISSING_GREEKS"
    greek_quality = _safe_text(data.get("greek_quality")) or (
        "FULL_GREEKS" if full_greeks else "REPORTED_DELTA_ONLY" if delta is not None else "MISSING_GREEKS"
    )

    breakeven_ok = True
    breakeven_rule = "break-even dentro del objetivo + buffer"
    if breakeven_pct is None:
        breakeven_ok = False
        breakeven_rule = "break-even requerido"
    elif effective_target_pct is not None:
        if side == "put":
            breakeven_ok = abs(breakeven_pct) <= (effective_target_pct + cfg.max_breakeven_buffer_pct)
        else:
            breakeven_ok = breakeven_pct <= (effective_target_pct + cfg.max_breakeven_buffer_pct)
    elif side == "put":
        breakeven_ok = breakeven_pct < 0
    else:
        breakeven_ok = breakeven_pct > 0

    fits_risk = max_loss_per_contract is not None and max_loss_per_contract > 0 and (
        risk_budget <= 0 or max_loss_per_contract <= risk_budget
    )
    checks = [
        _metric_check(
            "DTE",
            dte is not None and cfg.min_dte <= dte <= cfg.max_dte,
            dte,
            f"{cfg.min_dte}-{cfg.max_dte} dias",
        ),
        _metric_check(
            "Delta",
            _option_delta_ok(delta, side, cfg),
            delta,
            f"{cfg.min_call_delta:.2f}-{cfg.max_call_delta:.2f}" if side == "call" else f"{cfg.min_put_delta:.2f}-{cfg.max_put_delta:.2f}",
        ),
        _metric_check(
            "Spread",
            spread_pct is not None and spread_pct <= cfg.max_spread_pct,
            spread_pct,
            f"<= {cfg.max_spread_pct * 100:.0f}%",
        ),
        _metric_check("Volumen", volume >= cfg.min_volume, volume, f">= {cfg.min_volume}"),
        _metric_check("Open interest", open_interest >= cfg.min_open_interest, open_interest, f">= {cfg.min_open_interest}"),
        _metric_check("Break-even", breakeven_ok, breakeven_pct, breakeven_rule, severity="soft"),
        _metric_check("Max loss", max_loss_per_contract is not None and max_loss_per_contract > 0, max_loss_per_contract, "perdida maxima medible"),
        _metric_check(
            "Cabe en 1R",
            fits_risk,
            risk_multiple,
            "max loss <= riesgo de cuenta",
            severity="soft" if risk_budget > 0 else "info",
        ),
        _metric_check("Greeks", greeks_available, greek_quality, "delta obligatorio; gamma/theta/vega preferidos"),
    ]
    blockers = [
        f"{item['label']}: {item['rule']}"
        for item in checks
        if not item["passed"] and item.get("severity") == "hard"
    ]
    cautions = [
        f"{item['label']}: {item['rule']}"
        for item in checks
        if not item["passed"] and item.get("severity") != "hard"
    ]
    is_candidate = option_decision in {"OPTION_CANDIDATE", "WATCH", "BUY", ""}
    hard_ok = not blockers and score >= cfg.min_score and is_candidate
    if hard_ok and cautions:
        professional_decision = "ESPERAR"
        human_decision = f"Esperar {side_label}"
    elif hard_ok:
        professional_decision = "MIRAR_CALL" if side == "call" else "MIRAR_PUT"
        human_decision = f"Mirar {side_label}"
    elif blockers and any(
        item.startswith(("Delta:", "Volumen:", "Open interest:", "Greeks:")) for item in blockers
    ):
        professional_decision = "NO_OPERAR"
        human_decision = "No operar"
    elif score >= max(50, cfg.min_score - 15) and not any("Spread" in item for item in blockers):
        professional_decision = "ESPERAR"
        human_decision = f"Esperar {side_label}"
    else:
        professional_decision = "NO_OPERAR"
        human_decision = "No operar"

    spread_text = f"{spread_pct * 100:.1f}%" if spread_pct is not None else "-"
    delta_text = f"{delta:.2f}" if delta is not None else "-"
    dte_text = f"{int(dte)}" if dte is not None else "-"
    be_text = f"{breakeven_price:.2f}" if breakeven_price is not None else "-"
    max_loss_text = f"${max_loss_per_contract:.2f}" if max_loss_per_contract is not None else "-"
    summary = (
        f"{human_decision}: {data.get('contractSymbol') or '-'} | DTE {dte_text} | "
        f"delta {delta_text} | spread {spread_text} | OI {int(open_interest)} | "
        f"vol {int(volume)} | break-even {be_text} | max loss {max_loss_text}."
    )
    if cautions:
        summary += " Precaucion: " + "; ".join(cautions[:2]) + "."
    if blockers:
        summary += " Bloquea: " + "; ".join(blockers[:2]) + "."

    return {
        **data,
        "contract": data.get("contractSymbol") or data.get("contract"),
        "contractSymbol": data.get("contractSymbol") or data.get("contract"),
        "side": side.upper(),
        "side_label": side_label,
        "professional_decision": professional_decision,
        "human_decision": human_decision,
        "quality": "PROFESSIONAL" if full_greeks else "PARTIAL" if greeks_available else "INCOMPLETE",
        "quality_label": "Greeks completos" if full_greeks else "Delta disponible" if greeks_available else "Faltan Greeks",
        "score": score,
        "option_score": score,
        "option_decision": option_decision or data.get("option_decision"),
        "dte": dte,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "spread_dollars": spread_dollars,
        "spread_pct": spread_pct,
        "volume": volume,
        "openInterest": open_interest,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "impliedVolatility": implied_volatility,
        "strike": strike,
        "underlying_price": underlying_price,
        "breakeven_price": breakeven_price,
        "breakeven_pct": breakeven_pct,
        "max_loss_per_contract": max_loss_per_contract,
        "risk_budget": risk_budget,
        "risk_multiple": risk_multiple,
        "contracts_by_risk": contracts,
        "fits_1r": fits_risk,
        "greek_quality": greek_quality,
        "greek_note": data.get("greek_note") or "",
        "checks": checks,
        "blockers": blockers,
        "cautions": cautions,
        "summary": summary,
        "data_source": data.get("data_source") or data.get("source") or data.get("provider") or "Yahoo/basic",
    }


def best_option_contract(
    options_df: pd.DataFrame,
    symbol: str,
    *,
    account_equity: float = 500.0,
    risk_pct: float = 0.01,
    target_pct: float | None = None,
    config: OptionSelectionConfig | None = None,
) -> dict[str, Any]:
    if options_df.empty or "symbol" not in options_df.columns:
        return {}
    rows = options_df[options_df["symbol"].astype(str).str.upper().eq(str(symbol).upper())].copy()
    if rows.empty:
        return {}
    analyzed = [
        analyze_option_contract(
            row,
            account_equity=account_equity,
            risk_pct=risk_pct,
            target_pct=target_pct,
            config=config,
        )
        for _, row in rows.iterrows()
    ]
    rank = {"MIRAR_CALL": 3, "MIRAR_PUT": 3, "ESPERAR": 2, "NO_OPERAR": 1}
    analyzed.sort(
        key=lambda item: (
            rank.get(str(item.get("professional_decision")), 0),
            float(item.get("option_score") or 0),
            -float(item.get("spread_pct") if item.get("spread_pct") is not None else 99),
            -float(item.get("dte") if item.get("dte") is not None else 999),
        ),
        reverse=True,
    )
    return analyzed[0]


def professional_options_feed_status(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env if env is not None else os.environ
    feeds = [
        ("Tradier", ("TRADIER_ACCESS_TOKEN",)),
        ("ORATS", ("ORATS_API_KEY",)),
        ("Polygon", ("POLYGON_API_KEY",)),
        ("ThetaData", ("THETADATA_USERNAME", "THETADATA_PASSWORD")),
        ("MarketData.app", ("MARKETDATA_API_TOKEN",)),
    ]
    configured = [
        name
        for name, keys in feeds
        if all(str(source.get(key) or "").strip() for key in keys)
    ]
    if configured:
        provider_note = (
            "Tradier incluye cadenas de opciones con IV y Greeks cuando se pide greeks=true."
            if configured[0] == "Tradier"
            else "Proveedor profesional detectado; usar sus Greeks reportados antes de considerar calls/puts reales."
        )
        return {
            "status": "READY",
            "tone": "buy",
            "label": "Feed profesional conectado",
            "source": configured[0],
            "configured": configured,
            "note": provider_note,
        }
    return {
        "status": "BASIC",
        "tone": "watch",
        "label": "Feed profesional pendiente",
        "source": "Yahoo/basic",
        "configured": [],
        "note": "Roxy puede estimar delta, pero opciones reales necesitan proveedor con delta/theta/vega, OI y volumen confiables.",
    }


def _moneyness_pct(strike: float, underlying_price: float, option_type: str) -> float:
    if option_type == "put":
        return (underlying_price / strike) - 1.0
    return (strike / underlying_price) - 1.0


def _tradier_base_url(env: dict[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    base = str(source.get("TRADIER_BASE_URL") or "").strip()
    if base:
        return base.rstrip("/")
    if str(source.get("TRADIER_SANDBOX") or "").strip().lower() in {"1", "true", "yes"}:
        return "https://sandbox.tradier.com/v1"
    return TRADIER_DEFAULT_BASE_URL


def _http_get_json(url: str, params: dict[str, Any], token: str, timeout: int = 12) -> dict[str, Any]:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    full_url = f"{url}?{query}" if query else url
    request = Request(
        full_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with observe_api_call("tradier", "options") as observation:
        with urlopen(request, timeout=timeout) as response:
            observation.set_http_status(getattr(response, "status", None))
            return json.loads(response.read().decode("utf-8"))


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _tradier_expiration_dates(payload: dict[str, Any]) -> list[str]:
    expirations = payload.get("expirations") or {}
    return [str(item) for item in _list_value(expirations.get("date")) if item]


def _tradier_option_rows(payload: dict[str, Any], *, symbol: str, expiry: str, option_type: str) -> pd.DataFrame:
    options = (payload.get("options") or {}).get("option")
    rows = []
    for item in _list_value(options):
        if not isinstance(item, dict):
            continue
        side = str(item.get("option_type") or option_type or "").lower()
        if option_type and side and side != option_type:
            continue
        greeks = item.get("greeks") or {}
        iv = (
            _safe_float(greeks.get("mid_iv"))
            or _safe_float(greeks.get("smv_vol"))
            or _safe_float(greeks.get("bid_iv"))
            or _safe_float(greeks.get("ask_iv"))
            or _safe_float(item.get("implied_volatility"))
        )
        rows.append(
            {
                "contractSymbol": item.get("symbol"),
                "strike": item.get("strike"),
                "bid": item.get("bid"),
                "ask": item.get("ask"),
                "volume": item.get("volume"),
                "openInterest": item.get("open_interest") or item.get("openInterest"),
                "impliedVolatility": iv,
                "delta": greeks.get("delta") if isinstance(greeks, dict) else None,
                "gamma": greeks.get("gamma") if isinstance(greeks, dict) else None,
                "theta": greeks.get("theta") if isinstance(greeks, dict) else None,
                "vega": greeks.get("vega") if isinstance(greeks, dict) else None,
                "rho": greeks.get("rho") if isinstance(greeks, dict) else None,
                "data_source": "Tradier",
                "provider_expiry": item.get("expiration_date") or expiry,
                "root_symbol": item.get("root_symbol") or symbol,
            }
        )
    return pd.DataFrame(rows)


def fetch_tradier_scored_option_candidates(
    symbol: str,
    *,
    underlying_price: float,
    target_pct: float,
    option_type: str = "call",
    config: OptionSelectionConfig | None = None,
    token: str | None = None,
    base_url: str | None = None,
    today: date | None = None,
    http_get_json: Any = _http_get_json,
) -> pd.DataFrame:
    cfg = config or OptionSelectionConfig()
    tradier_token = str(token or os.environ.get("TRADIER_ACCESS_TOKEN") or "").strip()
    if not tradier_token:
        return pd.DataFrame()

    root = (base_url or _tradier_base_url()).rstrip("/")
    expirations_payload = http_get_json(
        f"{root}/markets/options/expirations",
        {"symbol": symbol, "includeAllRoots": "true", "strikes": "false"},
        tradier_token,
    )
    today_date = today or date.today()
    frames = []
    for expiry in _tradier_expiration_dates(expirations_payload):
        expiry_date = _parse_expiry(expiry)
        dte = (expiry_date - today_date).days
        if dte < cfg.min_dte or dte > cfg.max_dte:
            continue
        chain_payload = http_get_json(
            f"{root}/markets/options/chains",
            {"symbol": symbol, "expiration": expiry, "greeks": "true"},
            tradier_token,
        )
        chain = _tradier_option_rows(chain_payload, symbol=symbol, expiry=expiry, option_type=option_type)
        if chain.empty:
            continue
        scored = score_options_chain(
            chain,
            symbol=symbol,
            underlying_price=underlying_price,
            target_pct=target_pct,
            expiry=expiry,
            option_type=option_type,
            today=today_date,
            config=cfg,
        )
        if not scored.empty:
            frames.append(scored)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values(["option_decision", "option_score", "dte", "spread_pct"], ascending=[True, False, True, True]).reset_index(drop=True)


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _approx_delta(
    *,
    underlying_price: float,
    strike: float,
    dte: int,
    implied_volatility: float | None,
    option_type: str,
) -> float | None:
    if underlying_price <= 0 or strike <= 0 or dte <= 0 or not implied_volatility or implied_volatility <= 0:
        return None
    years = dte / 365.0
    try:
        d1 = (math.log(underlying_price / strike) + (0.5 * implied_volatility**2) * years) / (
            implied_volatility * math.sqrt(years)
        )
    except (ValueError, ZeroDivisionError):
        return None
    call_delta = _norm_cdf(d1)
    if option_type == "put":
        return call_delta - 1.0
    return call_delta


def _greek_data_quality(
    *,
    delta: float | None,
    gamma: float | None,
    theta: float | None,
    vega: float | None,
    implied_volatility: float | None,
    reported_delta: bool,
) -> tuple[str, str]:
    if all(value is not None for value in (delta, gamma, theta, vega)):
        return "FULL_GREEKS", "Reported delta/gamma/theta/vega"
    if reported_delta:
        return "REPORTED_DELTA_ONLY", "Reported delta only; gamma/theta/vega unavailable"
    if delta is not None and implied_volatility is not None:
        return "ESTIMATED_DELTA", "Estimated delta from IV; gamma/theta/vega unavailable"
    return "MISSING_GREEKS", "Greeks unavailable from current data source"


def _score_contract(
    *,
    dte: int,
    spread_pct: float | None,
    volume: int,
    open_interest: int,
    moneyness_pct: float,
    target_reaches_strike: bool,
    implied_volatility: float | None,
    config: OptionSelectionConfig,
) -> int:
    score = 50

    if config.min_dte <= dte <= config.max_dte:
        score += 15
    else:
        score -= 25

    if spread_pct is None:
        score -= 35
    elif spread_pct <= 0.08:
        score += 20
    elif spread_pct <= config.max_spread_pct:
        score += 8
    else:
        score -= 30

    if volume >= config.min_volume * 4:
        score += 12
    elif volume >= config.min_volume:
        score += 6
    else:
        score -= 15

    if open_interest >= config.min_open_interest * 5:
        score += 12
    elif open_interest >= config.min_open_interest:
        score += 6
    else:
        score -= 15

    if -0.03 <= moneyness_pct <= 0.04:
        score += 15
    elif -config.max_itm_pct <= moneyness_pct <= config.max_otm_pct:
        score += 5
    else:
        score -= 20

    if target_reaches_strike:
        score += 8
    else:
        score -= 20

    if implied_volatility is not None and implied_volatility > 1.5:
        score -= 10

    return int(max(0, min(100, score)))


def score_options_chain(
    chain: pd.DataFrame,
    *,
    symbol: str,
    underlying_price: float,
    target_pct: float,
    expiry: str | date | datetime,
    option_type: str = "call",
    today: date | None = None,
    config: OptionSelectionConfig | None = None,
) -> pd.DataFrame:
    cfg = config or OptionSelectionConfig()
    if chain.empty or underlying_price <= 0:
        return pd.DataFrame()

    expiry_date = _parse_expiry(expiry)
    today_date = today or date.today()
    dte = (expiry_date - today_date).days
    target_price = underlying_price * (1.0 + target_pct)

    rows = []
    for _, row in chain.iterrows():
        strike = _safe_float(row.get("strike"))
        bid = _safe_float(row.get("bid"))
        ask = _safe_float(row.get("ask"))
        if strike is None or bid is None or ask is None or ask <= 0:
            continue

        mid = (bid + ask) / 2.0
        spread = _spread_pct(bid, ask)
        spread_dollars = ask - bid
        volume = _safe_int(row.get("volume"))
        open_interest = _safe_int(row.get("openInterest"))
        implied_volatility = _safe_float(row.get("impliedVolatility"))
        gamma = _safe_float(row.get("gamma"))
        theta = _safe_float(row.get("theta"))
        vega = _safe_float(row.get("vega"))
        reported_delta_value = _safe_float(row.get("delta"))
        moneyness = _moneyness_pct(strike, underlying_price, option_type)
        target_reaches_strike = target_price >= strike if option_type == "call" else target_price <= strike
        breakeven_price = strike + ask if option_type == "call" else strike - ask
        breakeven_pct = (breakeven_price / underlying_price) - 1.0
        premium = ask
        intrinsic_at_target = max(target_price - strike, 0.0) if option_type == "call" else max(strike - target_price, 0.0)
        intrinsic_return = (intrinsic_at_target / ask) - 1.0 if ask > 0 else None
        delta = reported_delta_value
        if delta is None:
            delta = _approx_delta(
                underlying_price=underlying_price,
                strike=strike,
                dte=dte,
                implied_volatility=implied_volatility,
                option_type=option_type,
            )
        greek_quality, greek_note = _greek_data_quality(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            implied_volatility=implied_volatility,
            reported_delta=reported_delta_value is not None,
        )
        score = _score_contract(
            dte=dte,
            spread_pct=spread,
            volume=volume,
            open_interest=open_interest,
            moneyness_pct=moneyness,
            target_reaches_strike=target_reaches_strike,
            implied_volatility=implied_volatility,
            config=cfg,
        )
        decision = "OPTION_CANDIDATE" if score >= cfg.min_score and spread is not None and spread <= cfg.max_spread_pct else "REJECT"

        rows.append(
            {
                "symbol": symbol,
                "contractSymbol": row.get("contractSymbol"),
                "option_type": option_type,
                "expiry": expiry_date.isoformat(),
                "dte": dte,
                "strike": strike,
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "premium": premium,
                "spread_dollars": spread_dollars,
                "spread_pct": spread,
                "volume": volume,
                "openInterest": open_interest,
                "impliedVolatility": implied_volatility,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "greek_quality": greek_quality,
                "greek_note": greek_note,
                "data_source": _option_data_source(row),
                "moneyness_pct": moneyness,
                "underlying_price": underlying_price,
                "target_pct": target_pct,
                "target_underlying_price": target_price,
                "target_reaches_strike": target_reaches_strike,
                "breakeven_price": breakeven_price,
                "breakeven_pct": breakeven_pct,
                "intrinsic_value_at_target": intrinsic_at_target,
                "intrinsic_return_at_target_pct": intrinsic_return,
                "estimated_contract_value_at_target": intrinsic_at_target * 100.0,
                "risk_reward_at_target": intrinsic_at_target / ask if ask > 0 else None,
                "max_loss_per_contract": ask * 100.0,
                "option_score": score,
                "option_decision": decision,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["option_decision", "option_score", "spread_pct"], ascending=[True, False, True]).reset_index(drop=True)


def fetch_scored_option_candidates(
    symbol: str,
    *,
    underlying_price: float,
    target_pct: float,
    option_type: str = "call",
    config: OptionSelectionConfig | None = None,
    provider: str = "auto",
) -> pd.DataFrame:
    selected_provider = str(provider or "auto").strip().lower()
    if selected_provider in {"auto", "tradier"} and str(os.environ.get("TRADIER_ACCESS_TOKEN") or "").strip():
        try:
            tradier = fetch_tradier_scored_option_candidates(
                symbol,
                underlying_price=underlying_price,
                target_pct=target_pct,
                option_type=option_type,
                config=config,
            )
            if not tradier.empty:
                return tradier
        except Exception:
            if selected_provider == "tradier":
                raise

    import yfinance as yf

    cfg = config or OptionSelectionConfig()
    ticker = yf.Ticker(symbol)
    expiries = list(getattr(ticker, "options", []) or [])
    frames = []
    today = date.today()
    for expiry in expiries:
        expiry_date = _parse_expiry(expiry)
        dte = (expiry_date - today).days
        if dte < cfg.min_dte or dte > cfg.max_dte:
            continue
        chain = ticker.option_chain(expiry)
        frame = chain.calls if option_type == "call" else chain.puts
        scored = score_options_chain(
            frame,
            symbol=symbol,
            underlying_price=underlying_price,
            target_pct=target_pct,
            expiry=expiry,
            option_type=option_type,
            today=today,
            config=cfg,
        )
        if not scored.empty:
            frames.append(scored)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values(["option_decision", "option_score", "dte", "spread_pct"], ascending=[True, False, True, True]).reset_index(drop=True)
