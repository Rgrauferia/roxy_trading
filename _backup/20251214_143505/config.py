# =========================
# WATCHLIST DEFAULTS
# =========================
CRYPTO_SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD"]
STOCK_SYMBOLS = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "AMD", "PLTR", "COIN"]

# Timeframes
TIMEFRAMES = ["1h", "4h"]
STOCK_INTERVAL = "1h"

# Risk / levels
ATR_MULT_STOP = 2.0
ATR_MULT_TP1 = 2.0
ATR_MULT_TP2 = 3.5

# Filters
TOP_N = 10
MIN_TECH_SCORE = 15
MIN_GROWTH_SCORE = 35

# Data depth
CRYPTO_OHLCV_LIMIT = 500
STOCK_PERIOD = "6mo"

# Output
EXPORT_CSV = True
OUTPUT_DIR = "output"

# Señales / umbrales (ajústalo a tu gusto)
BUY_TECH_SCORE = 55
WATCH_TECH_SCORE = 30

BUY_GROWTH_SCORE = 65
WATCH_GROWTH_SCORE = 45

# Risk/Reward mínimo para aceptar un trade
MIN_RR = 0.5

# RR mínimo SOLO para BUY usando TP2
MIN_RR_BUY_TP2 = 1.1

# PRE-BUY (casi BUY): score cerca del BUY y RR(TP2) bueno
PREBUY_TECH_SCORE = 45
PREBUY_MIN_RR_TP2 = 1.1
