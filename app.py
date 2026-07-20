# -*- coding: utf-8 -*-
import hashlib
import json
from datetime import datetime
from pathlib import Path

import config
import roxy_scanner as rs
try:
    import storage
except Exception:  # optional persistence
    storage = None
from logging_config import get_logger
from notifier import notify_if_changed
from durable_storage import atomic_write_csv, atomic_write_text

logger = get_logger("roxy")
# ===============================
# SAFE DEFAULTS (no rompe si falta algo en config.py)
# ===============================
ATR_MULT_STOP = getattr(config, "ATR_MULT_STOP", 1.5)
ATR_MULT_TP1 = getattr(config, "ATR_MULT_TP1", 1.0)
ATR_MULT_TP2 = getattr(config, "ATR_MULT_TP2", 2.0)

BUY_TECH_SCORE = getattr(config, "BUY_TECH_SCORE", 60)
PREBUY_TECH_SCORE = getattr(config, "PREBUY_TECH_SCORE", 40)
WATCH_TECH_SCORE = getattr(config, "WATCH_TECH_SCORE", 30)

MIN_RR_BUY_TP2 = getattr(config, "MIN_RR_BUY_TP2", 1.5)
PREBUY_MIN_RR_TP2 = getattr(config, "PREBUY_MIN_RR_TP2", 1.2)

W_SCORE = getattr(config, "W_SCORE", 0.6)
W_RRTP2 = getattr(config, "W_RRTP2", 0.4)
RR_CAP = getattr(config, "RR_CAP", 3.0)

TOP_PICKS_N = getattr(config, "TOP_PICKS_N", 5)

# common lists from config
CRYPTO_SYMBOLS = getattr(config, "CRYPTO_SYMBOLS", [])
STOCK_SYMBOLS = getattr(config, "STOCK_SYMBOLS", [])
TIMEFRAMES = getattr(config, "TIMEFRAMES", ["1h", "4h"])
STOCK_INTERVAL = getattr(config, "STOCK_INTERVAL", "1h")


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR_P = BASE_DIR / "output"
ALERTS_DIR_P = BASE_DIR / "alerts"
LOGS_DIR_P = BASE_DIR / "logs"

OUTPUT_DIR_P.mkdir(exist_ok=True)
ALERTS_DIR_P.mkdir(exist_ok=True)
LOGS_DIR_P.mkdir(exist_ok=True)

ALERT_HASH_FILE = ALERTS_DIR_P / "latest_alert.hash"
ALERT_TEXT_FILE = ALERTS_DIR_P / "latest_alert.txt"
TOP_PICKS_FILE = ALERTS_DIR_P / "top_picks.txt"
SUMMARY_JSON = ALERTS_DIR_P / "latest_summary.json"


