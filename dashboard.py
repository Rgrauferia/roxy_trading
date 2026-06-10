# -*- coding: utf-8 -*-
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Optional data sources
import yfinance as yf

# -------------------------
# App Config (Modern UI)
# -------------------------
st.set_page_config(
    page_title="ROXY Trader Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------
# Paths
# -------------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
ALERTS_DIR = BASE_DIR / "alerts"
DB_DIR = BASE_DIR / "db"

OUTPUT_DIR.mkdir(exist_ok=True)
ALERTS_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)

SCAN_DB = DB_DIR / "scan_history.csv"


# -------------------------
# Helpers
# -------------------------
def fnum(x):
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "-"
        return f"{float(x):.2f}"
    except Exception:
        return str(x)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_colname(c):
    # columns sometimes become tuples / MultiIndex — convert safely to string
    try:
        if isinstance(c, tuple):
            c = "_".join([str(i) for i in c])
        return str(c).strip()
    except Exception:
        return str(c)


def ensure_ohlcv(df):
    """Normalize to columns: time, open, high, low, close, volume (volume optional)."""
    if df is None or len(df) == 0:
        return pd.DataFrame()

    x = df.copy()
    # flatten / stringify column names
    x.columns = [safe_colname(c) for c in x.columns]

    # If index is Datetime, keep it
    if "time" not in x.columns:
        if isinstance(x.index, pd.DatetimeIndex):
            x = x.copy()
            x["time"] = x.index
        elif "Date" in x.columns:
            x["time"] = pd.to_datetime(x["Date"], errors="coerce")
        else:
            x["time"] = pd.to_datetime(x.index, errors="coerce")

    # standardize case
    cols = {c.lower(): c for c in x.columns}

    def pick(name):
        return cols.get(name, None)

    mapping = {
        "open": pick("open"),
        "high": pick("high"),
        "low": pick("low"),
        "close": pick("close"),
        "volume": pick("volume"),
    }

    # if yfinance style (Open High Low Close Volume)
    if mapping["open"] is None and "Open" in x.columns:
        mapping = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}

    # if alpaca style maybe: open high low close volume
    rename = {}
    for k, v in mapping.items():
        if v is not None:
            rename[v] = k

    x = x.rename(columns=rename)

    needed = ["open", "high", "low", "close"]
    for c in needed:
        if c not in x.columns:
            return pd.DataFrame()

    # numeric
    for c in ["open", "high", "low", "close"]:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    if "volume" in x.columns:
        # volume can sometimes be DataFrame or weird — force 1D numeric
        v = x["volume"]
        if isinstance(v, pd.DataFrame):
            v = v.iloc[:, 0]
        try:
            v = pd.Series(v).squeeze()
        except Exception:
            pass
        x["volume"] = pd.to_numeric(v, errors="coerce").fillna(0)

    x["time"] = pd.to_datetime(x["time"], errors="coerce")
    x = x.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time")
    x = x.reset_index(drop=True)
    return x


# -------------------------
# Indicators
# -------------------------
def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    out = 100 - (100 / (1 + rs))
    return out.fillna(0)


def atr(df, period=14):
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_indicators(df):
    x = df.copy()
    x["ema20"] = ema(x["close"], 20)
    x["ema50"] = ema(x["close"], 50)
    x["ema200"] = ema(x["close"], 200)
    x["rsi14"] = rsi(x["close"], 14)
    x["atr14"] = atr(x, 14)
    return x


# -------------------------
# Simple AI signal logic (safe + explainable)
# -------------------------
def opportunity_ai(df):
    """
    Returns: (signal, score, reasons_dict)
    signal: BUY / PRE-BUY / WATCH / AVOID
    """
    if df is None or df.empty or len(df) < 50:
        return ("AVOID", 0, {"info": "No hay data suficiente"})

    x = add_indicators(df)
    last = x.iloc[-1]
    prev = x.iloc[-2]

    # Force scalars (avoid Series ambiguity)
    c = float(last["close"])
    ema50 = float(last["ema50"])
    ema200 = float(last["ema200"])
    r = float(last["rsi14"])
    r_prev = float(prev["rsi14"])
    atrv = float(last["atr14"]) if not pd.isna(last["atr14"]) else 0.0

    reasons = []
    score = 0

    # Trend
    if c > ema200:
        score += 25
        reasons.append("Precio > EMA200 (tendencia alcista)")
    if ema50 > ema200:
        score += 15
        reasons.append("EMA50 > EMA200 (estructura alcista)")

    # Momentum RSI
    if 45 <= r <= 65 and r > r_prev:
        score += 20
        reasons.append("RSI 45–65 y subiendo (momentum sano)")
    elif r < 35:
        score += 10
        reasons.append("RSI bajo (posible rebote)")
    elif r > 70:
        score -= 10
        reasons.append("RSI alto (riesgo de pullback)")

    # Volumen (si existe)
    if "volume" in x.columns:
        v = x["volume"].tail(20)
        if float(v.mean()) > 0 and float(v.iloc[-1]) > float(v.mean()) * 1.2:
            score += 10
            reasons.append("Volumen fuerte vs promedio (interés real)")

    # Safety clamp
    score = int(max(0, min(100, score)))

    # Signal thresholds (tune later)
    if score >= 70:
        signal = "BUY"
    elif score >= 55:
        signal = "PRE-BUY"
    elif score >= 35:
        signal = "WATCH"
    else:
        signal = "AVOID"

    return (signal, score, {"reasons": reasons, "rsi": r, "ema50": ema50, "ema200": ema200, "atr": atrv})


