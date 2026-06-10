from __future__ import annotations

from typing import Any

import pandas as pd

from moving_average_strategy import add_moving_averages
from salto_strategies import detect_salto_setups
from tools.ma_scan import is_intraday_stock_interval, stock_fetch_interval, stock_period_for_interval


SYMBOL_ALIASES = {
    "APPLE": "AAPL",
    "APPLE INC": "AAPL",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "TESLA": "TSLA",
    "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",
    "META": "META",
    "AMD": "AMD",
    "PALANTIR": "PLTR",
    "BITCOIN": "BTC/USD",
    "BTC": "BTC/USD",
    "ETHEREUM": "ETH/USD",
    "ETH": "ETH/USD",
    "SOLANA": "SOL/USD",
    "SOL": "SOL/USD",
}

DERIVED_INTRADAY_TIMEFRAMES = {"2h": "2h", "4h": "4h"}


def normalize_timeframe(timeframe: str) -> str:
    value = str(timeframe or "1h").strip().lower()
    aliases = {
        "60m": "1h",
        "120m": "2h",
        "240m": "4h",
        "1d": "1d",
        "day": "1d",
        "daily": "1d",
    }
    return aliases.get(value, value)


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty or "ts" not in df.columns:
        return pd.DataFrame()
    data = df.copy()
    data["ts"] = pd.to_datetime(data["ts"], errors="coerce")
    data = data.dropna(subset=["ts"]).sort_values("ts")
    if data.empty:
        return pd.DataFrame()
    aggregations = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    keep = [column for column in aggregations if column in data.columns]
    if not {"open", "high", "low", "close"}.issubset(keep):
        return pd.DataFrame()
    resampled = (
        data.set_index("ts")
        .resample(rule, label="right", closed="right")
        .agg({column: aggregations[column] for column in keep})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    return resampled


def resolve_symbol_query(query: str, market: str = "stock") -> str:
    value = str(query or "").strip().upper()
    if not value:
        return ""
    value = SYMBOL_ALIASES.get(value, value)
    if market == "crypto" and "/" not in value:
        value = f"{value}/USD"
    return value


def fetch_symbol_history(
    symbol: str,
    *,
    market: str,
    timeframe: str,
    include_extended_hours: bool = True,
) -> pd.DataFrame:
    import roxy_scanner as scanner

    timeframe = normalize_timeframe(timeframe)
    if timeframe in DERIVED_INTRADAY_TIMEFRAMES:
        if market == "crypto":
            base = scanner.fetch_crypto_ohlcv(symbol, timeframe="1h", limit=1000)
        else:
            base_period = stock_period_for_interval("1h", None, "730d" if timeframe == "4h" else "60d")
            base = scanner.fetch_stock_ohlcv(
                symbol,
                interval=stock_fetch_interval("1h"),
                period=base_period,
                prepost=include_extended_hours,
            )
        return resample_ohlcv(base, DERIVED_INTRADAY_TIMEFRAMES[timeframe])

    if market == "crypto":
        return scanner.fetch_crypto_ohlcv(symbol, timeframe=timeframe, limit=500)

    period = stock_period_for_interval(timeframe, None, "60d")
    return scanner.fetch_stock_ohlcv(
        symbol,
        interval=stock_fetch_interval(timeframe),
        period=period,
        prepost=include_extended_hours and is_intraday_stock_interval(timeframe),
    )


def prepare_symbol_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = add_moving_averages(df)
    out = out.copy()
    out["ts"] = pd.to_datetime(out["ts"])
    out["ema9"] = out["close"].ewm(span=9, adjust=False).mean()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, pd.NA)
    out["rsi14"] = 100.0 - (100.0 / (1.0 + rs))
    out.loc[(loss == 0) & (gain > 0), "rsi14"] = 100.0
    out.loc[(loss == 0) & (gain == 0), "rsi14"] = 50.0
    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["bb_mid"] = out["close"].rolling(window=20, min_periods=20).mean()
    bb_std = out["close"].rolling(window=20, min_periods=20).std()
    out["bb_upper"] = out["bb_mid"] + (bb_std * 2.0)
    out["bb_lower"] = out["bb_mid"] - (bb_std * 2.0)
    out["range_high_60"] = out["high"].rolling(window=60, min_periods=20).max() if "high" in out.columns else None
    out["range_low_60"] = out["low"].rolling(window=60, min_periods=20).min() if "low" in out.columns else None
    if {"range_high_60", "range_low_60", "close"}.issubset(out.columns):
        out["channel_width_pct"] = (out["range_high_60"] - out["range_low_60"]) / out["close"]
    keep = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "ema9",
        "sma20",
        "sma40",
        "sma100",
        "sma200",
        "bb_mid",
        "bb_upper",
        "bb_lower",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_hist",
        "range_high_60",
        "range_low_60",
        "channel_width_pct",
        "volume",
        "volume_sma20",
        "relative_volume",
        "atr_pct",
    ]
    return out[[col for col in keep if col in out.columns]].dropna(subset=["close"]).reset_index(drop=True)


