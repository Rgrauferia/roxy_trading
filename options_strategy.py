from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import math
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
    with urlopen(request, timeout=timeout) as response:
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
