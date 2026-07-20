import os
import time
import math
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytz
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Alpaca (alpaca-py)
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.trading.requests import TakeProfitRequest, StopLossRequest

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from roxy_trader.indicators import exponential_moving_average, session_vwap, wilder_rsi

# ----------------------------
# CONFIG
# ----------------------------
load_dotenv()

EST = pytz.timezone("America/New_York")

API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
API_SECRET = os.getenv("ALPACA_API_SECRET", "").strip()
PAPER = os.getenv("ALPACA_PAPER", "true").lower() == "true"

if not API_KEY or not API_SECRET:
    raise SystemExit("Faltan ALPACA_API_KEY / ALPACA_API_SECRET en .env")

SYMBOLS = ["SPY"]  # empieza con 1 simbolo (SPY/QQQ/AAPL). Luego agregas mas.
TIMEFRAME = TimeFrame.Minute
LOOKBACK_BARS = 120  # minimo 60-100 recomendado
CHECK_EVERY_SECONDS = 30  # revisa cada 30s, pero decide con la ultima vela cerrada
RISK_PER_TRADE = 0.005  # 0.5% del equity
RR = 2.0  # take profit = 2R
MAX_TRADES_PER_DAY = 3
MAX_LOSSES_PER_DAY = 2
USE_VWAP = True

# Modo operativo
ENABLE_LONG = True
ENABLE_SHORT = True

# Horario recomendado: evita 9:30-9:45
NO_TRADE_FIRST_MINUTES = 15

LOG_LEVEL = logging.INFO

# ----------------------------
# LOGGING
# ----------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ----------------------------
# HELPERS: Indicators
# ----------------------------
def ema(series: pd.Series, period: int) -> pd.Series:
    return exponential_moving_average(series, period)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    return wilder_rsi(series, period)


def vwap(df: pd.DataFrame) -> pd.Series:
    normalized = df.rename(columns={"timestamp": "ts"}) if "ts" not in df.columns else df
    return session_vwap(normalized)


# ----------------------------
# STRATEGY SIGNALS
# ----------------------------
@dataclass
class Signal:
    symbol: str
    side: str  # "buy" or "sell"
    entry: float
    stop: float
    take_profit: float
    qty: int
    reason: str


def compute_signal(df: pd.DataFrame, symbol: str) -> Signal | None:
    """
    df: DataFrame con columnas: timestamp, close, volume (y opcional high/low)
    Usa la ultima vela CERRADA (penultima fila si la ultima esta en progreso).
    """
    if len(df) < 50:
        return None

    df = df.copy()
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["rsi14"] = rsi(df["close"], 14)

    if USE_VWAP:
        df["vwap"] = vwap(df)

    # Usar ultima vela cerrada
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Cruces EMA: confirmacion en cierre
    crossed_up = (prev["ema9"] <= prev["ema21"]) and (last["ema9"] > last["ema21"])
    crossed_down = (prev["ema9"] >= prev["ema21"]) and (last["ema9"] < last["ema21"])

    price = float(last["close"])
    r = float(last["rsi14"])

    # VWAP filtro
    above_vwap = True
    below_vwap = True
    if USE_VWAP and "vwap" in df.columns and not math.isnan(float(last["vwap"])):
        above_vwap = price > float(last["vwap"])
        below_vwap = price < float(last["vwap"])

    # Reglas LONG
    if ENABLE_LONG and crossed_up and above_vwap and (40 <= r <= 65) and (price > float(last["ema9"])):
        # stop: minimo vela anterior si hay low; si no, usa close anterior como aproximacion
        if "low" in df.columns:
            stop = float(prev["low"])
        else:
            stop = float(prev["close"])  # fallback
        entry = price
        if stop >= entry:
            return None
        return Signal(
            symbol=symbol,
            side="buy",
            entry=entry,
            stop=stop,
            take_profit=entry + (entry - stop) * RR,
            qty=0,  # se calcula despues con equity
            reason=f"LONG: EMA9>EMA21 cross + VWAP + RSI={r:.1f}",
        )

    # Reglas SHORT
    if ENABLE_SHORT and crossed_down and below_vwap and (35 <= r <= 60) and (price < float(last["ema9"])):
        if "high" in df.columns:
            stop = float(prev["high"])
        else:
            stop = float(prev["close"])  # fallback
        entry = price
        if stop <= entry:
            return None
        return Signal(
            symbol=symbol,
            side="sell",
            entry=entry,
            stop=stop,
            take_profit=entry - (stop - entry) * RR,
            qty=0,
            reason=f"SHORT: EMA9<EMA21 cross + VWAP + RSI={r:.1f}",
        )

    return None


