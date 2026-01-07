# ===============================
# WATCHLISTS
# ===============================
CRYPTO_SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD"]
STOCK_SYMBOLS = [
    "AAPL",
    "PLTR",
    "TSLA",
    "META",
    "NVDA",
    "AMD",
    "COIN",
    "AMZN",
    "MSFT",
]

TIMEFRAMES = ["1h", "4h"]
STOCK_INTERVAL = "1h"

# ===============================
# TECH SCORES
# ===============================
BUY_TECH_SCORE = 55
PREBUY_TECH_SCORE = 40
WATCH_TECH_SCORE = 30

# ===============================
# GROWTH SCORES
# ===============================
BUY_GROWTH_SCORE = 65
WATCH_GROWTH_SCORE = 45

# ===============================
# RISK / REWARD
# ===============================
MIN_RR_BUY_TP2 = 1.10
PREBUY_MIN_RR_TP2 = 1.20

# ===============================
# RANKING WEIGHTS
# ===============================
W_SCORE = 0.6
W_RRTP2 = 0.4
RR_CAP = 2.0

# ===============================
# CONFIRMATION
# ===============================
REQUIRE_TF_CONFIRM = False
CONFIRM_TIMEFRAMES = ("1h", "4h")

# ===============================
# OUTPUT
# ===============================
TOP_PICKS_N = 5
OUTPUT_DIR = "output"
ALERTS_DIR = "alerts"
TOP_PICKS_FILE = f"{ALERTS_DIR}/top_picks.txt"
LATEST_ALERT_FILE = f"{ALERTS_DIR}/latest_alert.txt"

# ===============================
# AI / Grok model toggles
# ===============================
import os

# If set to '1' or 'true' (case-insensitive), enable Grok Code Fast 1 features
ENABLE_GROK_CODE_FAST = os.getenv("ENABLE_GROK_CODE_FAST", os.getenv("GROK_CODE_FAST", "0")).lower() in ("1", "true", "yes")
# Admin token for sensitive controls (start/stop snapshot). Set to a secure value in production.
ADMIN_TOKEN = os.getenv("ROXY_ADMIN_TOKEN")

# ===============================
# BACKTEST DEFAULTS
# ===============================
BACKTEST_STARTING_CAPITAL = 10000.0
BACKTEST_POSITION_SIZE = 0.01
BACKTEST_SLIPPAGE_PCT = 0.0005
BACKTEST_FEE_PCT = 0.0005