def trade_levels(df, atr_mult_stop=1.5, atr_mult_tp1=1.0, atr_mult_tp2=2.0):
    if df is None or df.empty or len(df) < 20:
        return None
    x = add_indicators(df)
    last = x.iloc[-1]
    entry = float(last["close"])
    atrv = float(last["atr14"]) if not pd.isna(last["atr14"]) else 0.0
    if atrv <= 0:
        return None
    stop = entry - atr_mult_stop * atrv
    tp1 = entry + atr_mult_tp1 * atrv
    tp2 = entry + atr_mult_tp2 * atrv
    rr2 = (tp2 - entry) / max(1e-9, (entry - stop))
    return {"entry": entry, "stop": stop, "tp1": tp1, "tp2": tp2, "rr_tp2": rr2}


# -------------------------
# Fetch live market data
# -------------------------
@st.cache_data(ttl=30, show_spinner=False)
def fetch_yf(symbol, tf, lookback_days=180):
    # tf mapping for yfinance
    tf_map = {"1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m", "30m": "30m", "60m": "60m", "1h": "60m", "1d": "1d"}
    interval = tf_map.get(tf, "60m")
    start = datetime.now() - timedelta(days=int(lookback_days))

    df = yf.download(
        tickers=symbol,
        interval=interval,
        start=start.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=False,
        threads=True,
    )
    df = ensure_ohlcv(df)
    return df


@st.cache_data(ttl=15, show_spinner=False)
def fetch_ccxt(symbol, tf, limit=300, exchange_id="binance"):
    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    # symbol example: BTC/USDT
    tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    timeframe = tf_map.get(tf, "1h")

    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not ohlcv:
        return pd.DataFrame()
    x = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
    x["time"] = pd.to_datetime(x["time"], unit="ms")
    return ensure_ohlcv(x)


# -------------------------
# Build Chart (Candles + EMA + Levels)
# -------------------------
def build_candles(df, title, levels=None):
    if df is None or df.empty:
        st.warning("No hay data suficiente o falló el fetch. Revisa símbolos / internet.")
        return

    x = add_indicators(df)

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(x=x["time"], open=x["open"], high=x["high"], low=x["low"], close=x["close"], name="Price")
    )
    fig.add_trace(go.Scatter(x=x["time"], y=x["ema20"], mode="lines", name="EMA20"))
    fig.add_trace(go.Scatter(x=x["time"], y=x["ema50"], mode="lines", name="EMA50"))
    fig.add_trace(go.Scatter(x=x["time"], y=x["ema200"], mode="lines", name="EMA200"))

    if levels:
        for k in ["entry", "stop", "tp1", "tp2"]:
            if k in levels and levels[k] is not None:
                fig.add_hline(y=float(levels[k]), line_width=1, line_dash="dot", annotation_text=k.upper())

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Price",
        height=520,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_rangeslider_visible=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    # RSI chart
    rsi_fig = go.Figure()
    rsi_fig.add_trace(go.Scatter(x=x["time"], y=x["rsi14"], mode="lines", name="RSI14"))
    rsi_fig.add_hline(y=70, line_width=1, line_dash="dot")
    rsi_fig.add_hline(y=30, line_width=1, line_dash="dot")
    rsi_fig.update_layout(height=220, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(rsi_fig, use_container_width=True)


# -------------------------
# Local scan history (simple DB)
# -------------------------
def append_history(row):
    try:
        df = pd.DataFrame([row])
        if SCAN_DB.exists():
            df.to_csv(SCAN_DB, mode="a", header=False, index=False)
        else:
            df.to_csv(SCAN_DB, index=False)
    except Exception:
        pass


def load_recent_scans(limit=200):
    if not SCAN_DB.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(SCAN_DB)
        if df.empty:
            return df
        return df.tail(limit)
    except Exception:
        return pd.DataFrame()


# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("🤖 ROXY Trader PRO")
st.sidebar.caption(f"Last refresh: {now_str()}")

market_mode = st.sidebar.selectbox("Market", ["stocks", "crypto"], index=0)

if market_mode == "stocks":
    symbol_default = "AAPL"
    symbol = st.sidebar.text_input("Symbol (Stocks)", value=symbol_default).upper().strip()
    tf = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=3)
    data_source = st.sidebar.selectbox("Source", ["yfinance"], index=0)