def fnum(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "-"


def export_csv(df, name):
    if df is None or getattr(df, "empty", True):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR_P / f"{name}_{ts}.csv"
    atomic_write_csv(df, path)
    return str(path)


def md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def write_if_changed(path: Path, text: str):
    old = path.read_text() if path.exists() else ""
    if text != old:
        atomic_write_text(text, path)


def write_alerts_if_changed(lines):
    if not lines:
        # Limpia alerta si no hay nada
        write_if_changed(ALERT_TEXT_FILE, "")
        write_if_changed(ALERT_HASH_FILE, "")
        return

    text = "\n".join(lines) + "\n"
    h = md5_text(text)
    old = ALERT_HASH_FILE.read_text().strip() if ALERT_HASH_FILE.exists() else ""

    if h != old:
        ALERT_HASH_FILE.write_text(h)
        ALERT_TEXT_FILE.write_text(text)


def ensure_trade_meta(df):
    if df is None or getattr(df, "empty", True):
        return df
    fn = getattr(rs, "add_trade_meta", None)
    if callable(fn):
        # Algunos builds usan kwargs, otros posicional
        try:
            return fn(df, buy_score=BUY_TECH_SCORE, watch_score=WATCH_TECH_SCORE)
        except TypeError:
            return fn(df, BUY_TECH_SCORE, WATCH_TECH_SCORE)
    return df


def ensure_filter_rr(df):
    if df is None or getattr(df, "empty", True):
        return df
    fn = getattr(rs, "filter_rr", None)
    if callable(fn):
        return fn(df)
    return df


def ensure_rank(df):
    if df is None or getattr(df, "empty", True):
        return df

    # Si existe rank_trades, úsalo
    fn = getattr(rs, "rank_trades", None)
    if callable(fn):
        return fn(df)

    # Si no existe, crea rank_score simple
    x = df.copy()
    if "rr_tp2" not in x.columns:
        x["rr_tp2"] = None
    if "signal" not in x.columns:
        x["signal"] = "AVOID"

    def bonus(sig):
        sig = (sig or "AVOID").upper()
        if sig == "BUY":
            return 15.0
        if sig == "PRE-BUY":
            return 10.0
        if sig == "WATCH":
            return 3.0
        return 0.0

    rr2 = x["rr_tp2"].fillna(0).astype(float).clip(upper=float(RR_CAP))
    x["rank_score"] = float(W_SCORE) * x["score"].astype(float) + float(W_RRTP2) * rr2 + x["signal"].apply(bonus)
    x = x.sort_values("rank_score", ascending=False)
    return x


def print_trade(r):
    sym = r.get("symbol", "-")
    tf = r.get("tf", r.get("interval", "-"))
    score = int(r.get("score", 0) or 0)
    sig = r.get("signal", "-")

    lines = []
    lines.append(f"• {sym} [{tf}]  Score {score}/100")
    lines.append(f"  Signal: {sig} | RR(TP1): {fnum(r.get('rr_tp1'))} | RR(TP2): {fnum(r.get('rr_tp2'))}")
    lines.append(f"  Rank  : {fnum(r.get('rank_score'))}")
    lines.append(f"  Entry : {fnum(r.get('entry'))}")
    lines.append(f"  SL    : {fnum(r.get('stop'))}")
    lines.append(f"  TP1   : {fnum(r.get('tp1'))}")
    lines.append(f"  TP2   : {fnum(r.get('tp2'))}")

    reasons = r.get("reasons") or r.get("growth_reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    if reasons:
        lines.append("  Razones: " + "; ".join(reasons[:6]))

    for line in lines:
        logger.info(line)


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("=== ROXY TRADING SCANNER (PRO MAX) ===")
    logger.info(ts)
    try:
        logger.info(f"Crypto symbols: {len(CRYPTO_SYMBOLS)}")
    except Exception:
        logger.info("Crypto symbols: ?")
    try:
        logger.info(f"Stock symbols : {len(STOCK_SYMBOLS)}")
    except Exception:
        logger.info("Stock symbols: ?")
    logger.info(f"TFs Crypto    : {TIMEFRAMES}")
    logger.info(f"Interval Stock: {STOCK_INTERVAL}")

    alerts = []
    top_picks_lines = []
    summary = {"timestamp": ts, "top_picks": [], "alerts": []}

    # ---------------- CRYPTO ----------------
    logger.info("📡 Escaneando CRIPTO...")
    scan_crypto_fn = getattr(rs, "scan_crypto", None)
    cdf = None
    if callable(scan_crypto_fn):
        # Tu build anterior usa scan_crypto( symbols, timeframes, atr_mult... )
        try:
            cdf = scan_crypto_fn(
                CRYPTO_SYMBOLS,
                timeframes=TIMEFRAMES,
                atr_mult_stop=ATR_MULT_STOP,
                atr_mult_tp1=ATR_MULT_TP1,
                atr_mult_tp2=ATR_MULT_TP2,
            )
        except TypeError:
            # fallback si tu scan_crypto ya tiene defaults internos
            cdf = scan_crypto_fn()

    cdf = ensure_trade_meta(cdf)
    cdf = ensure_filter_rr(cdf)
    cdf = ensure_rank(cdf)

    if cdf is None or getattr(cdf, "empty", True):
        logger.info("No hubo resultados de cripto.")
    else:
        logger.info("🔥 TOP CRIPTO (ranked)")
        for _, r in cdf.head(10).iterrows():
            print_trade(r)
            if r.get("signal") in ("BUY", "PRE-BUY"):
                sym = r.get("symbol")
                tf = r.get("tf", r.get("interval", "-"))
                alerts.append(
                    f"CRYPTO {sym} [{tf}] {r.get('signal')} | "
                    f"Rank {fnum(r.get('rank_score'))} | Entry {fnum(r.get('entry'))}"
                )

    # ---------------- STOCKS TECH ----------------
    logger.info("📡 Escaneando STOCKS (técnico)...")

    # Nombre correcto en tu repo: scan_stocks
    scan_stocks_fn = getattr(rs, "scan_stocks", None)
    sdf = None
    if callable(scan_stocks_fn):
        try:
            sdf = scan_stocks_fn(
                STOCK_SYMBOLS,
                interval=STOCK_INTERVAL,
                atr_mult_stop=ATR_MULT_STOP,
                atr_mult_tp1=ATR_MULT_TP1,
                atr_mult_tp2=ATR_MULT_TP2,
            )
        except TypeError:
            sdf = scan_stocks_fn(STOCK_SYMBOLS)

    sdf = ensure_trade_meta(sdf)
    sdf = ensure_filter_rr(sdf)
    sdf = ensure_rank(sdf)

    if sdf is None or getattr(sdf, "empty", True):
        logger.info("No hubo stocks técnicos.")
    else:
        logger.info("🚀 TOP STOCKS (ranked)")
        for _, r in sdf.head(10).iterrows():
            print_trade(r)
            if r.get("signal") in ("BUY", "PRE-BUY"):
                sym = r.get("symbol")
                tf = r.get("tf", r.get("interval", "-"))
                alerts.append(
                    f"STOCK {sym} [{tf}] {r.get('signal')} | "
                    f"Rank {fnum(r.get('rank_score'))} | Entry {fnum(r.get('entry'))}"
                )

    # ---------------- GROWTH ----------------
    logger.info("📡 Escaneando STOCKS (growth)...")
    scan_growth_fn = getattr(rs, "scan_growth_stocks", None)
    gdf = None
    if callable(scan_growth_fn):
        try:
            gdf = scan_growth_fn(STOCK_SYMBOLS, interval=STOCK_INTERVAL, period="1y")
        except TypeError:
            gdf = scan_growth_fn(STOCK_SYMBOLS)

    if gdf is None or getattr(gdf, "empty", True):
        logger.info("No hubo growth.")
    else:
        logger.info("🌱 TOP GROWTH")
        for _, r in gdf.head(10).iterrows():
            print_trade(r)

    # ---------------- TOP PICKS ----------------
    def collect(label, df):
        if df is None or getattr(df, "empty", True):
            return
        for _, r in df.head(int(TOP_PICKS_N)).iterrows():
            sym = r.get('symbol', '-')
            tf = r.get('tf', r.get('interval', '-'))
            line = (
                f"{label} {sym} [{tf}] {r.get('signal','-')} | Rank {fnum(r.get('rank_score'))} | "
                f"RR2 {fnum(r.get('rr_tp2'))} | Entry {fnum(r.get('entry'))}"
            )
            top_picks_lines.append(line)
            summary["top_picks"].append(
                {
                    "bucket": label,
                    "symbol": r.get("symbol"),
                    "tf": r.get("tf", r.get("interval")),
                    "signal": r.get("signal"),
                    "rank": r.get("rank_score"),
                    "score": r.get("score"),
                    "rr_tp2": r.get("rr_tp2"),
                    "entry": r.get("entry"),
                    "stop": r.get("stop"),
                    "tp2": r.get("tp2"),
                }
            )

    collect("CRYPTO", cdf)
    collect("STOCKS", sdf)

    if top_picks_lines:
        write_if_changed(TOP_PICKS_FILE, "\n".join(top_picks_lines) + "\n")
        logger.info(f"🏁 TOP PICKS guardados en: {TOP_PICKS_FILE}")

    # ---------------- ALERTAS ----------------
    if alerts:
        logger.info("🚨 ALERTAS (BUY / PRE-BUY) 🚨")
        for a in alerts:
            logger.info("• %s", a)
        write_alerts_if_changed(alerts)
        try:
            notify_if_changed(alerts)
        except Exception:
            logger.exception("notify_if_changed failed")
        summary["alerts"] = alerts
    else:
        write_alerts_if_changed([])
        summary["alerts"] = []

    write_if_changed(SUMMARY_JSON, json.dumps(summary, indent=2) + "\n")
    # persist summary to local DB if available
    if storage is not None:
        try:
            storage.save_summary(summary)
        except Exception:
            logger.exception("Failed to save summary to DB")

    # ---------------- EXPORTS ----------------
    logger.info("💾 Exportando CSV...")
    logger.info(" Crypto : %s", export_csv(cdf, "crypto_tech"))
    logger.info(" Stocks : %s", export_csv(sdf, "stocks_tech"))
    # persist scans to DB if storage is available
    if storage is not None:
        try:
            storage.save_scan_df(cdf, market="crypto")
            storage.save_scan_df(sdf, market="stock")
            storage.save_scan_df(gdf, market="growth")
        except Exception:
            logger.exception("Failed to save scans to DB")
    logger.info(" Growth : %s", export_csv(gdf, "stocks_growth"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Unhandled error in main")
        raise
