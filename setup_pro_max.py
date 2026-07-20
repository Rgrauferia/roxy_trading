# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB = DATA_DIR / "roxy.db"

DEFAULT_STOCKS_120 = [
    # Mega/Tech
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "GOOG",
    "META",
    "TSLA",
    "AMD",
    "INTC",
    "AVGO",
    "ORCL",
    "CRM",
    "ADBE",
    "QCOM",
    "CSCO",
    "IBM",
    "NOW",
    "SHOP",
    "UBER",
    # Finance
    "JPM",
    "BAC",
    "WFC",
    "C",
    "GS",
    "MS",
    "V",
    "MA",
    "AXP",
    "PYPL",
    "COIN",
    "SCHW",
    "BLK",
    # Consumer
    "COST",
    "WMT",
    "TGT",
    "HD",
    "LOW",
    "NKE",
    "SBUX",
    "MCD",
    "KO",
    "PEP",
    "DIS",
    "NFLX",
    "CMCSA",
    "ROKU",
    # Healthcare
    "UNH",
    "JNJ",
    "PFE",
    "MRK",
    "ABBV",
    "LLY",
    "TMO",
    "DHR",
    "ABT",
    "ISRG",
    # Energy / Industrials
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "BA",
    "CAT",
    "GE",
    "MMM",
    "DE",
    "HON",
    "LMT",
    "RTX",
    "NOC",
    # Semis/ETFs-ish proxies
    "SMH",
    "SOXX",
    "QQQ",
    "SPY",
    "IWM",
    "DIA",
    # Growth favorites
    "PLTR",
    "SNOW",
    "CRWD",
    "PANW",
    "DDOG",
    "NET",
    "MDB",
    "ZS",
    "RBLX",
    "U",
    "SQ",
    "DKNG",
    "HOOD",
    "ABNB",
    # EV/Auto
    "RIVN",
    "LCID",
    "F",
    "GM",
    # AI/Data
    "ARM",
    "MU",
    "TSM",
    "ASML",
    # Misc
    "NFLX",
    "INTU",
    "LULU",
    "TTEK",
]

DEFAULT_CRYPTO = [
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "BNB/USD",
    # si tu exchange los tiene, aparecen; si no, no pasa nada
    "DOGE/USD",
    "SHIB/USD",
    "PEPE/USD",
    "BONK/USD",
    "WIF/USDT",
    "FLOKI/USD",
    "AVAX/USD",
    "XRP/USD",
    "LINK/USD",
    "ADA/USD",
    "MATIC/USD",
    "DOT/USD",
    "LTC/USD",
]


def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,         -- 'stock' or 'crypto'
        symbol TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """
    )
    con.commit()
    con.close()


def seed_watchlist():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # stocks
    for s in DEFAULT_STOCKS_120:
        cur.execute("INSERT OR IGNORE INTO watchlist(kind,symbol,enabled) VALUES('stock',?,1)", (s,))

    # crypto
    for c in DEFAULT_CRYPTO:
        cur.execute("INSERT OR IGNORE INTO watchlist(kind,symbol,enabled) VALUES('crypto',?,1)", (c,))

    con.commit()
    con.close()


def write_files():
    p1 = DATA_DIR / "watchlist_stocks.txt"
    p2 = DATA_DIR / "watchlist_crypto.txt"
    p1.write_text("\n".join(sorted(set(DEFAULT_STOCKS_120))) + "\n")
    p2.write_text("\n".join(sorted(set(DEFAULT_CRYPTO))) + "\n")


if __name__ == "__main__":
    init_db()
    seed_watchlist()
    write_files()
    print("✅ PRO MAX listo: data/roxy.db + watchlists en data/")