def latest_symbol_rows(scan_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if scan_df.empty or "symbol" not in scan_df.columns:
        return pd.DataFrame()
    out = scan_df[scan_df["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
    if out.empty:
        return out
    if "score" in out.columns:
        out["score"] = pd.to_numeric(out["score"], errors="coerce")
        out = out.sort_values(["tf", "score"], ascending=[True, False])
    return out.reset_index(drop=True)


def latest_confluence_row(confluence_df: pd.DataFrame, symbol: str) -> dict[str, Any]:
    if confluence_df.empty or "symbol" not in confluence_df.columns:
        return {}
    rows = confluence_df[confluence_df["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
    if rows.empty:
        return {}
    if "confluence_score" in rows.columns:
        rows["confluence_score"] = pd.to_numeric(rows["confluence_score"], errors="coerce")
        rows = rows.sort_values("confluence_score", ascending=False)
    return rows.iloc[0].to_dict()


def _safe_float(value: Any) -> float | None:
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


def _safe_int(value: Any) -> int:
    number = _safe_float(value)
    return int(number) if number is not None else 0


def _safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip().upper()


def _risk_pct(setup: dict[str, Any]) -> float | None:
    entry = _safe_float(setup.get("entry"))
    stop = _safe_float(setup.get("stop"))
    if entry is None or stop is None or entry <= 0 or stop <= 0 or stop >= entry:
        return None
    return (entry - stop) / entry


def classify_strategy_playbook(
    setup: dict[str, Any],
    *,
    confluence: dict[str, Any] | None = None,
    market: str = "stock",
    timeframe: str = "1d",
) -> dict[str, str]:
    """Translate raw SMA metrics into a trading playbook explanation."""
    confluence = confluence or {}
    signal = _safe_text(setup.get("signal"))
    setup_name = _safe_text(setup.get("setup"))
    confluence_signal = _safe_text(confluence.get("signal"))
    trade_decision = _safe_text(confluence.get("trade_decision"))
    score = _safe_int(setup.get("score"))

    close = _safe_float(setup.get("close") or setup.get("entry"))
    sma20 = _safe_float(setup.get("sma20"))
    sma40 = _safe_float(setup.get("sma40"))
    sma100 = _safe_float(setup.get("sma100"))
    sma200 = _safe_float(setup.get("sma200"))
    dist20 = _safe_float(setup.get("dist_sma20_pct"))
    dist40 = _safe_float(setup.get("dist_sma40_pct"))
    risk = _risk_pct(setup)
    salto_family = _safe_text(setup.get("salto_family") or confluence.get("salto_family") or setup.get("strategy_family"))

    moving_averages = [sma20, sma40, sma100, sma200]
    has_all_ma = close is not None and all(value is not None for value in moving_averages)
    bullish_stack = bool(has_all_ma and sma20 > sma40 > sma100 > sma200)
    bearish_stack = bool(has_all_ma and sma20 < sma40 < sma100 < sma200)
    close_above_all = bool(has_all_ma and close > max(moving_averages))
    close_below_200 = bool(has_all_ma and close < sma200)
    near_20_40 = any(value is not None and abs(value) <= 3.0 for value in (dist20, dist40))
    extended = bool(dist20 is not None and dist20 > 12.0)
    confluence_confirmed = confluence_signal == "BUY" and trade_decision.startswith("TRADE_FOR")
    confluence_wait = confluence_signal in {"WATCH", "AVOID"} or trade_decision in {"WAIT", "NO_TRADE", "NO_TRADE_DOWNTREND"}
    risk_high = bool(risk is not None and risk > 0.03)

    if salto_family.startswith("SALTO") or "SALTO" in salto_family:
        regime = "Setup de salto"
        strategy = str(setup.get("salto_family") or confluence.get("salto_family") or "Salto pendiente de confirmar")
        entry_rule = "Confirmar 15m/1h y preparar entrada manual cerca del cierre; no activar sin stop medible."
    elif close_below_200 or bearish_stack or setup_name == "DOWNTREND":
        regime = "Bajista / debajo de SMA200"
        strategy = "No trade: esperar recuperacion de SMA200"
        entry_rule = "No buscar compras hasta que el precio recupere SMA200 y SMA20 vuelva sobre SMA40."
    elif bullish_stack and setup_name == "PULLBACK":
        regime = "Canal alcista"
        strategy = "Rebote en SMA20/SMA40"
        entry_rule = "Entrada solo si rebota en SMA20/SMA40 con volumen y el gatillo 15m confirma."
    elif bullish_stack and close_above_all and extended:
        regime = "Tendencia alcista extendida"
        strategy = "Canal fortalecido, pero precio lejos de SMA20"
        entry_rule = "No perseguir vela extendida; esperar retroceso a SMA20/SMA40 o consolidacion."
    elif bullish_stack and close_above_all:
        regime = "Canal fortalecido de largo plazo"
        strategy = "Continuacion de tendencia 20 > 40 > 100 > 200"
        entry_rule = "Entrada valida con cierre sobre SMA20 y confirmacion 15m/1h."
    elif setup_name == "EARLY_UPTREND":
        regime = "Transicion alcista"
        strategy = "Cruce de medias hacia tendencia"
        entry_rule = "Esperar que SMA20>SMA40 y que el precio mantenga SMA100/SMA200 como soporte."
    elif has_all_ma and close > sma200 and near_20_40:
        regime = "Canal lateral sobre SMA200"
        strategy = "Rebote controlado en medias"
        entry_rule = "Comprar solo ruptura o rebote confirmado; evitar entradas dentro del rango sin volumen."
    else:
        regime = "Neutral / canal lateral"
        strategy = "Watchlist: esperar ruptura o pullback limpio"
        entry_rule = "Esperar alineacion de SMA20/40 y confirmacion de volumen antes de operar."

    if signal == "BUY" and confluence_confirmed and not risk_high:
        stock_plan = "Operable segun la estrategia: usar entrada, stop y objetivo del confluence."
    elif signal == "BUY" and confluence_confirmed and risk_high:
        stock_plan = "Setup confirmado, pero riesgo alto; reducir tamano o esperar stop mas cercano."
    elif signal == "BUY":
        stock_plan = "Watchlist fuerte: no entrar todavia; esperar confirmacion de 15m/1h."
    elif signal == "WATCH":
        stock_plan = "Vigilar: falta una condicion antes de operar."
    else:
        stock_plan = "No operar: la estrategia no tiene compra valida ahora."

    if confluence_wait and signal == "BUY":
        stock_plan += " La lectura intradia todavia no acompana."
    if risk_high:
        stock_plan += " El stop actual queda lejos; el riesgo supera 3%."

    if market == "stock":
        if signal == "BUY" and confluence_confirmed and not risk_high:
            options_plan = "Opciones: considerar call/debit spread liquido solo si spread, DTE y volumen son sanos."
        elif signal == "BUY":
            options_plan = "Opciones: esperar; no comprar contratos hasta que 15m/1h confirme entrada."
        else:
            options_plan = "Opciones: no operar sin setup BUY y confluence confirmado."
    else:
        options_plan = "No aplica para crypto."

    return {
        "regime": regime,
        "strategy": strategy,
        "entry_rule": entry_rule,
        "stock_plan": stock_plan,
        "options_plan": options_plan,
        "timing": "Pre/post market se usa solo como informacion; la entrada se valida con volumen y 15m/1h.",
        "score_note": f"Score {score}: senal {signal or '-'} en {timeframe}.",
    }


def _pct_distance(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None or reference == 0:
        return None
    return ((value / reference) - 1.0) * 100.0


def _status(active: bool, watch: bool = False) -> str:
    if active:
        return "ACTIVE"
    if watch:
        return "WATCH"
    return "BLOCKED"


def detect_reference_strategies(chart_df: pd.DataFrame, setup: dict[str, Any]) -> list[dict[str, str]]:
    """Detect the strategy families shown in the user's reference photos."""
    if chart_df.empty:
        return []

    complete = chart_df.dropna(subset=["close"]).copy()
    if complete.empty:
        return []

    last = complete.iloc[-1]
    close = _safe_float(last.get("close"))
    ema9 = _safe_float(last.get("ema9"))
    sma20 = _safe_float(last.get("sma20"))
    sma40 = _safe_float(last.get("sma40"))
    sma100 = _safe_float(last.get("sma100"))
    sma200 = _safe_float(last.get("sma200"))
    upper = _safe_float(last.get("bb_upper"))
    lower = _safe_float(last.get("bb_lower"))
    resistance = _safe_float(last.get("range_high_60"))
    support = _safe_float(last.get("range_low_60"))
    channel_width = _safe_float(last.get("channel_width_pct"))
    rel_vol = _safe_float(last.get("relative_volume"))
    setup_name = _safe_text(setup.get("setup"))
    signal = _safe_text(setup.get("signal"))

    has_stack = all(value is not None for value in [close, sma20, sma40, sma100, sma200])
    bullish_stack = bool(has_stack and sma20 > sma40 > sma100 > sma200)
    bearish_stack = bool(has_stack and sma20 < sma40 < sma100 < sma200)
    close_above_200 = bool(close is not None and sma200 is not None and close > sma200)
    close_above_20_40 = bool(close is not None and sma20 is not None and sma40 is not None and close > sma20 and close > sma40)
    near_ema9 = abs(_pct_distance(close, ema9) or 999.0) <= 1.5
    near_sma20_40 = min(abs(_pct_distance(close, sma20) or 999.0), abs(_pct_distance(close, sma40) or 999.0)) <= 3.0
    near_sma100_200 = min(abs(_pct_distance(close, sma100) or 999.0), abs(_pct_distance(close, sma200) or 999.0)) <= 3.5
    near_resistance = abs(_pct_distance(close, resistance) or 999.0) <= 2.0
    near_support = abs(_pct_distance(close, support) or 999.0) <= 2.0
    compressed_channel = bool(channel_width is not None and channel_width <= 0.22)
    broad_channel = bool(channel_width is not None and channel_width <= 0.35)
    strong_volume = bool(rel_vol is not None and rel_vol >= 1.1)
    band_breakout = bool(close is not None and upper is not None and close > upper)
    lower_reclaim = bool(close is not None and lower is not None and support is not None and close > support and close > lower)

    rows: list[dict[str, str]] = []

    rows.append(
        {
            "family": "Canal alcista con tendencia alcista",
            "status": _status(bullish_stack and close_above_20_40, bullish_stack or setup_name in {"PULLBACK", "EARLY_UPTREND"}),
            "trigger": "Rebote en EMA9/SMA20/SMA40",
            "action": (
                "Buscar entrada solo si 15m confirma rebote y volumen."
                if bullish_stack and (near_ema9 or near_sma20_40)
                else "Esperar pullback a EMA9, SMA20 o SMA40."
            ),
            "why": "La estructura ideal es SMA20 > SMA40 > SMA100 > SMA200 con precio respetando medias.",
        }
    )

    rows.append(
        {
            "family": "Canal fortalecido de largo plazo",
            "status": _status(bullish_stack and close_above_20_40 and signal in {"BUY", "WATCH"}, bullish_stack),
            "trigger": "SMA20 y SMA40 sostienen el avance",
            "action": "Comprar pullback controlado; evitar perseguir si esta muy extendido sobre SMA20.",
            "why": "Replica la referencia de AMD: canal principal guiado por SMA20/40.",
        }
    )

    rows.append(
        {
            "family": "Tendencia alcista de largo plazo",
            "status": _status(close_above_200 and bullish_stack, close_above_200 and not bearish_stack),
            "trigger": "Precio sobre SMA200 y medias largas alineadas",
            "action": "Mantener sesgo alcista; entradas nuevas necesitan confirmacion 15m/1h.",
            "why": "SMA100/SMA200 definen el filtro de direccion principal.",
        }
    )

    lateral_active = broad_channel and not bullish_stack and not bearish_stack
    rows.append(
        {
            "family": "Canal lateral",
            "status": _status(lateral_active, broad_channel),
            "trigger": "Patron imparable / salto por manipulacion",
            "action": (
                "Comprar ruptura con volumen o rebote en soporte; evitar largos pegados al techo."
                if not near_resistance
                else "Esta cerca del techo del canal; esperar ruptura confirmada o retroceso."
            ),
            "why": "Usa soporte/resistencia de 60 velas y bandas para detectar rango.",
        }
    )

    lateral_long = compressed_channel or near_sma100_200
    rows.append(
        {
            "family": "Tendencia lateral de largo plazo",
            "status": _status(lateral_long, broad_channel or near_sma100_200),
            "trigger": "Cruce de medias / busqueda SMA100-SMA200",
            "action": (
                "Esperar ruptura de resistencia con volumen o rebote claro en SMA100/SMA200."
                if lateral_long
                else "No es lateral limpio; priorizar la lectura del regimen dominante."
            ),
            "why": "Se enfoca en cruces, rebote en techo y fuerza inversa entre SMA100/SMA200.",
        }
    )

    rows.append(
        {
            "family": "Banda / nube de volatilidad",
            "status": _status(band_breakout or lower_reclaim, upper is not None and lower is not None),
            "trigger": "Ruptura de banda o recuperacion desde banda baja",
            "action": (
                "Validar con volumen antes de entrada."
                if band_breakout or lower_reclaim
                else "Usar la nube como contexto; no es gatillo por si sola."
            ),
            "why": "La nube ayuda a ver expansion, compresion y extremos del precio.",
        }
    )

    if strong_volume:
        for row in rows:
            if row["status"] == "WATCH":
                row["action"] += " Volumen acompana."
    if near_support:
        rows.append(
            {
                "family": "Rebote en soporte",
                "status": "WATCH",
                "trigger": "Precio cerca del piso del canal",
                "action": "Esperar vela de rechazo y confirmacion 15m antes de comprar.",
                "why": "La zona de soporte puede dar mejor riesgo que entrar en medio del rango.",
            }
        )

    for salto in detect_salto_setups(chart_df, setup):
        rows.append(
            {
                "family": str(salto.get("family")),
                "status": str(salto.get("status")),
                "trigger": str(salto.get("trigger")),
                "action": str(salto.get("action")),
                "why": str(salto.get("why")),
            }
        )

    return rows


def latest_chart_strategy_events(chart_df: pd.DataFrame, setup: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the latest actionable chart events that match the strategy photos."""
    if chart_df.empty:
        return []

    complete = chart_df.dropna(subset=["close"]).copy()
    if complete.empty:
        return []
    setup = setup or {}
    last = complete.iloc[-1]
    prev = complete.iloc[-2] if len(complete) >= 2 else last

    close = _safe_float(last.get("close"))
    open_ = _safe_float(last.get("open")) or close
    low = _safe_float(last.get("low")) or close
    sma20 = _safe_float(last.get("sma20"))
    sma40 = _safe_float(last.get("sma40"))
    sma100 = _safe_float(last.get("sma100"))
    sma200 = _safe_float(last.get("sma200"))
    prev_sma20 = _safe_float(prev.get("sma20"))
    prev_sma40 = _safe_float(prev.get("sma40"))
    prev_sma100 = _safe_float(prev.get("sma100"))
    rel_vol = _safe_float(last.get("relative_volume"))
    support = _safe_float(last.get("range_low_60"))
    resistance = _safe_float(last.get("range_high_60"))
    setup_name = _safe_text(setup.get("setup"))

    has_stack = close is not None and all(value is not None for value in [sma20, sma40, sma100, sma200])
    bullish_stack = bool(has_stack and close > sma20 > sma40 > sma100 > sma200)
    close_above_200 = bool(close is not None and sma200 is not None and close > sma200)
    green_close = bool(close is not None and open_ is not None and close >= open_)
    near_sma20_40 = min(abs(_pct_distance(close, sma20) or 999.0), abs(_pct_distance(close, sma40) or 999.0)) <= 2.5
    near_support = abs(_pct_distance(close, support) or 999.0) <= 2.0
    near_resistance = abs(_pct_distance(close, resistance) or 999.0) <= 2.0
    strong_volume = bool(rel_vol is not None and rel_vol >= 1.1)

    events: list[dict[str, Any]] = []

    def add_event(event: str, status: str, marker: str, meaning: str, wait_for: str, color: str) -> None:
        if close is None:
            return
        events.append(
            {
                "ts": last.get("ts"),
                "price": close,
                "event": event,
                "status": status,
                "marker": marker,
                "what_it_means": meaning,
                "wait_for": wait_for,
                "color": color,
            }
        )

    if bullish_stack:
        add_event(
            "MA_STACK_BULL",
            "ACTIVE",
            "Canal alcista",
            "SMA20 > SMA40 > SMA100 > SMA200 y precio sobre las medias.",
            "Buscar pullback o continuacion con 15m BUY y volumen.",
            "#22c55e",
        )

    if prev_sma20 is not None and prev_sma40 is not None and sma20 is not None and sma40 is not None:
        if prev_sma20 <= prev_sma40 and sma20 > sma40:
            add_event(
                "SMA20_CROSS_SMA40",
                "ACTIVE",
                "Cruce 20/40",
                "La media rapida recupera la media de tendencia corta.",
                "Confirmar que el precio mantenga SMA20 como soporte.",
                "#38bdf8",
            )
        elif sma20 > sma40 and abs(_pct_distance(sma20, sma40) or 999.0) <= 1.5:
            add_event(
                "SMA20_OVER_SMA40",
                "WATCH",
                "20 sobre 40",
                "La estructura corta sigue positiva, pero no es un cruce nuevo.",
                "Esperar entrada limpia en 15m o rebote en SMA20/SMA40.",
                "#38bdf8",
            )

    if prev_sma20 is not None and prev_sma100 is not None and sma20 is not None and sma100 is not None:
        if prev_sma20 <= prev_sma100 and sma20 > sma100:
            add_event(
                "SMA20_CROSS_SMA100",
                "ACTIVE",
                "Cruce 20/100",
                "La fuerza de corto plazo supera una media principal.",
                "Esperar retroceso controlado o ruptura con volumen.",
                "#a78bfa",
            )

    if green_close and near_sma20_40 and (bullish_stack or close_above_200 or setup_name == "PULLBACK"):
        add_event(
            "PULLBACK_REBOUND",
            "ACTIVE",
            "Rebote en media",
            "Precio respeta SMA20/SMA40 y cierra fuerte.",
            "Entrada solo si 15m confirma y el stop queda cerca.",
            "#f59e0b",
        )

    if resistance is not None and close is not None:
        if close > resistance and strong_volume:
            add_event(
                "RESISTANCE_BREAK",
                "ACTIVE",
                "Ruptura con volumen",
                "Precio rompe resistencia de rango con volumen relativo fuerte.",
                "Usar entrada con stop bajo la ruptura; evitar perseguir si se extiende.",
                "#22d3ee",
            )
        elif near_resistance:
            add_event(
                "RESISTANCE_TEST",
                "WATCH",
                "Probando resistencia",
                "Precio esta cerca del techo del canal.",
                "Esperar ruptura con volumen o rechazo para evitar entrada tarde.",
                "#22d3ee",
            )

    if support is not None and close is not None and low is not None:
        if low <= support * 1.01 and close > support and green_close:
            add_event(
                "SUPPORT_REBOUND",
                "ACTIVE",
                "Rebote en soporte",
                "Precio defendio soporte de rango.",
                "Confirmar 15m BUY; stop debe ir debajo del soporte.",
                "#60a5fa",
            )
        elif near_support:
            add_event(
                "SUPPORT_TEST",
                "WATCH",
                "Probando soporte",
                "Precio esta cerca del piso del canal.",
                "Esperar rebote verde o perder soporte para evitar entrada anticipada.",
                "#60a5fa",
            )

    if strong_volume:
        add_event(
            "VOLUME_CONFIRM",
            "ACTIVE",
            "Volumen confirma",
            "Volumen relativo mayor a 1.10x.",
            "Solo usarlo a favor de una entrada tecnica valida.",
            "#eab308",
        )
    elif rel_vol is not None and rel_vol < 0.8:
        add_event(
            "LOW_VOLUME",
            "BLOCKED",
            "Volumen debil",
            "El movimiento no tiene volumen suficiente.",
            "Esperar que el volumen acompanhe antes de operar.",
            "#ef4444",
        )

    salto_colors = {
        "SALTO_EMA_HOURS": "#14b8a6",
        "SALTO_MA_DISTANCE": "#84cc16",
        "SALTO_ATH_BREAKOUT": "#f97316",
        "SALTO_EMA_2H_BEARISH": "#ef4444",
        "SALTO_CHANNEL_CHANGE": "#c084fc",
    }
    for salto in detect_salto_setups(complete, setup):
        if salto.get("status") == "BLOCKED":
            continue
        add_event(
            str(salto.get("key")),
            str(salto.get("status")),
            str(salto.get("family")),
            str(salto.get("why")),
            str(salto.get("action")),
            salto_colors.get(str(salto.get("key")), "#f97316"),
        )

    order = {"ACTIVE": 0, "WATCH": 1, "BLOCKED": 2}
    return sorted(events, key=lambda row: (order.get(str(row.get("status")), 9), str(row.get("event"))))