# ----------------------------
# TRADING / RISK
# ----------------------------
class RoxyAlpacaBot:
    def __init__(self):
        self.trading = TradingClient(API_KEY, API_SECRET, paper=PAPER)
        self.data = StockHistoricalDataClient(API_KEY, API_SECRET)

        self.trades_today = 0
        self.losses_today = 0
        self.today = datetime.now(EST).date()

    def reset_daily_counters_if_needed(self):
        now_date = datetime.now(EST).date()
        if now_date != self.today:
            self.today = now_date
            self.trades_today = 0
            self.losses_today = 0
            logging.info("Nuevo dia: contadores reiniciados.")

    def market_open_ok(self) -> bool:
        clock = self.trading.get_clock()
        if not clock.is_open:
            return False

        # Evitar primeros minutos desde apertura
        t = clock.timestamp.astimezone(EST)
        if t.hour == 9 and t.minute < (30 + NO_TRADE_FIRST_MINUTES):
            return False
        return True

    def get_equity(self) -> float:
        acct = self.trading.get_account()
        return float(acct.equity)

    def has_position(self, symbol: str) -> bool:
        try:
            pos = self.trading.get_open_position(symbol)
            return pos is not None
        except Exception:
            return False

    def open_orders_exist(self, symbol: str) -> bool:
        orders = self.trading.get_orders(status="open")
        for o in orders:
            if getattr(o, "symbol", None) == symbol:
                return True
        return False

    def fetch_bars(self, symbol: str) -> pd.DataFrame:
        # Pedimos hasta "ahora - 1 minuto" para asegurarnos de vela cerrada
        end = datetime.now(EST).replace(second=0, microsecond=0) - timedelta(minutes=1)
        start = end - timedelta(minutes=LOOKBACK_BARS)

        req = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TIMEFRAME,
            start=start,
            end=end,
            feed="iex",  # en paper suele funcionar; si tienes data subscription puedes usar "sip"
        )
        bars = self.data.get_stock_bars(req).df

        # Si viene multiindex (symbol, timestamp), lo normalizamos
        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.reset_index()

        # Esperado: columns: symbol, timestamp, open, high, low, close, volume
        bars["timestamp"] = pd.to_datetime(bars["timestamp"]).dt.tz_convert(EST)
        bars = bars.sort_values("timestamp")

        # Filtrar solo el simbolo
        if "symbol" in bars.columns:
            bars = bars[bars["symbol"] == symbol].copy()

        return bars[["timestamp", "open", "high", "low", "close", "volume"]].dropna()

    def position_size(self, equity: float, entry: float, stop: float) -> int:
        risk_dollars = equity * RISK_PER_TRADE
        per_share_risk = abs(entry - stop)
        if per_share_risk <= 0:
            return 0
        qty = int(risk_dollars / per_share_risk)
        return max(qty, 0)

    def submit_bracket(self, sig: Signal):
        equity = self.get_equity()
        qty = self.position_size(equity, sig.entry, sig.stop)
        if qty <= 0:
            logging.info(
                f"{sig.symbol}: qty=0 (entry={sig.entry:.2f}, stop={sig.stop:.2f})"
            )
            return

        # Reglas de freno diario
        if self.trades_today >= MAX_TRADES_PER_DAY:
            logging.info("Limite de trades diarios alcanzado.")
            return
        if self.losses_today >= MAX_LOSSES_PER_DAY:
            logging.info("Limite de perdidas diarias alcanzado.")
            return

        side = OrderSide.BUY if sig.side == "buy" else OrderSide.SELL

        order = MarketOrderRequest(
            symbol=sig.symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=round(sig.take_profit, 2)),
            stop_loss=StopLossRequest(stop_price=round(sig.stop, 2)),
        )

        logging.info(
            f"ENVIANDO {sig.symbol} {sig.side.upper()} qty={qty} "
            f"entry~{sig.entry:.2f} SL={sig.stop:.2f} TP={sig.take_profit:.2f} | {sig.reason}"
        )

        try:
            self.trading.submit_order(order)
            self.trades_today += 1
            logging.info(f"Orden enviada. Trades hoy: {self.trades_today}")
        except Exception as e:
            logging.error(f"Error enviando orden: {e}")

    def monitor_closed_orders_for_losses(self):
        """
        Simple: cuenta perdidas al detectar fills cerrados (approx).
        Para algo mas exacto: usar account activities y P/L real.
        """
        # Mantenerlo simple: no incrementamos perdidas automaticamente aqui
        # porque requiere reconciliar fills y P/L. Lo agregamos luego si quieres.
        pass

    def run(self):
        logging.info(
            f"Roxy Alpaca Bot iniciado | PAPER={PAPER} | Symbols={SYMBOLS}"
        )
        while True:
            try:
                self.reset_daily_counters_if_needed()

                if not self.market_open_ok():
                    logging.info("Mercado cerrado o en ventana NO-trade. Esperando...")
                    time.sleep(60)
                    continue

                for sym in SYMBOLS:
                    if self.has_position(sym):
                        logging.info(f"{sym}: ya hay posicion abierta. Saltando.")
                        continue
                    if self.open_orders_exist(sym):
                        logging.info(f"{sym}: ya hay ordenes abiertas. Saltando.")
                        continue

                    df = self.fetch_bars(sym)
                    if df.empty or len(df) < 50:
                        logging.info(f"{sym}: no hay suficientes barras.")
                        continue

                    sig = compute_signal(df, sym)
                    if sig:
                        self.submit_bracket(sig)
                    else:
                        logging.info(f"{sym}: sin senal.")

                time.sleep(CHECK_EVERY_SECONDS)

            except KeyboardInterrupt:
                logging.info("Bot detenido por el usuario.")
                break
            except Exception as e:
                logging.error(f"Error general: {e}")
                time.sleep(30)


if __name__ == "__main__":
    bot = RoxyAlpacaBot()
    bot.run()