else:
    symbol_default = "BTC/USDT"
    symbol = st.sidebar.text_input("Symbol (Crypto)", value=symbol_default).upper().strip()
    tf = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3)
    data_source = st.sidebar.selectbox("Source", ["ccxt:binance"], index=0)

auto_refresh = st.sidebar.checkbox("Auto refresh", value=True)
refresh_sec = st.sidebar.slider("Refresh seconds", 10, 120, 30)

st.sidebar.markdown("---")
atr_stop = st.sidebar.slider("ATR Stop (x)", 0.5, 3.0, 1.5, 0.1)
atr_tp1 = st.sidebar.slider("ATR TP1 (x)", 0.5, 3.0, 1.0, 0.1)
atr_tp2 = st.sidebar.slider("ATR TP2 (x)", 0.5, 5.0, 2.0, 0.1)

# -------------------------
# Header
# -------------------------
c1, c2, c3, c4 = st.columns([2.0, 1.2, 1.2, 1.2])

with c1:
    st.markdown("## 🚀 ROXY Trader Dashboard")
    st.caption("Candles + Indicators + Signals + Alerts (safe & explainable)")

# Fetch live
with st.spinner("Cargando data..."):
    if market_mode == "stocks":
        df_live = fetch_yf(symbol, tf, lookback_days=365 if tf == "1d" else 90)
    else:
        df_live = fetch_ccxt(symbol, tf, limit=500, exchange_id="binance")

df_live = ensure_ohlcv(df_live)

sig, score, meta = opportunity_ai(df_live)
levels = trade_levels(df_live, atr_mult_stop=atr_stop, atr_mult_tp1=atr_tp1, atr_mult_tp2=atr_tp2)

with c2:
    st.metric("Signal", sig)
with c3:
    st.metric("Score", str(score))
with c4:
    st.metric("RR(TP2)", "-" if not levels else fnum(levels.get("rr_tp2")))

# Reasons
st.markdown("### 🧠 Roxy Explicación (por qué)")
if isinstance(meta, dict):
    reasons = meta.get("reasons", [])
    if reasons:
        st.write("• " + "\n• ".join(reasons))
    else:
        st.caption("Sin razones fuertes (señal débil).")

# Chart
build_candles(df_live, f"{symbol} ({market_mode.upper()}) - {tf}", levels=levels)

# -------------------------
# Alerts Panel + History
# -------------------------
st.markdown("---")
st.subheader("🚨 Alertas")

df_scan = pd.DataFrame(
    [
        {
            "ts": now_str(),
            "market": market_mode,
            "symbol": symbol,
            "tf": tf,
            "signal": sig,
            "score": score,
            "rr_tp2": None if not levels else levels.get("rr_tp2"),
            "entry": None if not levels else levels.get("entry"),
            "stop": None if not levels else levels.get("stop"),
            "tp2": None if not levels else levels.get("tp2"),
        }
    ]
)

append_history(df_scan.iloc[0].to_dict())

alerts = df_scan[df_scan["signal"].isin(["BUY", "PRE-BUY"])].copy()
if alerts.empty:
    st.info("No hay BUY/PRE-BUY ahora mismo.")
else:
    st.success("Oportunidades activas:")
    show = alerts.copy()
    for col in ["rr_tp2", "entry", "stop", "tp2"]:
        show[col] = show[col].map(fnum)
    st.dataframe(show[["symbol", "tf", "signal", "score", "rr_tp2", "entry", "stop", "tp2"]], use_container_width=True)

# latest_alert.txt
try:
    latest_path = ALERTS_DIR / "latest_alert.txt"
    if not alerts.empty:
        lines = []
        for _, r in alerts.iterrows():
            lines.append(
                f"{market_mode.upper()} {r['symbol']} [{r['tf']}] {r['signal']} | "
                f"Score {int(r.get('score',0))} | RR2 {fnum(r.get('rr_tp2'))} | Entry {fnum(r.get('entry'))}"
            )
        latest_path.write_text("\n".join(lines).strip(), encoding="utf-8")
except Exception:
    pass

st.markdown("---")
st.subheader("🗃️ Historial reciente (DB local)")
hist = load_recent_scans(limit=200)
if hist is None or hist.empty:
    st.caption("Sin historial aún.")
else:
    st.dataframe(hist.tail(200), use_container_width=True, height=260)

# -------------------------
# Auto refresh loop
# -------------------------
if auto_refresh:
    time.sleep(int(refresh_sec))
    st.rerun()
