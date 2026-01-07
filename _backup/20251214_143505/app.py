import os
from datetime import datetime
from pathlib import Path

import roxy_scanner as rs
from config import (
    ATR_MULT_STOP,
    ATR_MULT_TP1,
    ATR_MULT_TP2,
    BUY_GROWTH_SCORE,
    BUY_TECH_SCORE,
    CRYPTO_SYMBOLS,
    MIN_RR_BUY_TP2,
    PREBUY_MIN_RR_TP2,
    PREBUY_TECH_SCORE,
    STOCK_INTERVAL,
    STOCK_SYMBOLS,
    TIMEFRAMES,
    WATCH_GROWTH_SCORE,
    WATCH_TECH_SCORE,
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
ALERTS_DIR = BASE_DIR / "alerts"

OUTPUT_DIR.mkdir(exist_ok=True)
ALERTS_DIR.mkdir(exist_ok=True)

ALERT_FILE = ALERTS_DIR / "latest_alert.txt"


def fnum(x):
    if x is None:
        return "—"
    try:
        return f"{float(x):.2f}"
    except Exception:
        return str(x)


def write_alert_file(lines):
    """Anti-spam: solo escribe si cambió el contenido."""
    new_text = "\n".join(lines) + "\n"
    old_text = ALERT_FILE.read_text() if ALERT_FILE.exists() else ""
    if new_text != old_text:
        ALERT_FILE.write_text(new_text)


def export_csv(df, name):
    if df is None or df.empty:
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{name}_{ts}.csv"
    df.to_csv(path, index=False)
    return str(path)


def add_trade_meta_safe(df, buy_score, watch_score):
    fn = getattr(rs, "add_trade_meta", None)
    if fn is None or df is None or df.empty:
        return df
    return fn(df, buy_score=buy_score, watch_score=watch_score)


def apply_advanced_signal(df):
    """Usa signal_tech_advanced si existe (BUY exige RR TP2 mínimo + PRE-BUY opcional)."""
    if df is None or df.empty:
        return df
    df = df.copy()

    adv = getattr(rs, "signal_tech_advanced", None)
    if adv is None or "rr_tp2" not in df.columns:
        return df

    df["signal"] = df.apply(
        lambda r: adv(
            r.get("score"),
            r.get("rr_tp2"),
            BUY_TECH_SCORE,
            WATCH_TECH_SCORE,
            MIN_RR_BUY_TP2,
            PREBUY_TECH_SCORE,
            PREBUY_MIN_RR_TP2,
        ),
        axis=1,
    )
    return df


def filter_rr_safe(df):
    fn = getattr(rs, "filter_rr", None)
    if fn is None or df is None or df.empty:
        return df
    return fn(df)


def print_trade_rows(df, topn=12):
    if df is None or df.empty:
        return
    for _, r in df.head(topn).iterrows():
        sym = r.get("symbol", "—")
        tf = r.get("tf", "—")
        score = int(r.get("score", 0)) if r.get("score") is not None else 0
        sig = r.get("signal", "—")
        rr1 = r.get("rr_tp1")
        rr2 = r.get("rr_tp2")

        print(f"\n• {sym} [{tf}]  Score {score}/100")
        print(f"  Signal: {sig} | RR(TP1): {fnum(rr1)} | RR(TP2): {fnum(rr2)}")
        print(f"  Entry : {fnum(r.get('entry'))}")
        print(f"  SL    : {fnum(r.get('stop'))}")
        print(f"  TP1   : {fnum(r.get('tp1'))}")
        print(f"  TP2   : {fnum(r.get('tp2'))}")

        reasons = r.get("reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        print("  Razones: " + ("; ".join(reasons[:6]) if reasons else ""))


def main():
    print("\n=== ROXY TRADING SCANNER (PRO+SIGNALS) ===\n")
    print(f"Crypto symbols: {len(CRYPTO_SYMBOLS)}")
    print(f"Stock symbols : {len(STOCK_SYMBOLS)}")
    print(
        f"Umbrales -> TECH: BUY {BUY_TECH_SCORE} WATCH {WATCH_TECH_SCORE} | GROWTH: BUY {BUY_GROWTH_SCORE} WATCH {WATCH_GROWTH_SCORE}"
    )
    print(f"MIN RR BUY (TP2): {MIN_RR_BUY_TP2} | PREBUY: {PREBUY_TECH_SCORE} RR: {PREBUY_MIN_RR_TP2}")

    # ---- CRYPTO ----
    print("\n📡 Escaneando CRIPTO...\n")
    cdf = rs.scan_crypto(
        CRYPTO_SYMBOLS,
        timeframes=TIMEFRAMES,
        atr_mult_stop=ATR_MULT_STOP,
        atr_mult_tp1=ATR_MULT_TP1,
        atr_mult_tp2=ATR_MULT_TP2,
    )
    cdf = add_trade_meta_safe(cdf, BUY_TECH_SCORE, WATCH_TECH_SCORE)
    cdf = apply_advanced_signal(cdf)
    cdf = filter_rr_safe(cdf)

    if cdf is not None and not cdf.empty:
        print("🔥 TOP CRIPTO OPORTUNIDADES")
        print_trade_rows(cdf)
    else:
        print("No hubo resultados de cripto con filtros.")

    # ---- STOCKS TECH ----
    print("\n📡 Escaneando STOCKS (técnico)...\n")
    sdf = rs.scan_stocks(
        STOCK_SYMBOLS,
        interval=STOCK_INTERVAL,
        atr_mult_stop=ATR_MULT_STOP,
        atr_mult_tp1=ATR_MULT_TP1,
        atr_mult_tp2=ATR_MULT_TP2,
    )
    sdf = add_trade_meta_safe(sdf, BUY_TECH_SCORE, WATCH_TECH_SCORE)
    sdf = apply_advanced_signal(sdf)
    sdf = filter_rr_safe(sdf)

    if sdf is not None and not sdf.empty:
        print("🚀 TOP STOCKS OPORTUNIDADES")
        print_trade_rows(sdf)
    else:
        print("No hubo resultados de stocks con filtros.")

    # ---- GROWTH ----
    print("\n📡 Escaneando STOCKS (growth)...\n")
    gdf = rs.scan_growth_stocks(STOCK_SYMBOLS, interval=STOCK_INTERVAL, period="1y")

    if gdf is not None and not gdf.empty:
        sig_fn = getattr(rs, "signal_from_score", None)
        if sig_fn:
            gdf["growth_signal"] = gdf["growth_score"].apply(
                lambda s: sig_fn(s, buy=BUY_GROWTH_SCORE, watch=WATCH_GROWTH_SCORE)
            )
        else:
            gdf["growth_signal"] = gdf["growth_score"].apply(
                lambda s: "BUY" if s >= BUY_GROWTH_SCORE else ("WATCH" if s >= WATCH_GROWTH_SCORE else "AVOID")
            )

        print("🌱 TOP GROWTH CANDIDATES\n")
        for _, r in gdf.head(10).iterrows():
            print(
                f"• {r.get('symbol','—')} [{r.get('tf','—')}] Growth {int(r.get('growth_score',0))}/100 | Signal {r.get('growth_signal','—')}"
            )
            reasons = r.get("growth_reasons") or []
            if isinstance(reasons, str):
                reasons = [reasons]
            print("  Razones: " + ("; ".join(reasons[:6]) if reasons else ""))

    else:
        print("No hubo growth candidates (ajustamos universo/intervalo).")

    # ---- ALERTS ----
    alert_lines = []
    for label, df in [("CRYPTO", cdf), ("STOCKS", sdf)]:
        if df is None or df.empty:
            continue
        hot = df[df["signal"].isin(["BUY", "PRE-BUY"])].head(10)
        for _, r in hot.iterrows():
            rr2 = r.get("rr_tp2")
            rr2_s = "—" if rr2 is None else f"{rr2:.2f}"
            alert_lines.append(
                f"{label} {r.get('symbol','—')} [{r.get('tf','—')}] {r.get('signal','—')} | "
                f"Score {int(r.get('score',0))} | RR(TP2) {rr2_s} | Entry {float(r.get('entry',0)):.2f}"
            )

    if alert_lines:
        print("\n🚨 ALERTAS (BUY / PRE-BUY) 🚨")
        for ln in alert_lines:
            print("•", ln)
        write_alert_file(alert_lines)

    # ---- EXPORT ----
    print("\n💾 Exportando CSV...")
    print(" Crypto :", export_csv(cdf, "crypto_tech"))
    print(" Stocks :", export_csv(sdf, "stocks_tech"))
    print(" Growth :", export_csv(gdf, "stocks_growth"))


if __name__ == "__main__":
    main()
