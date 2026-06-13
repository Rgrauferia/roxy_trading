"""Focused Streamlit app for Roxy AI Trading.

The active UI is centered on the SMA 20/40/100/200 strategy, 15m/1h
confluence, symbol analysis, AI-ranked opportunities, and 24h watch status.
"""

from __future__ import annotations

import base64
import html
import json
import math
import os
import shutil
import socket
import subprocess
import warnings
from urllib.parse import quote
from glob import glob
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import pandas as pd
import sqlite3
import streamlit as st
import altair as alt
try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional runtime dependency
    yf = None

from chart_health import chart_freshness_status as shared_chart_freshness_status
from chart_health import latest_chart_timestamp as shared_latest_chart_timestamp
from chart_health import timeframe_minutes as shared_timeframe_minutes
from config import TOP_PICKS_FILE, ENABLE_GROK_CODE_FAST
import storage
import grok_control
import auth
import notifier
from roxy_paths import alerts_dir, output_dir, project_path
from accuracy_tracker import build_accuracy_report, real_signal_memory_summary
from dashboard_metrics import (
    best_confluence_candidate,
    option_expiry_counts,
    option_quality_points,
    risk_score_points,
    score_distribution,
    setup_counts_by_timeframe,
    signal_counts_by_timeframe,
    target_ladder_counts,
    trade_decision_counts,
)
from moving_average_strategy import analyze_moving_average_setup
from options_strategy import professional_options_feed_status
from salto_strategies import SALTO_STRATEGIES
from symbol_detail import (
    classify_strategy_playbook,
    detect_reference_strategies,
    fetch_symbol_history,
    latest_chart_strategy_events,
    latest_confluence_row,
    latest_symbol_rows,
    prepare_symbol_chart_data,
    resolve_symbol_query,
)
from roxy_ai import (
    DEFAULT_ACCOUNT_EQUITY,
    alert_gate_label,
    apply_global_alert_context,
    autonomous_learning_plan,
    build_brief,
    build_notification_lines,
    build_strategy_lab,
    experiment_status_label,
    human_alert_reason,
    human_trade_action,
    learning_research_queue,
    learning_action_label,
    load_memory,
    market_session_status,
    realtime_health_status,
    safety_mode_label,
    source_freshness_status,
    summarize_alert_gates,
    summarize_strategy_learning,
    write_brief,
)
from platform_credentials import (
    credential_table_rows,
    encryption_status,
    initialize_local_vault_key,
    platform_credential_status,
    save_platform_credentials,
)
from platform_execution import build_order_preview
from platform_router import PLATFORM_PROFILES, build_platform_route_rows, build_platform_ticket
from schwab_preview import build_schwab_preview
from trade_brief import (
    CORE_STRATEGIES,
    build_symbol_trade_brief,
    latest_backtest_trades,
    strategy_family_from_setup,
    summarize_backtest_by_strategy,
)


PLATFORM_STATUS_LABELS = {
    "READY_TO_PREVIEW": "Listo para preparar",
    "WAIT_FOR_CONFIRMATION": "Esperar confirmacion",
    "NO_TRADE": "No operar",
    "BLOCKED_STALE_DATA": "Datos vencidos",
    "BLOCKED_MARKET_CLOSED": "Mercado cerrado",
    "RISK_GUARDRAIL": "Riesgo bloquea",
}

PLATFORM_REASON_LABELS = {
    "Roxy allows preview only after platform buying-power check.": "Roxy permite preparar el ticket, pero debes confirmar buying power y precio en la plataforma.",
    "Do not place this order. Wait until Roxy returns WATCH or BUY.": "No coloques esta orden. Espera que Roxy vuelva a WATCH o BUY.",
    "Prepare the ticket only; wait for 15m entry and 1h confirmation.": "Prepara el ticket solamente. Falta gatillo 15m y confirmacion 1h.",
    "Refresh live/confluence data before preparing any platform preview.": "Refresca datos live/confluencia antes de preparar una orden.",
    "Execution context is acceptable for preview-only preparation.": "Contexto aceptable para preparar ticket manual, sin envio automatico.",
}

ASSET_TYPE_LABELS = {
    "stock": "Accion",
    "option": "Opcion",
    "crypto": "Crypto",
}

ACTION_LABELS = {
    "ALERT": "Operar",
    "WATCH": "Esperar",
    "BUY": "Comprar",
    "AVOID": "Evitar",
}

OUTPUT_DIR = output_dir()
ALERTS_DIR = alerts_dir()


def runtime_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    parts = p.parts
    if parts and parts[0] == "output":
        return OUTPUT_DIR.joinpath(*parts[1:])
    if parts and parts[0] == "alerts":
        return ALERTS_DIR.joinpath(*parts[1:])
    return project_path(p)


CONNECTION_MODE_LABELS = {
    "NEEDS_CREDENTIALS": "Faltan credenciales",
    "PREVIEW_ONLY": "Solo preview",
    "LIVE_ARMED": "Live armado",
}

ADAPTER_STATUS_LABELS = {
    "IMPLEMENTED": "Implementado",
    "PREVIEW_ONLY": "Solo preview",
}

EXECUTION_BLOCKER_LABELS = {
    "Platform credentials are missing.": "Faltan credenciales de la plataforma.",
    "Quantity is zero or unavailable.": "La cantidad es cero o no esta disponible.",
    "Entry price is unavailable.": "El precio de entrada no esta disponible.",
    "No live broker adapter is implemented yet; Roxy prepares manual and preview payloads only.": "Todavia no hay adaptador live; Roxy solo prepara tickets manuales y previews.",
    "Roxy does not send live broker orders from this screen. This preview is for manual review and future adapter wiring.": "Roxy no envia ordenes reales desde esta pantalla. Este preview es para revision manual y futuro adaptador.",
    "This prepares the Schwab previewOrder request body only. Roxy does not call Schwab or place a live order from this screen.": "Esto prepara solamente el cuerpo previewOrder de Schwab. Roxy no llama a Schwab ni coloca orden real desde esta pantalla.",
}

NOTIFICATION_CHANNEL_LABELS = {
    "macos": "Mac local",
    "email": "Email",
    "discord": "Discord",
    "slack": "Slack",
    "webhook": "Webhook",
}

NOTIFICATION_NOTE_LABELS = {
    "Local desktop notification on this Mac.": "Notificacion local en esta Mac.",
    "Best for phone delivery if your email pushes notifications.": "Mejor opcion para telefono si tu email tiene push.",
    "Good phone alerts from a mobile app.": "Alertas al telefono desde una app movil.",
    "Team/mobile alerts.": "Alertas a equipo o telefono.",
    "Custom automation endpoint.": "Endpoint propio para automatizaciones.",
}

ROXY_LOGO_SVG = """
<svg class="roxy-logo-svg" viewBox="0 0 64 64" role="img" aria-label="Roxy logo">
  <rect x="6" y="6" width="52" height="52" rx="8" fill="#101827" stroke="#38bdf8" stroke-width="2"/>
  <path d="M17 43 L25 32 L33 36 L46 20" fill="none" stroke="#22c55e" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M17 47 H47" stroke="#f59e0b" stroke-width="3" stroke-linecap="round"/>
  <text x="17" y="28" font-size="18" font-weight="800" fill="#f8fafc" font-family="Arial, sans-serif">R</text>
</svg>
"""

BRAND_LOGO_PATH = project_path("assets/grau_service_logo.png")


def brand_logo_html() -> str:
    try:
        data = BRAND_LOGO_PATH.read_bytes()
    except OSError:
        return ROXY_LOGO_SVG.strip()
    encoded = base64.b64encode(data).decode("ascii")
    return f'<img class="brand-logo-img" src="data:image/png;base64,{encoded}" alt="Grau Service LLC logo"/>'

PLATFORM_BADGE_BRANDS = {
    "crypto_com": {
        "abbr": "CRO",
        "accent": "#1199fa",
        "asset": "Crypto 24h",
        "use": "oportunidades crypto",
    },
    "schwab": {
        "abbr": "CS",
        "accent": "#22c55e",
        "asset": "Acciones/opciones",
        "use": "tickets manuales",
    },
    "webull": {
        "abbr": "WB",
        "accent": "#a78bfa",
        "asset": "Acciones/crypto",
        "use": "confirmacion visual",
    },
}

TIMEFRAME_OPTIONS = ["15m", "1h", "2h", "4h", "1d"]
REALTIME_REFRESH_SECONDS = [30, 60, 120, 300]
DEFAULT_REALTIME_REFRESH_SECONDS = 60


def normalize_command_timeframe(value: Any, *, default: str = "1h") -> str:
    text = str(value or "").strip().lower()
    return text if text in TIMEFRAME_OPTIONS else default


def normalize_command_market(value: Any, symbol: Any = "") -> str:
    text = str(value or "").strip().lower()
    if text in {"stock", "crypto"}:
        return text
    return "crypto" if "/" in str(symbol or "") else "stock"


def first_query_param_value(params: Any, key: str) -> str:
    try:
        value = params.get(key)
    except Exception:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def sync_dashboard_query_params(
    params: Any,
    *,
    symbol: Any,
    market: Any,
    timeframe: Any,
    page: Any = "Dashboard",
) -> None:
    symbol_value = str(symbol or "AAPL").strip().upper() or "AAPL"
    desired = {
        "symbol": symbol_value,
        "market": normalize_command_market(market, symbol_value),
        "tf": normalize_command_timeframe(timeframe),
        "view": str(page or "Dashboard").strip() or "Dashboard",
    }
    for key, value in desired.items():
        try:
            if first_query_param_value(params, key) != value:
                params[key] = value
        except Exception:
            continue


def persist_command_query_params() -> None:
    symbol = str(st.session_state.get("command_symbol", "AAPL") or "AAPL").strip().upper()
    market = normalize_command_market(st.session_state.get("command_market"), symbol)
    timeframe = normalize_command_timeframe(st.session_state.get("command_timeframe", "1h"))
    st.session_state["command_symbol"] = symbol
    st.session_state["command_market"] = market
    st.session_state["command_timeframe"] = timeframe
    sync_dashboard_query_params(
        st.query_params,
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        page=st.session_state.get("roxy_focused_page", first_query_param_value(st.query_params, "view") or "Dashboard"),
    )


def persist_command_symbol_query_params() -> None:
    symbol = str(st.session_state.get("command_symbol", "AAPL") or "AAPL").strip().upper()
    st.session_state["command_symbol"] = symbol
    if "/" in symbol:
        st.session_state["command_market"] = "crypto"
    else:
        st.session_state["command_market"] = normalize_command_market(st.session_state.get("command_market"), symbol)
    persist_command_query_params()


def apply_pending_command_state() -> bool:
    changed = False
    pending_symbol = st.session_state.pop("command_symbol_pending", None)
    if pending_symbol:
        st.session_state["command_symbol"] = str(pending_symbol).strip().upper()
        changed = True
    pending_market = st.session_state.pop("command_market_pending", None)
    if pending_market:
        st.session_state["command_market"] = normalize_command_market(pending_market, st.session_state.get("command_symbol"))
        changed = True
    pending_timeframe = st.session_state.pop("command_timeframe_pending", None)
    if pending_timeframe:
        st.session_state["command_timeframe"] = normalize_command_timeframe(pending_timeframe)
        changed = True
    if changed:
        persist_command_query_params()
    return changed
AUTOHEAL_REPORT_KEYS = (
    "launchd_autoheal",
    "runtime_backup_autoheal",
    "runtime_backup_report_autoheal",
    "streamlit_app_autoheal",
    "chart_health_autoheal",
    "live_data_autoheal",
    "storage_migration_autoheal",
    "yfinance_cache_autoheal",
    "output_maintenance_autoheal",
    "ai_brief_autoheal",
    "alert_quality_autoheal",
)
LIVE_SOURCE_LABEL = "Live intradia"

STRATEGY_STUDY_GUIDES = {
    "Canal alcista": {
        "headline": "Usar la tendencia a favor, comprando continuaciones o retrocesos sanos.",
        "works_when": "Precio sobre SMA200, medias ordenadas 20 > 40 > 100 > 200 y 1h mantiene maximos crecientes.",
        "entry": "Entrada ideal cuando 15m vuelve a cerrar sobre SMA20/SMA40 con volumen relativo normal o fuerte.",
        "avoid": "Evitar si el precio queda extendido lejos de SMA20 o si el stop supera el riesgo permitido.",
        "option_note": "Calls solo si el spread es bajo, DTE suficiente y el target 2% paga el riesgo.",
        "practice": "Marca soporte de canal, espera pullback y compara entrada contra stop/objetivos 2%, 5% y 10%.",
    },
    "Canal lateral": {
        "headline": "Operar rango solo cuando el precio respeta soporte/resistencia y el riesgo es pequeno.",
        "works_when": "SMA100/SMA200 planas, precio dentro de rango y Bollinger/soporte muestran rebotes claros.",
        "entry": "Entrada cerca de soporte con cierre verde, o ruptura de resistencia con volumen confirmado.",
        "avoid": "Evitar el centro del rango, velas sin volumen o rompimientos falsos sin cierre.",
        "option_note": "Opciones requieren mas cuidado: preferir contratos liquidos y no perseguir ruptura tarde.",
        "practice": "Dibuja soporte, resistencia y punto medio; solo valida entradas en bordes del rango.",
    },
    "Pullback": {
        "headline": "Comprar retroceso dentro de una tendencia viva, no una caida sin control.",
        "works_when": "Tendencia 1h sigue arriba, precio toca SMA20/SMA40 y no pierde la estructura mayor.",
        "entry": "Entrada cuando aparece rebote en SMA20/SMA40, 15m da BUY y el volumen acompana.",
        "avoid": "Evitar si el pullback pierde SMA100/SMA200 o si el rebote no recupera SMA20.",
        "option_note": "Call watch si la entrada esta cerca del stop y el contrato cabe en el riesgo.",
        "practice": "Mide distancia entrada-stop antes de mirar ganancia; si 2% no compensa, esperar.",
    },
    "Rebote en media": {
        "headline": "Buscar reaccion limpia en una media clave despues de una pausa del precio.",
        "works_when": "La media actua como soporte repetido y el precio no cierra fuerte debajo de ella.",
        "entry": "Entrada sobre confirmacion de vela de rebote y recuperacion de SMA20 o SMA40.",
        "avoid": "Evitar si hay cierre bajo SMA200 o si el rebote ocurre con volumen debil.",
        "option_note": "Calls solo si la prima no destruye el target 2% y el break-even es razonable.",
        "practice": "Compara los ultimos tres toques de la media y revisa si cada rebote hizo maximo nuevo.",
    },
    "Cruce de medias": {
        "headline": "Detectar cambio temprano de tendencia cuando las medias cortas empiezan a girar.",
        "works_when": "SMA20 cruza sobre SMA40 y el precio sostiene sobre SMA100/SMA200.",
        "entry": "Primera entrada es watch; operar cuando el cruce se confirma con 1h y volumen.",
        "avoid": "Evitar cruces dentro de un rango estrecho porque suelen dar senales falsas.",
        "option_note": "En opciones, esperar confirmacion extra; los cruces tempranos pueden fallar rapido.",
        "practice": "Busca el cruce, luego revisa si el pullback posterior respeta SMA20/SMA40.",
    },
    "Tendencia bajista": {
        "headline": "Proteger capital. Roxy prioriza no operar o mirar puts solo con confirmacion.",
        "works_when": "Precio bajo SMA200, medias inclinadas hacia abajo y cada rebote falla en resistencia.",
        "entry": "Para puts, esperar rechazo en SMA20/SMA40 y 15m confirmando debilidad.",
        "avoid": "Evitar calls mientras no recupere SMA200 y no cambie la estructura.",
        "option_note": "Puts solo con liquidez, spread bajo y riesgo maximo definido.",
        "practice": "Marca SMA200, zona de rechazo y ultimo minimo; no anticipar reversa sin confirmacion.",
    },
}

for _salto_strategy in SALTO_STRATEGIES:
    STRATEGY_STUDY_GUIDES.setdefault(
        _salto_strategy.family,
        {
            "headline": _salto_strategy.headline,
            "works_when": _salto_strategy.works_when,
            "entry": _salto_strategy.entry,
            "avoid": _salto_strategy.avoid,
            "option_note": _salto_strategy.option_note,
            "practice": _salto_strategy.practice,
            "requirements": list(_salto_strategy.requirements),
            "requirements_text": " | ".join(_salto_strategy.requirements),
            "confirmation_timeframes": list(_salto_strategy.confirmation_timeframes),
            "direction": _salto_strategy.direction,
        },
    )


def latest_file(pattern: str) -> Optional[str]:
    files = glob(str(runtime_path(pattern)))
    if not files:
        return None
    # choose by modified time
    files.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return files[0]


def load_latest_tech_df(kind: str) -> pd.DataFrame:
    """Load the most recent tech CSV for `kind` in `output/`.

    kind should be 'crypto' or 'stocks'.
    """
    pattern = f"output/{kind}_tech_*.csv" if kind == "stocks" else f"output/{kind}_tech_*.csv"
    path = latest_file(pattern)
    if not path:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def get_ohlcv(symbol: str) -> pd.DataFrame:
    """Query the local `db/roxy.db` ohlcv table for `symbol`.

    Returns a DataFrame indexed by datetime with open/high/low/close/volume.
    """
    conn = sqlite3.connect(storage.DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ts, open, high, low, close, volume FROM ohlcv WHERE symbol = ? ORDER BY ts",
            (symbol,),
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])  # type: ignore
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    return df


def read_summary_json(path: str) -> dict:
    p = runtime_path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def heartbeat_artifact_path(key: str) -> str | None:
    heartbeat = read_summary_json("alerts/ma_live_heartbeat.json")
    value = heartbeat.get(key)
    if not value:
        return None
    path = Path(str(value))
    return str(path) if path.exists() else None


def load_learning_journal(path: str = "alerts/roxy_learning_journal.csv", limit: int = 50) -> pd.DataFrame:
    p = runtime_path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    return df.tail(limit).copy()


def read_latest_alert_text(path: str) -> str:
    p = runtime_path(path)
    if not p.exists():
        return ""
    return p.read_text()


def speak_in_browser(text: str, *, key: str, lang: str = "es-US") -> None:
    spoken = " ".join(str(text or "").split())[:1400]
    if not spoken:
        return
    payload = json.dumps(spoken)
    lang_payload = json.dumps(lang)
    component_id = json.dumps(f"roxy-voice-{key}")
    st.components.v1.html(
        f"""
        <div id={component_id}></div>
        <script>
        (() => {{
            const message = {payload};
            const lang = {lang_payload};
            const speak = () => {{
                const utterance = new SpeechSynthesisUtterance(message);
                utterance.lang = lang;
                utterance.rate = 0.95;
                utterance.pitch = 1.0;
                const voices = window.speechSynthesis.getVoices() || [];
                const preferred = voices.find(v => (v.lang || '').toLowerCase().startsWith('es'))
                    || voices.find(v => (v.lang || '').toLowerCase().startsWith('en'))
                    || voices[0];
                if (preferred) utterance.voice = preferred;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utterance);
            }};
            if ('speechSynthesis' in window) {{
                if (window.speechSynthesis.getVoices().length === 0) {{
                    window.speechSynthesis.onvoiceschanged = speak;
                    setTimeout(speak, 350);
                }} else {{
                    speak();
                }}
            }}
        }})();
        </script>
        """,
        height=0,
    )


def show_market_tab(kind: str) -> None:
    df = load_latest_tech_df(kind)
    if df.empty:
        st.info(f"No {kind} data available in `output/`.")
        return

    # normalize market column variations
    if "market" in df.columns:
        df = df.copy()
        # keep only relevant rows
    st.write(f"Latest {kind.capitalize()} scan — {len(df)} rows")

    # top picks in this market
    if "rank_score" in df.columns:
        top = df.sort_values("rank_score", ascending=False).head(10)
        st.subheader("Top recommendations")
        st.dataframe(
            top[
                [
                    c
                    for c in ["symbol", "tf", "signal", "score", "rank_score", "entry", "stop", "tp2"]
                    if c in top.columns
                ]
            ]
        )

    # pick a symbol to inspect
    symbols = sorted(df["symbol"].unique())
    choice = st.selectbox(f"Select {kind} symbol", symbols)
    row = df[df["symbol"] == choice].iloc[0]

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"{choice} — {row.get('signal', '')} | score {row.get('score', '')}")
        ohlcv = get_ohlcv(choice)
        if not ohlcv.empty:
            # build a candlestick chart with zoom/tooltip
            df_cs = ohlcv.reset_index().rename(columns={"ts": "time"})
            df_cs["time_str"] = df_cs["time"].dt.strftime("%Y-%m-%d %H:%M")

            base = alt.Chart(df_cs).encode(x=alt.X("time:T", title="Time"))

            rule = base.mark_rule().encode(
                y=alt.Y("low:Q", title="Price"),
                y2="high:Q",
                tooltip=[
                    alt.Tooltip("time_str:N", title="Time"),
                    alt.Tooltip("open:Q"),
                    alt.Tooltip("high:Q"),
                    alt.Tooltip("low:Q"),
                    alt.Tooltip("close:Q"),
                    alt.Tooltip("volume:Q"),
                ],
            )

            bar = base.mark_bar().encode(
                y=alt.Y("open:Q", title=""),
                y2="close:Q",
                color=alt.condition("datum.open <= datum.close", alt.value("green"), alt.value("red")),
                tooltip=[
                    alt.Tooltip("time_str:N", title="Time"),
                    alt.Tooltip("open:Q"),
                    alt.Tooltip("high:Q"),
                    alt.Tooltip("low:Q"),
                    alt.Tooltip("close:Q"),
                    alt.Tooltip("volume:Q"),
                ],
            )

            selection = alt.selection_interval(bind="scales")

            chart = (rule + bar).properties(height=360).add_selection(selection)

            # overlay horizontal lines for entry/stop/tp2
            overlays = []
            for fld, color, label in (("entry", "green", "Entry"), ("stop", "red", "Stop"), ("tp2", "blue", "TP2")):
                val = row.get(fld)
                if val is not None and pd.notna(val):
                    overlays.append(
                        alt.Chart(pd.DataFrame({"y": [float(val)], "label": [label]}))
                        .mark_rule(color=color, size=1)
                        .encode(y="y:Q")
                    )
                    overlays.append(
                        alt.Chart(pd.DataFrame({"y": [float(val)], "label": [label]}))
                        .mark_text(align="left", dx=5, dy=-5, color=color)
                        .encode(y="y:Q", text=alt.Text("label:N"))
                    )

            for o in overlays:
                chart = chart + o

            st.altair_chart(chart.interactive(), width="stretch")
        else:
            st.info("No historical OHLCV in local DB for this symbol — showing latest metrics.")
            st.metric("Entry", row.get("entry", "n/a"))
            st.metric("Stop", row.get("stop", "n/a"))
            st.metric("TP2", row.get("tp2", "n/a"))

    with col2:
        st.subheader("Trade setup")
        signal = str(row.get("signal", "")).upper()
        if signal == "BUY":
            st.success(f"Signal: {signal}")
        elif signal == "WATCH":
            st.info(f"Signal: {signal}")
        else:
            st.warning(f"Signal: {signal}")

        st.write(f"**Score:** {row.get('score', '')}  ")
        st.write(f"**Rank:** {row.get('rank_score', '')}  ")
        st.write(f"**RR (tp2):** {row.get('rr_tp2', '')}  ")
        st.markdown("---")
        st.subheader("Simulation")
        user = st.session_state.get("user", "anon")
        sizing_mode = st.selectbox("Sizing mode", options=["Units", "% Equity"], key=f"{kind}_sizing_mode")
        if sizing_mode == "% Equity":
            try:
                equity = storage.get_account_equity(user)
            except Exception:
                equity = 10000.0
            pct = st.slider("Percent of equity", 1, 100, 10, key=f"{kind}_equity_pct")
            price = float(row.get("entry") or (ohlcv["close"].iloc[-1] if not ohlcv.empty else 0.0))
            qty = (equity * (pct / 100.0)) / (price if price > 0 else 1.0)
        else:
            qty = st.number_input(
                "Position size (units)",
                min_value=0.0,
                value=1.0,
                step=0.1,
                key=f"{kind}_position_size_units",
            )
            price = float(row.get("entry") or (ohlcv["close"].iloc[-1] if not ohlcv.empty else 0.0))

        if st.button("Simulate BUY", key=f"{kind}_simulate_buy"):
            try:
                pid = storage.open_sim_position(user, choice, float(qty), float(price), note="simulated via UI")
                storage.save_simulated_trade(user, choice, "BUY", float(qty), float(price), note=f"open_pos:{pid}")
                # snapshot equity including unrealized after opening
                try:
                    storage.snapshot_account_point(user)
                except Exception:
                    pass
                st.success(f"Opened simulated position #{pid}")
            except Exception as e:
                st.error(f"Failed to open simulated position: {e}")

        if st.button("Simulate SELL (close)", key=f"{kind}_simulate_sell"):
            try:
                pnl = storage.close_sim_position_by_symbol(user, choice, float(qty), float(price))
                storage.save_simulated_trade(user, choice, "SELL", float(qty), float(price), note=f"close_qty={qty}")
                # snapshot equity after realized P&L applied
                try:
                    storage.snapshot_account_point(user)
                except Exception:
                    pass
                st.success(f"Closed positions for {qty} units, realized P&L {pnl:.2f}")
            except Exception as e:
                st.error(f"Failed to close simulated position: {e}")

        st.subheader("Open simulated positions")
        open_pos = storage.get_open_positions(user)
        if open_pos:
            rows = []
            last_price = float(ohlcv["close"].iloc[-1]) if not ohlcv.empty else price
            for pid, ts_open, usr, sym, pqty, entry_price, note in open_pos:
                unreal = (last_price - float(entry_price)) * float(pqty)
                rows.append(
                    {
                        "id": pid,
                        "ts_open": ts_open,
                        "symbol": sym,
                        "qty": pqty,
                        "entry": entry_price,
                        "last": last_price,
                        "unreal_pnl": unreal,
                        "note": note,
                    }
                )
            df_open = pd.DataFrame(rows)
            st.table(df_open)
        else:
            st.write("No open simulated positions.")

        # show equity curve for signed-in user
        if user:
            pts = storage.get_equity_series(user)
            if pts:
                df_eq = pd.DataFrame(pts, columns=["ts", "equity"])  # type: ignore
                df_eq["ts"] = pd.to_datetime(df_eq["ts"])
                eq_chart = (
                    alt.Chart(df_eq)
                    .mark_line(color="#2b8cbe")
                    .encode(x=alt.X("ts:T", title="Time"), y=alt.Y("equity:Q", title="Equity"))
                )
                st.subheader("Equity Curve")
                st.altair_chart(eq_chart.properties(height=200), width="stretch")
            else:
                st.write("No equity history for this user yet.")

        st.subheader("Recent simulated trades (audit)")
        rows = storage.get_simulated_trades(limit=20)
        if rows:
            df_tr = pd.DataFrame(rows, columns=["id", "ts", "user", "symbol", "side", "qty", "price", "note"])  # type: ignore
            st.table(df_tr)
        else:
            st.write("No simulated trades yet.")

        # Grok suggestion
        from grok_integration import generate_suggestion

        if st.button("Generate Grok suggestion", key=f"{kind}_grok_suggestion"):
            ctx = {"score": row.get("score"), "signal": row.get("signal")}
            sugg = generate_suggestion(choice, ctx)
            st.info(sugg.get("text"))
            st.write("Confidence:", f"{sugg.get('confidence'):.2f}")


def show_news_tab() -> None:
    st.subheader("Latest Alert")
    last = read_latest_alert_text("alerts/latest_alert.txt")
    if last:
        st.info(last)
    else:
        st.write("No latest alert file found.")

    st.subheader("Latest Summary JSON")
    summary = read_summary_json("alerts/latest_summary.json")
    if summary:
        st.json(summary)
    else:
        st.write("No latest summary JSON found.")

    st.subheader("News & Suggestions")
    # simple suggestions: echo top picks with a short suggestion sentence
    top_picks = read_summary_json("alerts/latest_summary.json").get("top_picks", [])
    suggestions = []
    for p in top_picks[:10]:
        symbol = p.get("symbol")
        signal = p.get("signal")
        if symbol and signal:
            suggestions.append(
                f"{symbol}: Current suggestion — {signal}. Consider watching entry {p.get('entry')} and stop {p.get('stop')}"
            )

    if suggestions:
        for s in suggestions:
            st.write("- ", s)
    else:
        st.write("No suggestions available.")

    # RSS / news fetcher
    st.markdown("---")
    # Dashboard Overview panel (quick metrics & aggregate equity chart)
    with st.expander("Overview", expanded=True):
        try:
            acct_rows = storage.list_accounts()
            total_accounts = len(acct_rows)
        except Exception:
            total_accounts = 0

        open_pos_count = 0
        try:
            for a in storage.list_accounts():
                open_pos = storage.get_open_positions(a[0])
                if open_pos:
                    open_pos_count += len(open_pos)
        except Exception:
            open_pos_count = open_pos_count

        total_trades = 0
        try:
            rows = storage.get_simulated_trades(limit=1000000)
            total_trades = len(rows) if rows else 0
        except Exception:
            total_trades = total_trades

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Accounts", total_accounts)
        with c2:
            st.metric("Open positions", open_pos_count)
        with c3:
            st.metric("Simulated trades", total_trades)

        # aggregated equity chart across snapshot points
        try:
            pts = storage.get_snapshot_points(limit=2000)
            if pts:
                df_eq = pd.DataFrame(pts, columns=["user", "ts", "equity"])  # type: ignore
                df_eq["ts"] = pd.to_datetime(df_eq["ts"])
                df_agg = df_eq.groupby("ts")["equity"].sum().reset_index()
                chart = (
                    alt.Chart(df_agg)
                    .mark_line(color="#2b8cbe")
                    .encode(x=alt.X("ts:T", title="Time"), y=alt.Y("equity:Q", title="Total Equity"))
                )
                st.altair_chart(chart.properties(height=200), width="stretch")
        except Exception:
            pass

        # Top Picks summary and simple chart (reads TOP_PICKS_FILE if present)
        try:
            tp = Path(TOP_PICKS_FILE)
            if tp.exists():
                txt = tp.read_text()
                import json as _json
                from io import StringIO as _StringIO

                df_p = pd.DataFrame()
                try:
                    parsed = _json.loads(txt)
                    if isinstance(parsed, list):
                        df_p = pd.DataFrame(parsed)
                except Exception:
                    try:
                        df_p = pd.read_csv(_StringIO(txt))
                    except Exception:
                        df_p = pd.DataFrame()

                if not df_p.empty:
                    st.subheader("Top Picks")
                    # prefer columns symbol and score if present
                    show_cols = [c for c in ("symbol", "score") if c in df_p.columns]
                    st.table(df_p.head(10)[show_cols] if show_cols else df_p.head(10))
                    if "score" in df_p.columns and "symbol" in df_p.columns:
                        ch = (
                            alt.Chart(df_p.head(10))
                            .mark_bar()
                            .encode(
                                x=alt.X("symbol:N", sort='-y', title="Symbol"),
                                y=alt.Y("score:Q", title="Score"),
                                color=alt.value("#2b8cbe"),
                            )
                        )
                        st.altair_chart(ch, width="stretch")
        except Exception:
            pass

        # Voice assistant prototype (client-side speech + server-side reply)
        with st.expander("Voice Assistant (prototype)"):
            st.write(
                "Try speaking or typing a question. This is a local prototype: replies are generated from simple rules."
            )
            va_user = st.session_state.get("user")
            query = st.text_input("Ask the assistant", key="va_query")
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("Ask Assistant"):
                    try:
                        from tools import voice_assistant as va

                        reply = va.generate_reply(query or "", user=va_user)
                        st.info(reply)
                        # speak the reply via client-side TTS using a tiny component
                        import json as _json

                        js = f"<script>const msg={_json.dumps(reply)}; const u=new SpeechSynthesisUtterance(msg); window.speechSynthesis.cancel(); window.speechSynthesis.speak(u);</script>"
                        st.components.v1.html(js, height=0)
                    except Exception as e:
                        st.error(f"Assistant error: {e}")
            with col2:
                # small client-side speech capture UI (Web Speech API) — transcribes locally in the browser
                st.components.v1.html(
                    """
                                <div>
                                    <button id="start">Start voice capture</button>
                                    <button id="stop">Stop</button>
                                    <div id="out" style="margin-top:8px;color:#222;">Transcript will appear here.</div>
                                    <script>
                                        let recognition=null;
                                        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                                            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
                                            recognition = new SR();
                                            recognition.lang = 'en-US';
                                            recognition.interimResults = false;
                                            recognition.onresult = (e) => { document.getElementById('out').innerText = e.results[0][0].transcript; };
                                            recognition.onerror = (e) => { document.getElementById('out').innerText = 'Error: '+e.error; };
                                        } else {
                                            document.getElementById('out').innerText = 'Speech recognition not available in this browser.';
                                        }
                                        document.getElementById('start').onclick = () => { if(recognition) recognition.start(); };
                                        document.getElementById('stop').onclick = () => { if(recognition) recognition.stop(); };
                                    </script>
                                </div>
                                """,
                    height=140,
                )
    st.subheader("External News Feeds")
    try:
        from news import fetch_news, save_highlights
    except Exception as e:
        fetch_news = None
        save_highlights = None
        st.error(f"News module unavailable: {e}")

    with st.expander("Fetch latest headlines"):
        max_items = st.slider("Headlines", 5, 50, 10)
        if fetch_news is None:
            headlines = []
        else:
            try:
                headlines = fetch_news(max_items=max_items)
            except Exception as e:
                st.error(f"Failed to fetch news: {e}")
                headlines = []

        if not headlines:
            st.write("No items fetched.")
        else:
            sources = sorted({h.get("source", "") for h in headlines})
            sel = st.multiselect("Sources", options=sources, default=sources)
            sent_threshold = st.slider("Minimum sentiment", -1.0, 1.0, 0.0, 0.1)

            filtered = [h for h in headlines if h.get("source") in sel and h.get("sentiment", 0) >= sent_threshold]

            st.write(f"Showing {len(filtered)} / {len(headlines)} items")

            to_save = []
            for h in filtered:
                s = h.get("sentiment", 0.0)
                if s > 0.2:
                    sentiment_mark = f"🟢 {s:.2f}"
                elif s < -0.2:
                    sentiment_mark = f"🔴 {s:.2f}"
                else:
                    sentiment_mark = f"🟡 {s:.2f}"

                st.markdown(f"**[{h['source']}]** {sentiment_mark} [{h['title']}]({h['link']})")
                st.write(h.get("summary", "")[:500])
                if st.button(f"Save highlight: {h.get('title')[:60]}", key=h.get("link")):
                    to_save.append(h)
                    st.success("Saved")
                st.write("---")

            if st.button("Save all visible highlights") and filtered:
                try:
                    if save_highlights is None:
                        st.error("News highlight saver is unavailable.")
                    else:
                        save_highlights(filtered)
                        st.success(f"Saved {len(filtered)} items to alerts/news_highlights.json")
                except Exception as e:
                    st.error(f"Failed to save highlights: {e}")

    # Saved highlights review
    st.markdown("---")
    st.subheader("Saved Highlights")
    highlights_path = Path("alerts/news_highlights.json")
    if highlights_path.exists():
        try:
            saved = json.loads(highlights_path.read_text())
        except Exception:
            saved = []
    else:
        saved = []

    if not saved:
        st.write("No saved highlights yet.")
    else:
        for i, h in enumerate(list(saved)):
            st.markdown(
                f"**{h.get('source','')}** [{h.get('title','')}]({h.get('link','')}) — sentiment {h.get('sentiment',0):+.2f}"
            )
            if st.button(f"Remove", key=f"rm_{i}"):
                try:
                    saved.pop(i)
                    highlights_path.write_text(json.dumps(saved, indent=2))
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Failed to remove: {e}")
            st.write(h.get("summary", "")[:400])
            st.write("---")

        if st.button("Export saved highlights to CSV"):
            df = pd.DataFrame(saved)
            outp = runtime_path("output/news_highlights.csv")
            outp.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(outp, index=False)
            st.success(f"Wrote {outp}")


def load_latest_ma_scan(prefix: str = "ma_strategy") -> tuple[Optional[str], pd.DataFrame]:
    path = heartbeat_artifact_path("scan_path") if prefix == "ma_live_strategy" else None
    path = path or latest_file(f"output/{prefix}_*.csv")
    if not path:
        return None, pd.DataFrame()
    try:
        return path, pd.read_csv(path)
    except Exception:
        return path, pd.DataFrame()


def load_latest_ma_confluence() -> tuple[Optional[str], pd.DataFrame]:
    path = heartbeat_artifact_path("confluence_path") or latest_file("output/ma_confluence_*.csv")
    if not path:
        return None, pd.DataFrame()
    try:
        return path, pd.read_csv(path)
    except Exception:
        return path, pd.DataFrame()


def load_latest_options_candidates() -> tuple[Optional[str], pd.DataFrame]:
    path = heartbeat_artifact_path("options_path") or latest_file("output/options_candidates_*.csv")
    if not path:
        return None, pd.DataFrame()
    try:
        return path, pd.read_csv(path)
    except Exception:
        return path, pd.DataFrame()


def pct_display(value) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "-"


def num_display(value, digits: int = 2) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "-"


def price_display(value) -> str:
    number = safe_float(value)
    if number is None:
        return "-"
    abs_number = abs(number)
    if abs_number >= 100:
        digits = 2
    elif abs_number >= 1:
        digits = 4
    elif abs_number >= 0.01:
        digits = 5
    elif abs_number >= 0.0001:
        digits = 6
    else:
        digits = 8
    return num_display(number, digits)


def compact_large_number(value) -> str:
    number = safe_float(value)
    if number is None:
        return "-"
    abs_number = abs(number)
    for suffix, divisor in (("T", 1_000_000_000_000), ("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if abs_number >= divisor:
            return f"{number / divisor:.2f}{suffix}"
    return f"{number:.0f}"


def company_profile_summary(profile: dict[str, Any]) -> dict[str, str]:
    current_price = safe_float(profile.get("currentPrice") or profile.get("regularMarketPrice"))
    target_price = safe_float(profile.get("targetMeanPrice"))
    target_upside = ((target_price / current_price) - 1.0) if current_price and target_price else None
    return {
        "name": text_display(profile.get("longName") or profile.get("shortName")),
        "sector": text_display(profile.get("sector")),
        "industry": text_display(profile.get("industry")),
        "country": text_display(profile.get("country")),
        "exchange": text_display(profile.get("exchange") or profile.get("fullExchangeName")),
        "market_cap": compact_large_number(profile.get("marketCap")),
        "employees": compact_large_number(profile.get("fullTimeEmployees")),
        "price": num_display(current_price, 2),
        "pe": num_display(profile.get("trailingPE"), 2),
        "forward_pe": num_display(profile.get("forwardPE"), 2),
        "beta": num_display(profile.get("beta"), 2),
        "dividend_yield": pct_display(profile.get("dividendYield")),
        "recommendation": text_display(profile.get("recommendationKey")).title(),
        "target_price": num_display(target_price, 2),
        "target_upside": pct_display(target_upside),
        "range_52w": f"{num_display(profile.get('fiftyTwoWeekLow'), 2)} / {num_display(profile.get('fiftyTwoWeekHigh'), 2)}",
        "website": text_display(profile.get("website")),
        "summary": text_display(profile.get("longBusinessSummary")),
    }


def text_display(value) -> str:
    try:
        if pd.isna(value):
            return "-"
    except Exception:
        pass
    value = str(value).strip()
    return value if value else "-"


def strategy_family_for_row(row: dict[str, Any]) -> str:
    explicit = row.get("strategy_family") or row.get("salto_family")
    if text_display(explicit) != "-":
        return strategy_family_from_setup(explicit)
    setup = row.get("trigger_setup") or row.get("setup") or row.get("raw_signal")
    trend = row.get("trend_setup") or row.get("trend")
    return strategy_family_from_setup(setup, trend_setup=trend)


def dashboard_strategy_label(row: dict[str, Any]) -> str:
    explicit = text_display(row.get("strategy_family") or row.get("salto_family"))
    if explicit != "-":
        return explicit
    return strategy_family_for_row(row)


def safe_key(value: Any) -> str:
    text = str(value or "item").strip().lower()
    cleaned = [ch if ch.isalnum() else "_" for ch in text]
    return "_".join(part for part in "".join(cleaned).split("_") if part) or "item"


def resolve_study_strategy_choice(
    strategy_names: list[str],
    preferred: str,
    *,
    requested: str | None = None,
    current: str | None = None,
) -> str:
    if requested in strategy_names:
        return str(requested)
    if current in strategy_names:
        return str(current)
    if preferred in strategy_names:
        return preferred
    return strategy_names[0] if strategy_names else "-"


def chart_strategy_summary(
    setup: dict,
    confluence: dict | None,
    brief: dict | None,
    chart_df: pd.DataFrame,
) -> dict[str, str]:
    confluence = confluence or {}
    brief = brief or {}
    setup_name = text_display(setup.get("setup") or confluence.get("trigger_setup"))
    family = strategy_family_from_setup(setup_name, trend_setup=confluence.get("trend_setup"))
    action = human_trade_action(brief) if brief else action_label(confluence.get("signal"))
    tone = "buy" if action in {"Operar", "Comprar"} else "avoid" if action in {"No operar", "Evitar"} else "watch"
    latest = chart_df.iloc[-1].to_dict() if not chart_df.empty else {}
    sma20 = safe_float(latest.get("sma20") or setup.get("sma20"))
    sma40 = safe_float(latest.get("sma40") or setup.get("sma40"))
    sma200 = safe_float(latest.get("sma200") or setup.get("sma200"))
    risk = safe_float(brief.get("risk_pct") or confluence.get("risk_pct")) or setup_risk_pct(setup)
    target = safe_float(brief.get("recommended_target_pct") or confluence.get("recommended_target_pct"))

    watch_plan = brief.get("watch_plan") if isinstance(brief, dict) else {}
    movement = text_display((watch_plan or {}).get("movement"))
    if movement == "-":
        if family == "Pullback":
            movement = f"Esperar rebote en SMA20/SMA40 ({num_display(sma20)} - {num_display(sma40)}) con vela verde."
        elif family == "Cruce de medias":
            movement = "Esperar que SMA20 cruce y sostenga sobre SMA40 con confirmacion 1h."
        elif family == "Canal alcista":
            movement = "Esperar continuacion sobre SMA20 sin perder estructura 20/40/100/200."
        elif family == "Canal lateral":
            movement = "Esperar rebote en soporte o ruptura de resistencia con volumen."
        elif family == "Tendencia bajista":
            movement = f"No buscar calls hasta recuperar SMA200 {num_display(sma200)}."
        else:
            movement = "Esperar 15m en BUY, 1h confirmando, volumen y riesgo medible."

    if action in {"Operar", "Comprar"}:
        decision_note = "Setup listo si respeta entrada, stop y volumen."
    elif action in {"No operar", "Evitar"}:
        decision_note = "No entrar hasta que cambie la estructura."
    else:
        decision_note = "Vigilar sin ejecutar; falta una confirmacion."

    return {
        "family": family,
        "setup": setup_name,
        "action": action,
        "tone": tone,
        "movement": movement,
        "decision_note": decision_note,
        "risk": pct_display(risk),
        "target": pct_display(target),
    }


def render_chart_strategy_summary(
    setup: dict,
    confluence: dict | None,
    brief: dict | None,
    chart_df: pd.DataFrame,
) -> None:
    summary = chart_strategy_summary(setup, confluence, brief, chart_df)
    tone = summary["tone"] if summary["tone"] in {"buy", "watch", "avoid"} else "neutral"
    st.markdown(
        f"""
        <div class="chart-context chart-context-{tone}">
            <div>
                <div class="chart-context-kicker">Lectura de estrategia</div>
                <div class="chart-context-title">{html.escape(summary["family"])} · {html.escape(summary["action"])}</div>
                <div class="chart-context-text">{html.escape(summary["movement"])}</div>
            </div>
            <div class="chart-context-grid">
                <span>Setup <strong>{html.escape(summary["setup"])}</strong></span>
                <span>Riesgo <strong>{html.escape(summary["risk"])}</strong></span>
                <span>Target <strong>{html.escape(summary["target"])}</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def command_center_target_prices(row: dict[str, Any]) -> dict[str, float | None]:
    entry = safe_float(row.get("entry"))
    targets = {
        "target_2": safe_float(row.get("target_2pct_price") or row.get("target_2")),
        "target_5": safe_float(row.get("target_5pct_price") or row.get("target_5")),
        "target_10": safe_float(row.get("target_10pct_price") or row.get("target_10")),
    }
    ladder = row.get("target_ladder") or []
    for item in ladder if isinstance(ladder, list) else []:
        label = str(item.get("target") or "")
        price = safe_float(item.get("target_price"))
        if price is None:
            continue
        if label == "2%":
            targets["target_2"] = price
        elif label == "5%":
            targets["target_5"] = price
        elif label == "10%":
            targets["target_10"] = price
    if entry is not None:
        targets["target_2"] = targets["target_2"] if targets["target_2"] is not None else entry * 1.02
        targets["target_5"] = targets["target_5"] if targets["target_5"] is not None else entry * 1.05
        targets["target_10"] = targets["target_10"] if targets["target_10"] is not None else entry * 1.10
    return targets


def command_center_checklist_rows(row: dict[str, Any]) -> list[dict[str, str]]:
    checks = row.get("condition_checks")
    rows: list[dict[str, str]] = []

    def add(label: str, passed: bool | None, detail: Any = "-") -> None:
        if passed is True:
            status = "OK"
            tone = "buy"
        elif passed is False:
            status = "Falta"
            tone = "avoid"
        else:
            status = "Pendiente"
            tone = "watch"
        rows.append(
            {
                "label": label,
                "status": status,
                "tone": tone,
                "detail": text_display(detail),
            }
        )

    if isinstance(checks, list) and checks:
        for item in checks[:7]:
            passed_value = item.get("passed")
            add(
                str(item.get("label") or "Condicion"),
                passed_value if isinstance(passed_value, bool) else None,
                item.get("detail"),
            )
        return rows

    signal = str(row.get("signal") or "").upper()
    decision = str(row.get("decision") or row.get("trade_decision") or "").upper()
    trade_ready = opportunity_is_trade_ready(row)
    risk = safe_float(row.get("risk_pct"))
    target = safe_float(row.get("recommended_target_pct") or row.get("target_pct"))
    relative_volume = safe_float(row.get("relative_volume") or row.get("relative_volume_15m"))
    backtest = row.get("backtest_eligible")

    add("1h confirma", True if trade_ready else None, row.get("trend") or row.get("trend_setup") or "Esperando 1h")
    add("15m da entrada", trade_ready if signal else None, decision or signal or "Sin gatillo")
    add(
        "Volumen acompana",
        None if relative_volume is None else relative_volume >= 0.8,
        f"{relative_volume:.2f}x" if relative_volume is not None else "No disponible",
    )
    add("Riesgo bajo", None if risk is None else risk <= 0.035, pct_display(risk))
    add("Target 2% viable", None if target is None else target >= 0.02, pct_display(target))
    if backtest is not None:
        add("Filtro historico", bool(backtest), "Backtest elegible" if bool(backtest) else "No validado")
    return rows


def build_command_center_summary(row: dict[str, Any]) -> dict[str, Any]:
    action = str(row.get("action") or row.get("ai_action") or "").upper()
    signal = str(row.get("signal") or "").upper()
    decision_raw = str(row.get("decision") or row.get("trade_decision") or "").upper()
    if action in {"BUY_STOCK", "WATCH_CALL"} or opportunity_is_trade_ready(row):
        status = "Operar"
        tone = "buy"
    elif action == "NO_TRADE" or signal == "AVOID" or decision_raw.startswith("NO_TRADE"):
        status = "No operar"
        tone = "avoid"
    else:
        status = "Esperar"
        tone = "watch"

    decision = text_display(row.get("decision"))
    if decision == "-":
        decision = human_trade_action(row)
    strategy = text_display(row.get("strategy_family"))
    if strategy == "-":
        strategy = strategy_family_for_row(row)
    reason = text_display((row.get("decision_reason") or {}).get("summary") if isinstance(row.get("decision_reason"), dict) else None)
    if reason == "-":
        reason = human_alert_reason(row) or opportunity_reason_label(row)
    movement = text_display((row.get("watch_plan") or {}).get("movement") if isinstance(row.get("watch_plan"), dict) else None)
    if movement == "-":
        movement = watch_movement_label(row)
    memory = row.get("memory") or {}
    memory_note = text_display(memory.get("note") if isinstance(memory, dict) else None)
    targets = command_center_target_prices(row)
    return {
        "symbol": text_display(row.get("symbol")).upper(),
        "market": text_display(row.get("market")),
        "timeframe": text_display(row.get("timeframe")),
        "status": status,
        "tone": tone,
        "decision": decision,
        "strategy": strategy,
        "reason": reason,
        "movement": movement,
        "entry": safe_float(row.get("entry")),
        "stop": safe_float(row.get("stop")),
        "risk": safe_float(row.get("risk_pct")),
        "score": safe_float(row.get("score") or row.get("ai_score")),
        "readiness": safe_float(row.get("readiness") or row.get("alert_readiness_score")),
        "target_2": targets["target_2"],
        "target_5": targets["target_5"],
        "target_10": targets["target_10"],
        "memory_note": memory_note,
    }


def render_command_center_panel(row: dict[str, Any], *, platform_ticket: dict | None = None) -> None:
    summary = build_command_center_summary(row)
    tone = summary["tone"] if summary["tone"] in {"buy", "watch", "avoid"} else "watch"
    platform_name_text = text_display((platform_ticket or {}).get("platform"))
    platform_status_text = platform_status_label((platform_ticket or {}).get("status")) if platform_ticket else "-"
    platform_qty = num_display((platform_ticket or {}).get("quantity"), 4) if platform_ticket else "-"
    st.markdown(
        f"""
        <section class="command-center command-center-{html.escape(tone)}">
            <div class="command-main">
                <div class="command-kicker">Oportunidad real</div>
                <h2>{html.escape(summary["symbol"])} · {html.escape(summary["status"])}</h2>
                <p>{html.escape(summary["reason"])}</p>
            </div>
            <div class="command-side">
                <span>Accion Roxy</span>
                <strong>{html.escape(summary["decision"])}</strong>
                <small>{html.escape(summary["strategy"])} · {html.escape(summary["timeframe"])}</small>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    kpis = st.columns([0.85, 0.85, 1.15, 1.15, 0.9, 1.15])
    with kpis[0]:
        render_kpi_card("Entrada", num_display(summary["entry"]), tone="buy" if tone == "buy" else "neutral")
    with kpis[1]:
        render_kpi_card("Stop", num_display(summary["stop"]), tone="avoid")
    with kpis[2]:
        render_kpi_card("Targets", f"{num_display(summary['target_2'])} / {num_display(summary['target_5'])} / {num_display(summary['target_10'])}")
    with kpis[3]:
        render_kpi_card("Esperamos", summary["movement"], tone="watch")
    with kpis[4]:
        render_kpi_card("Riesgo", pct_display(summary["risk"]), tone="buy" if summary["risk"] and summary["risk"] <= 0.035 else "watch")
    with kpis[5]:
        render_kpi_card("Plataforma", platform_name_text, detail=f"{platform_status_text} | Qty {platform_qty}", tone="watch")

    checklist = command_center_checklist_rows(row)
    if checklist:
        cards = []
        for item in checklist:
            cards.append(
                f'<div class="command-check command-check-{html.escape(item["tone"])}">'
                f'<span>{html.escape(item["label"])}</span>'
                f'<strong>{html.escape(item["status"])}</strong>'
                f'<small>{html.escape(item["detail"])}</small>'
                "</div>"
            )
        st.markdown(
            '<div class="command-checklist">' + "".join(cards) + "</div>",
            unsafe_allow_html=True,
        )
    if summary["memory_note"] != "-":
        st.caption("Memoria Roxy: " + summary["memory_note"])


def load_symbol_trade_context(
    *,
    symbol: str,
    market: str,
    timeframe: str,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    account_equity: float,
    risk_per_trade_pct: float,
    memory: dict | None = None,
) -> dict[str, Any]:
    resolved_symbol = resolve_symbol_query(symbol, market)
    history = fetch_symbol_history(resolved_symbol, market=market, timeframe=timeframe)
    chart_df = prepare_symbol_chart_data(history)
    setup = analyze_moving_average_setup(history) if not history.empty else {}
    if chart_df.empty or not setup:
        return {"symbol": resolved_symbol, "chart_df": chart_df, "setup": setup, "trade_brief": {}}
    confluence = latest_confluence_row(confluence_df, resolved_symbol)
    trade_brief = build_symbol_trade_brief(
        symbol=resolved_symbol,
        market=market,
        timeframe=timeframe,
        setup=setup,
        confluence=confluence,
        options_df=options_df,
        account_equity=float(account_equity),
        account_risk_pct=float(risk_per_trade_pct),
        memory=memory or load_memory(),
    )
    return {
        "symbol": resolved_symbol,
        "market": market,
        "timeframe": timeframe,
        "history": history,
        "chart_df": chart_df,
        "setup": setup,
        "confluence": confluence,
        "trade_brief": trade_brief,
    }


@st.cache_data(ttl=21_600, show_spinner=False)
def load_company_profile(symbol: str, market: str) -> dict[str, Any]:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol or "/" in clean_symbol or str(market or "").lower() != "stock" or yf is None:
        return {}
    try:
        ticker = yf.Ticker(clean_symbol)
        info = getattr(ticker, "info", None) or {}
    except Exception:
        return {}
    if not isinstance(info, dict):
        return {}
    return {
        key: info.get(key)
        for key in [
            "longName",
            "shortName",
            "sector",
            "industry",
            "country",
            "exchange",
            "fullExchangeName",
            "marketCap",
            "fullTimeEmployees",
            "currentPrice",
            "regularMarketPrice",
            "trailingPE",
            "forwardPE",
            "beta",
            "dividendYield",
            "recommendationKey",
            "targetMeanPrice",
            "fiftyTwoWeekLow",
            "fiftyTwoWeekHigh",
            "website",
            "longBusinessSummary",
        ]
    }


def render_company_profile_card(symbol: str, market: str) -> None:
    profile = load_company_profile(symbol, market)
    if not profile:
        st.caption("Perfil de compania no disponible para este simbolo o mercado.")
        return
    summary = company_profile_summary(profile)
    st.markdown("**Compañía**")
    st.markdown(
        f"""
        <section class="company-profile-card">
            <header>
                <strong>{html.escape(summary['name'])}</strong>
                <span>{html.escape(symbol.upper())} · {html.escape(summary['exchange'])} · {html.escape(summary['sector'])}</span>
            </header>
            <div class="company-profile-grid">
                <div><span>Industria</span><strong>{html.escape(summary['industry'])}</strong></div>
                <div><span>Market cap</span><strong>{html.escape(summary['market_cap'])}</strong></div>
                <div><span>Precio</span><strong>{html.escape(summary['price'])}</strong></div>
                <div><span>P/E</span><strong>{html.escape(summary['pe'])}</strong></div>
                <div><span>Forward P/E</span><strong>{html.escape(summary['forward_pe'])}</strong></div>
                <div><span>Beta</span><strong>{html.escape(summary['beta'])}</strong></div>
                <div><span>Div yield</span><strong>{html.escape(summary['dividend_yield'])}</strong></div>
                <div><span>Empleados</span><strong>{html.escape(summary['employees'])}</strong></div>
                <div><span>Analistas</span><strong>{html.escape(summary['recommendation'])}</strong></div>
                <div><span>Target/upside</span><strong>{html.escape(summary['target_price'])} · {html.escape(summary['target_upside'])}</strong></div>
                <div><span>52W</span><strong>{html.escape(summary['range_52w'])}</strong></div>
                <div><span>País</span><strong>{html.escape(summary['country'])}</strong></div>
            </div>
            <p>{html.escape(summary['summary'][:420])}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if summary["website"] != "-":
        st.link_button("Web compañía", summary["website"], use_container_width=True)


def render_professional_chart_block(
    chart_df: pd.DataFrame,
    setup: dict,
    confluence: dict | None,
    trade_brief: dict | None,
    *,
    price_height: int = 500,
    volume_height: int = 130,
    oscillator_height: int = 120,
) -> None:
    chart_symbol = text_display((trade_brief or {}).get("symbol") or setup.get("symbol"))
    timeframe = text_display((trade_brief or {}).get("timeframe") or setup.get("timeframe") or setup.get("tf"))
    clean_window = prepare_chart_window(chart_df)
    if clean_window.empty:
        st.markdown(
            f"""
            <section class="chart-empty-state">
              <div>
                <span>Gráfica pendiente</span>
                <strong>{html.escape(chart_symbol)} · {html.escape(timeframe)}</strong>
                <p>Roxy no encontró velas limpias suficientes para dibujar precio, volumen e indicadores.</p>
              </div>
              <ul>
                <li>Cambiar timeframe o símbolo.</li>
                <li>Verificar proveedor live.</li>
                <li>Esperar nueva lectura del scanner.</li>
              </ul>
            </section>
            """,
            unsafe_allow_html=True,
        )
        return
    if len(clean_window) < 40:
        st.info("Grafica limitada: hay pocas velas limpias para este simbolo/timeframe. Roxy muestra niveles, pero exige confirmacion extra.")
    visible_candles = len(clean_window)
    latest_candle = "-"
    if "ts" in clean_window.columns:
        try:
            ts_values = pd.to_datetime(clean_window["ts"], errors="coerce").dropna()
            if not ts_values.empty:
                latest_candle = pd.Timestamp(ts_values.max()).strftime("%m/%d %H:%M")
        except Exception:
            latest_candle = "-"
    latest_row = clean_window.iloc[-1]
    latest_open = safe_float(latest_row.get("open"))
    latest_high = safe_float(latest_row.get("high"))
    latest_low = safe_float(latest_row.get("low"))
    latest_close = safe_float(latest_row.get("close"))
    latest_volume = safe_float(latest_row.get("volume"))
    previous_close = safe_float(clean_window.iloc[-2].get("close")) if len(clean_window) > 1 else None
    candle_change = None
    if latest_close is not None and previous_close not in (None, 0):
        candle_change = (latest_close - previous_close) / previous_close
    candle_range = None
    if latest_high is not None and latest_low is not None and latest_close not in (None, 0):
        candle_range = (latest_high - latest_low) / latest_close
    candle_tone = "buy" if (latest_close or 0) >= (latest_open or latest_close or 0) else "avoid"
    candle_label = "Vela verde" if candle_tone == "buy" else "Vela roja"
    candle_ohlc = (
        f"O {num_display(latest_open, 2)} · H {num_display(latest_high, 2)} · "
        f"L {num_display(latest_low, 2)} · C {num_display(latest_close, 2)}"
    )
    candle_change_text = pct_display(candle_change) if candle_change is not None else "-"
    candle_range_text = pct_display(candle_range) if candle_range is not None else "-"
    candle_volume_text = num_display(latest_volume, 0) if latest_volume is not None else "-"
    entry_value = safe_float((trade_brief or {}).get("entry") or (confluence or {}).get("entry"))
    stop_value = safe_float((trade_brief or {}).get("stop") or (confluence or {}).get("stop"))
    target_value = safe_float((trade_brief or {}).get("target") or (trade_brief or {}).get("target_price"))
    entry = num_display(entry_value, 2)
    stop = num_display(stop_value, 2)
    target = num_display(target_value, 2)
    rr_value = None
    if (
        entry_value is not None
        and stop_value is not None
        and target_value is not None
        and abs(entry_value - stop_value) > 0
    ):
        rr_value = abs(target_value - entry_value) / abs(entry_value - stop_value)
    rr_display = f"1:{rr_value:.2f}" if rr_value is not None else "-"
    decision_label = human_trade_action(trade_brief or {}) if trade_brief else action_label((confluence or {}).get("signal"))
    if decision_label in {"Operar", "Comprar"}:
        decision_tone = "buy"
    elif decision_label in {"No operar", "Evitar"}:
        decision_tone = "avoid"
    else:
        decision_tone = "watch"
    checklist_rows = command_center_checklist_rows(trade_brief or {})
    blocking_check = next((item for item in checklist_rows if item.get("tone") != "buy"), None)
    if blocking_check:
        next_hint = f"{text_display(blocking_check.get('label'))}: {text_display(blocking_check.get('detail'))}"
    else:
        next_hint = "Listo si respeta entrada, stop, volumen y gestion de riesgo."
    visible_checks = checklist_rows[:5]
    checks_total = len(visible_checks)
    checks_ok = sum(1 for item in visible_checks if item.get("tone") == "buy")
    checks_pending = max(0, checks_total - checks_ok)
    checks_tone = "buy" if checks_pending == 0 and checks_total else "watch" if checks_pending <= 2 else "avoid"
    checks_summary = f"Checks {checks_ok}/{checks_total}" if checks_total else "Checks -"
    blockers_summary = "Sin bloqueos" if checks_pending == 0 and checks_total else f"Faltan {checks_pending}"
    confirmation_html = "".join(
        '<span class="chart-check-pill chart-check-{tone}" title="{detail}">'
        "<span><em>{label}</em><small>{detail}</small></span><strong>{status}</strong></span>".format(
            tone=html.escape(text_display(item.get("tone"))),
            label=html.escape(text_display(item.get("label"))),
            status=html.escape(text_display(item.get("status"))),
            detail=html.escape(text_display(item.get("detail"))),
        )
        for item in visible_checks
    )
    st.markdown(
        f"""
        <section class="chart-command-head">
          <div>
            <span>Gráfica profesional</span>
            <strong>{html.escape(chart_symbol)} · {html.escape(timeframe)}</strong>
            <small class="chart-next-action">Ahora: {html.escape(next_hint)}</small>
          </div>
          <aside>
            <b class="chart-level-decision chart-level-decision-{decision_tone}">Roxy {html.escape(decision_label)}</b>
            <b class="chart-level-entry">Entrada {html.escape(entry)}</b>
            <b class="chart-level-stop">Stop {html.escape(stop)}</b>
            <b class="chart-level-target">Target {html.escape(target)}</b>
            <b class="chart-level-rr">R:R {html.escape(rr_display)}</b>
            <b class="chart-level-check chart-level-check-{checks_tone}">{html.escape(checks_summary)} · {html.escape(blockers_summary)}</b>
            <b class="chart-level-data">Velas {visible_candles}</b>
            <b class="chart-level-data">Última {html.escape(latest_candle)}</b>
            <b class="chart-level-candle chart-level-candle-{candle_tone}">{html.escape(candle_label)} · {html.escape(candle_change_text)}</b>
            <b class="chart-level-data">{html.escape(candle_ohlc)}</b>
            <b class="chart-level-data">Rango {html.escape(candle_range_text)} · Vol {html.escape(candle_volume_text)}</b>
            <b class="chart-level-interact">Arrastra · Zoom · OHLC</b>
          </aside>
        </section>
        <section class="chart-check-strip">{confirmation_html}</section>
        """,
        unsafe_allow_html=True,
    )
    price_chart = build_professional_price_chart(
        clean_window,
        setup,
        confluence,
        trade_brief or {},
        paper_snapshot=st.session_state.get("alpaca_paper_journal_snapshot"),
        symbol=chart_symbol,
    ).properties(height=price_height)
    volume_chart = build_professional_volume_chart(clean_window)
    oscillator_chart = build_professional_oscillator_chart(clean_window)
    panels = [price_chart]
    if volume_chart is not None:
        panels.append(volume_chart.properties(height=volume_height))
    if oscillator_chart is not None:
        panels.append(oscillator_chart.properties(height=oscillator_height))
    def render_price_chart_fallback() -> None:
        fallback_cols = [
            col
            for col in ["close", "ema9", "sma20", "sma40", "sma100", "sma200"]
            if col in clean_window.columns
        ]
        st.markdown(
            f"""
            <section class="chart-fallback-state">
              <span>Fallback seguro</span>
              <strong>{html.escape(chart_symbol)} · precio y medias</strong>
              <p>La gráfica avanzada no renderizó, pero Roxy mantiene una vista simple para no perder contexto.</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
        if fallback_cols:
            fallback_df = clean_window[fallback_cols].apply(pd.to_numeric, errors="coerce")
            st.line_chart(fallback_df, height=min(price_height, 420), width="stretch")

    if len(panels) > 1:
        try:
            st.altair_chart(style_trading_chart(price_chart), width="stretch")
        except Exception:
            render_price_chart_fallback()
        with st.expander("Volumen y osciladores", expanded=False):
            for panel_idx, panel in enumerate(panels[1:], start=1):
                try:
                    st.altair_chart(style_trading_chart(panel), width="stretch", key=f"chart_indicator_{panel_idx}")
                except Exception:
                    st.caption("Indicador omitido por incompatibilidad temporal de gráfica.")
    else:
        try:
            st.altair_chart(style_trading_chart(price_chart), width="stretch")
        except Exception:
            render_price_chart_fallback()

    candle_table_cols = [col for col in ["ts", "open", "high", "low", "close", "volume"] if col in clean_window.columns]
    if {"open", "high", "low", "close"}.issubset(clean_window.columns):
        candle_table = clean_window[candle_table_cols].copy()
        close_values = pd.to_numeric(candle_table["close"], errors="coerce")
        high_values = pd.to_numeric(candle_table["high"], errors="coerce")
        low_values = pd.to_numeric(candle_table["low"], errors="coerce")
        candle_table["change_pct"] = close_values.pct_change()
        candle_table["range_pct"] = (high_values - low_values) / close_values.replace(0, pd.NA)
        candle_table = candle_table.tail(8).copy()
        if "ts" in candle_table.columns:
            candle_table["ts"] = pd.to_datetime(candle_table["ts"], errors="coerce").dt.strftime("%m/%d %H:%M")
        for column in ["open", "high", "low", "close"]:
            if column in candle_table.columns:
                candle_table[column] = candle_table[column].map(lambda value: num_display(value, 2))
        if "volume" in candle_table.columns:
            candle_table["volume"] = candle_table["volume"].map(lambda value: num_display(value, 0))
        candle_table["change_pct"] = candle_table["change_pct"].map(lambda value: pct_display(value))
        candle_table["range_pct"] = candle_table["range_pct"].map(lambda value: pct_display(value))
        candle_table = candle_table.rename(
            columns={
                "ts": "Hora",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volumen",
                "change_pct": "Cambio",
                "range_pct": "Rango",
            }
        )
        with st.expander("Últimas 8 velas OHLC", expanded=False):
            st.caption("Lectura rápida para comparar la vela actual contra las previas sin salir de la gráfica.")
            st.dataframe(candle_table, width="stretch", hide_index=True, height=260)


def render_command_center_analysis(
    context: dict[str, Any],
    *,
    app_brief: dict,
    account_equity: float,
    risk_per_trade_pct: float,
) -> None:
    chart_df = context.get("chart_df") if isinstance(context.get("chart_df"), pd.DataFrame) else pd.DataFrame()
    setup = context.get("setup") or {}
    trade_brief = context.get("trade_brief") or {}
    if chart_df.empty or not setup or not trade_brief:
        st.info(f"No hay suficiente historial para analizar {context.get('symbol', '-')}.")
        return
    confluence = context.get("confluence") or {}
    ticket = trade_plan_platform_preview(
        trade_brief,
        account_equity=float(account_equity),
        risk_per_trade_pct=float(risk_per_trade_pct),
        source_freshness=app_brief.get("source_freshness"),
        market_session=app_brief.get("market_session"),
    )
    render_professional_chart_block(chart_df, setup, confluence, trade_brief, price_height=460, volume_height=115)
    render_command_center_panel(trade_brief, platform_ticket=ticket)
    with st.expander("Lectura técnica, niveles y contexto", expanded=False):
        render_chart_strategy_summary(setup, confluence, trade_brief, chart_df)
        render_chart_level_plan(chart_df, setup, confluence, trade_brief)
    render_operation_gate(trade_brief)
    with st.expander("Detalles: por que Roxy toma esta decision", expanded=False):
        render_trade_plan_platform_preview(ticket)
        render_decision_reason(trade_brief)
        render_decision_transition(trade_brief)
        render_strategy_event_panel(chart_df, setup)


def platform_badge_rows(env: dict[str, str] | None = None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for platform_id, profile in PLATFORM_PROFILES.items():
        brand = PLATFORM_BADGE_BRANDS.get(platform_id, {})
        try:
            status = platform_credential_status(platform_id, env=env)
        except Exception:
            status = {"mode": "NEEDS_CREDENTIALS", "configured": False}
        mode = str(status.get("mode") or "NEEDS_CREDENTIALS")
        configured = bool(status.get("configured"))
        rows.append(
            {
                "platform_id": platform_id,
                "name": str(profile.get("name") or platform_id),
                "abbr": str(brand.get("abbr") or platform_id[:2].upper()),
                "asset": str(brand.get("asset") or ", ".join(profile.get("assets", []))),
                "use": str(brand.get("use") or profile.get("best_for") or "-"),
                "mode": connection_mode_label(mode),
                "tone": "buy" if configured else "watch",
                "accent": str(brand.get("accent") or "#38bdf8"),
            }
        )
    return rows


def live_provider_rows(env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    source = env if env is not None else os.environ

    def has_keys(keys: tuple[str, ...]) -> tuple[list[str], list[str]]:
        present = [key for key in keys if str(source.get(key) or "").strip()]
        missing = [key for key in keys if key not in present]
        return present, missing

    provider_specs = [
        {
            "provider": "yfinance",
            "role": "Fallback charts",
            "keys": (),
            "mode": "ON",
            "tone": "watch",
            "latency": "Delay/limitado",
            "next": "Mantener como respaldo; no usar como fuente principal de ejecucion.",
        },
        {
            "provider": "Alpaca",
            "role": "Stocks/Crypto live + paper",
            "keys": ("ALPACA_API_KEY", "ALPACA_API_SECRET"),
            "mode": "PAPER_READY",
            "tone": "buy",
            "latency": "WebSocket",
            "next": "Guardar key/secret en vault o env; iniciar solo paper trading.",
        },
        {
            "provider": "Tradier",
            "role": "Opciones/Greeks",
            "keys": ("TRADIER_ACCESS_TOKEN",),
            "mode": "OPTIONS_READY",
            "tone": "buy",
            "latency": "API",
            "next": "Usar para chain de opciones y scoring con spreads.",
        },
        {
            "provider": "Schwab",
            "role": "Stocks/options broker",
            "keys": ("SCHWAB_CLIENT_ID", "SCHWAB_CLIENT_SECRET", "SCHWAB_ACCESS_TOKEN", "SCHWAB_ACCOUNT_HASH"),
            "mode": "PREVIEW_READY",
            "tone": "watch",
            "latency": "OAuth/API",
            "next": "Completar OAuth; mantener envio real apagado.",
        },
        {
            "provider": "Finviz",
            "role": "Screener visual",
            "keys": (),
            "mode": "REFERENCE",
            "tone": "watch",
            "latency": "No broker",
            "next": "Usar como benchmark visual, no fuente principal live.",
        },
        {
            "provider": "TC2000",
            "role": "Charting externo",
            "keys": (),
            "mode": "MANUAL_LINK",
            "tone": "neutral",
            "latency": "Plataforma",
            "next": "Abrir simbolo/contexto externo; no depender de API para ejecucion.",
        },
    ]
    rows: list[dict[str, Any]] = []
    for spec in provider_specs:
        keys = tuple(spec.get("keys") or ())
        present, missing = has_keys(keys)
        configured = not missing if keys else True
        if keys and not configured:
            status = "Faltan credenciales"
            tone = "avoid" if spec["provider"] == "Alpaca" else "watch"
        elif spec["provider"] == "yfinance":
            status = "Activo fallback"
            tone = spec["tone"]
        elif not keys:
            status = "Referencia"
            tone = spec["tone"]
        else:
            status = "Listo paper/preview"
            tone = spec["tone"]
        rows.append(
            {
                "provider": spec["provider"],
                "role": spec["role"],
                "status": status,
                "tone": tone,
                "mode": spec["mode"],
                "latency": spec["latency"],
                "configured": configured,
                "present": len(present),
                "missing": ", ".join(missing) if missing else "-",
                "next": spec["next"],
            }
        )
    return rows


def alpaca_operations_gate(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env if env is not None else os.environ

    def env_value(*keys: str) -> tuple[str, str]:
        for key in keys:
            value = str(source.get(key) or "").strip()
            if value:
                return value, key
        return "", ""

    def env_bool_value(key: str, default: bool = False) -> bool:
        raw = str(source.get(key) or "").strip().lower()
        if not raw:
            return default
        return raw in {"1", "true", "yes", "on", "paper"}

    key_value, key_name = env_value("ALPACA_API_KEY")
    secret_value, secret_name = env_value("ALPACA_API_SECRET", "ALPACA_SECRET_KEY")
    endpoint, endpoint_name = env_value("ALPACA_BASE_URL", "ALPACA_ENDPOINT", "ALPACA_API_BASE_URL")
    paper_flag = env_bool_value("ALPACA_PAPER", True)
    endpoint_lower = endpoint.lower()
    endpoint_mode = "paper" if paper_flag or "paper-api.alpaca.markets" in endpoint_lower else "live"
    configured = bool(key_value and secret_value)
    live_detected = configured and endpoint_mode == "live"
    paper_ready = configured and endpoint_mode == "paper"
    present_keys = [name for name in [key_name, secret_name, endpoint_name] if name]
    missing = []
    if not key_value:
        missing.append("ALPACA_API_KEY")
    if not secret_value:
        missing.append("ALPACA_API_SECRET or ALPACA_SECRET_KEY")
    if live_detected:
        status = "Live bloqueado"
        tone = "avoid"
        mode = "LIVE_LOCKED"
        next_step = "Cambiar a ALPACA_PAPER=true y endpoint paper; operar real exige aprobacion manual, kill switch y track record paper."
    elif paper_ready:
        status = "Paper listo"
        tone = "buy"
        mode = "PAPER_ONLY"
        next_step = "Usar solo paper para forward-test; no hay envio real desde el dashboard."
    elif configured:
        status = "Credenciales listas"
        tone = "watch"
        mode = "PREVIEW_ONLY"
        next_step = "Confirmar ALPACA_PAPER=true antes de habilitar cualquier orden paper."
    else:
        status = "Faltan credenciales"
        tone = "avoid"
        mode = "NOT_CONFIGURED"
        next_step = "Configurar variables de entorno fuera del repo; nunca pegar secretos en codigo."
    return {
        "status": status,
        "tone": tone,
        "mode": mode,
        "configured": configured,
        "paper_ready": paper_ready,
        "paper_orders_allowed": paper_ready,
        "live_orders_allowed": False,
        "live_detected": live_detected,
        "endpoint_mode": endpoint_mode,
        "paper_flag": paper_flag,
        "present_keys": ", ".join(present_keys) if present_keys else "-",
        "missing": ", ".join(missing) if missing else "-",
        "next": next_step,
    }


def render_alpaca_operations_gate(env: dict[str, str] | None = None) -> str:
    gate = alpaca_operations_gate(env)
    tone = text_display(gate.get("tone"))
    paper_state = "ON" if gate.get("paper_orders_allowed") else "OFF"
    live_state = "ON" if gate.get("live_orders_allowed") else "LOCKED"
    return (
        f'<section class="alpaca-gate alpaca-gate-{html.escape(tone)}">'
        '<div><span>Alpaca Safety Gate</span>'
        f'<strong>{html.escape(text_display(gate.get("status")))}</strong>'
        f'<em>{html.escape(text_display(gate.get("mode")))} · Endpoint {html.escape(text_display(gate.get("endpoint_mode")))}</em></div>'
        f'<p>{html.escape(text_display(gate.get("next")))}</p>'
        '<aside>'
        f'<b>Paper orders: {html.escape(paper_state)}</b>'
        f'<b>Live orders: {html.escape(live_state)}</b>'
        f'<small>Creds: {html.escape(text_display(gate.get("present_keys")))} · Faltan: {html.escape(text_display(gate.get("missing")))}</small>'
        '</aside></section>'
    )



def alpaca_paper_account_snapshot(env: dict[str, str] | None = None, client_factory: Any | None = None) -> dict[str, Any]:
    source = env if env is not None else os.environ
    gate = alpaca_operations_gate(source)
    base = {
        "status": "No conectado",
        "tone": "avoid",
        "mode": gate.get("mode"),
        "connected": False,
        "paper_ready": bool(gate.get("paper_ready")),
        "buying_power": None,
        "cash": None,
        "portfolio_value": None,
        "equity": None,
        "account_status": "-",
        "trading_blocked": None,
        "pattern_day_trader": None,
        "detail": text_display(gate.get("next")),
    }
    if not gate.get("paper_ready"):
        base["status"] = "Paper pendiente" if gate.get("configured") else "Credenciales pendientes"
        base["tone"] = text_display(gate.get("tone"))
        return base

    key = str(source.get("ALPACA_API_KEY") or "").strip()
    secret = str(source.get("ALPACA_API_SECRET") or source.get("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        return base

    try:
        if client_factory is None:
            from alpaca.trading.client import TradingClient

            def client_factory(api_key: str, secret_key: str):
                return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)

        client = client_factory(key, secret)
        account = client.get_account()
    except Exception as exc:
        return {
            **base,
            "status": "Paper sin conexion",
            "tone": "watch",
            "detail": f"No se pudo leer cuenta paper: {type(exc).__name__}. Revisar env/permiso sin exponer secretos.",
        }

    def attr(name: str) -> Any:
        if isinstance(account, dict):
            return account.get(name)
        return getattr(account, name, None)

    return {
        **base,
        "status": "Paper conectado",
        "tone": "buy",
        "mode": "PAPER_ACCOUNT_SYNC",
        "connected": True,
        "buying_power": safe_float(attr("buying_power")),
        "cash": safe_float(attr("cash")),
        "portfolio_value": safe_float(attr("portfolio_value")),
        "equity": safe_float(attr("equity")),
        "account_status": text_display(attr("status")),
        "trading_blocked": bool(attr("trading_blocked")) if attr("trading_blocked") is not None else None,
        "pattern_day_trader": bool(attr("pattern_day_trader")) if attr("pattern_day_trader") is not None else None,
        "detail": "Lectura read-only de Alpaca paper. Ordenes reales siguen bloqueadas.",
    }


def render_alpaca_paper_account_panel(env: dict[str, str] | None = None) -> str:
    snapshot = alpaca_paper_account_snapshot(env)
    tone = text_display(snapshot.get("tone"))
    blocked = "SI" if snapshot.get("trading_blocked") else "NO" if snapshot.get("trading_blocked") is not None else "-"
    pdt = "SI" if snapshot.get("pattern_day_trader") else "NO" if snapshot.get("pattern_day_trader") is not None else "-"
    return (
        f'<section class="alpaca-paper-panel alpaca-paper-{html.escape(tone)}">'
        '<div><span>Alpaca Paper Account</span>'
        f'<strong>{html.escape(text_display(snapshot.get("status")))}</strong>'
        f'<em>{html.escape(text_display(snapshot.get("mode")))} · Estado {html.escape(text_display(snapshot.get("account_status")))}</em></div>'
        '<aside>'
        f'<b>Buying power</b><strong>{html.escape(num_display(snapshot.get("buying_power"), 2))}</strong>'
        f'<b>Portfolio</b><strong>{html.escape(num_display(snapshot.get("portfolio_value"), 2))}</strong>'
        f'<b>Cash</b><strong>{html.escape(num_display(snapshot.get("cash"), 2))}</strong>'
        '</aside>'
        f'<p>{html.escape(text_display(snapshot.get("detail")))} · Blocked: {html.escape(blocked)} · PDT: {html.escape(pdt)}</p>'
        '</section>'
    )



def alpaca_attr(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def alpaca_time_ago(value: Any, now: datetime | None = None) -> str:
    if value in (None, "", "-"):
        return "-"
    if isinstance(value, str):
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return text_display(value)
    elif isinstance(value, datetime):
        parsed = value
    else:
        return text_display(value)
    current = now or datetime.utcnow()
    if parsed.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=parsed.tzinfo)
    delta = current - parsed
    seconds = max(0, int(delta.total_seconds()))
    minutes = seconds // 60
    if minutes < 1:
        return "ahora"
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    return f"{hours // 24}d"


def alpaca_paper_journal_snapshot(
    env: dict[str, str] | None = None,
    client_factory: Any | None = None,
    *,
    limit: int = 8,
    now: datetime | None = None,
) -> dict[str, Any]:
    source = env if env is not None else os.environ
    gate = alpaca_operations_gate(source)
    base = {
        "status": "Paper journal pendiente",
        "tone": text_display(gate.get("tone")),
        "connected": False,
        "positions": [],
        "orders": [],
        "summary": {"open_positions": 0, "recent_orders": 0, "unrealized_pl": 0.0, "exposure": 0.0, "open_winners": 0},
        "detail": text_display(gate.get("next")),
    }
    if not gate.get("paper_ready"):
        return base
    key = str(source.get("ALPACA_API_KEY") or "").strip()
    secret = str(source.get("ALPACA_API_SECRET") or source.get("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        return base
    try:
        if client_factory is None:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            def client_factory(api_key: str, secret_key: str):
                return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)

            order_filter = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=int(limit), nested=True)
        else:
            order_filter = None
        client = client_factory(key, secret)
        positions_raw = client.get_all_positions()
        try:
            orders_raw = client.get_orders(filter=order_filter) if order_filter is not None else client.get_orders()
        except TypeError:
            orders_raw = client.get_orders()
    except Exception as exc:
        return {
            **base,
            "status": "Paper journal sin conexion",
            "tone": "watch",
            "detail": f"No se pudo leer journal paper: {type(exc).__name__}. Revisar env/permiso sin exponer secretos.",
        }
    if isinstance(positions_raw, dict):
        positions_raw = positions_raw.get("positions") or positions_raw.get("data") or []
    if isinstance(orders_raw, dict):
        orders_raw = orders_raw.get("orders") or orders_raw.get("data") or []
    entry_time_lookup: dict[str, Any] = {}
    orders: list[dict[str, Any]] = []
    for order in list(orders_raw or [])[: max(1, int(limit))]:
        symbol = text_display(alpaca_attr(order, "symbol")).upper()
        submitted_at = alpaca_attr(order, "submitted_at")
        filled_at = alpaca_attr(order, "filled_at")
        side = text_display(alpaca_attr(order, "side")).lower()
        status = text_display(alpaca_attr(order, "status")).lower()
        if symbol and symbol != "-" and side == "buy" and status in {"filled", "partially_filled"}:
            entry_time_lookup.setdefault(symbol, filled_at or submitted_at)
        orders.append(
            {
                "symbol": symbol,
                "side": side.upper(),
                "status": status.upper(),
                "qty": safe_float(alpaca_attr(order, "qty")),
                "filled_qty": safe_float(alpaca_attr(order, "filled_qty")),
                "type": text_display(alpaca_attr(order, "type")).upper(),
                "order_class": text_display(alpaca_attr(order, "order_class")).upper(),
                "submitted": alpaca_time_ago(submitted_at, now=now),
                "filled": alpaca_time_ago(filled_at, now=now),
                "submitted_at": text_display(submitted_at),
                "filled_at": text_display(filled_at),
                "limit_price": safe_float(alpaca_attr(order, "limit_price")),
                "stop_price": safe_float(alpaca_attr(order, "stop_price")),
                "filled_avg_price": safe_float(alpaca_attr(order, "filled_avg_price")),
            }
        )
    positions: list[dict[str, Any]] = []
    for position in list(positions_raw or [])[: max(1, int(limit))]:
        symbol = text_display(alpaca_attr(position, "symbol")).upper()
        unrealized = safe_float(alpaca_attr(position, "unrealized_pl")) or 0.0
        positions.append(
            {
                "symbol": symbol,
                "qty": safe_float(alpaca_attr(position, "qty")),
                "avg_entry": safe_float(alpaca_attr(position, "avg_entry_price")),
                "current": safe_float(alpaca_attr(position, "current_price")),
                "market_value": safe_float(alpaca_attr(position, "market_value")) or 0.0,
                "unrealized_pl": unrealized,
                "unrealized_plpc": safe_float(alpaca_attr(position, "unrealized_plpc")),
                "entry_at": text_display(entry_time_lookup.get(symbol)),
                "time_in_trade": alpaca_time_ago(entry_time_lookup.get(symbol), now=now),
                "tone": "buy" if unrealized >= 0 else "avoid",
            }
        )
    summary = {
        "open_positions": len(positions),
        "recent_orders": len(orders),
        "unrealized_pl": round(sum(safe_float(row.get("unrealized_pl")) or 0.0 for row in positions), 2),
        "exposure": round(sum(safe_float(row.get("market_value")) or 0.0 for row in positions), 2),
        "open_winners": sum(1 for row in positions if (safe_float(row.get("unrealized_pl")) or 0.0) >= 0),
    }
    return {
        **base,
        "status": "Paper journal conectado",
        "tone": "buy",
        "connected": True,
        "positions": positions,
        "orders": orders,
        "summary": summary,
        "detail": "Lectura read-only de posiciones y ordenes paper; no modifica cuenta.",
    }


def alpaca_paper_strategy_ranking(snapshot: dict[str, Any], opportunity_table: pd.DataFrame, *, limit: int = 5) -> pd.DataFrame:
    columns = ["strategy", "symbols", "open_positions", "orders", "pnl", "exposure", "win_rate", "tone"]
    strategy_lookup: dict[str, str] = {}
    if not opportunity_table.empty and "symbol" in opportunity_table.columns:
        for row in opportunity_table.to_dict("records"):
            symbol = text_display(row.get("symbol")).upper()
            if symbol and symbol != "-":
                strategy_lookup.setdefault(symbol, text_display(row.get("strategy_family") or row.get("Setup") or row.get("setup")))
    grouped: dict[str, dict[str, Any]] = {}

    def bucket(symbol: str) -> dict[str, Any]:
        strategy = strategy_lookup.get(symbol) or "Sin clasificar"
        return grouped.setdefault(
            strategy,
            {
                "strategy": strategy,
                "symbols": set(),
                "open_positions": 0,
                "orders": 0,
                "pnl": 0.0,
                "exposure": 0.0,
                "wins": 0,
                "closed": 0,
            },
        )

    for position in snapshot.get("positions") or []:
        symbol = text_display(position.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        item = bucket(symbol)
        pnl = safe_float(position.get("unrealized_pl")) or 0.0
        item["symbols"].add(symbol)
        item["open_positions"] += 1
        item["pnl"] += pnl
        item["exposure"] += safe_float(position.get("market_value")) or 0.0
        if pnl >= 0:
            item["wins"] += 1
    for order in snapshot.get("orders") or []:
        symbol = text_display(order.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        item = bucket(symbol)
        item["symbols"].add(symbol)
        item["orders"] += 1
        if text_display(order.get("status")).upper() in {"FILLED", "PARTIALLY_FILLED"}:
            item["closed"] += 1
    rows: list[dict[str, Any]] = []
    for item in grouped.values():
        denominator = max(int(item["open_positions"]), int(item["closed"]), 1)
        win_rate = (int(item["wins"]) / denominator) if denominator else 0.0
        pnl = round(float(item["pnl"]), 2)
        rows.append(
            {
                "strategy": text_display(item["strategy"]),
                "symbols": " · ".join(sorted(item["symbols"])) or "-",
                "open_positions": int(item["open_positions"]),
                "orders": int(item["orders"]),
                "pnl": pnl,
                "exposure": round(float(item["exposure"]), 2),
                "win_rate": round(win_rate, 4),
                "tone": "buy" if pnl >= 0 else "avoid",
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    result = pd.DataFrame(rows, columns=columns)
    return result.sort_values(["pnl", "open_positions", "orders"], ascending=[False, False, False]).head(limit).reset_index(drop=True)


def alpaca_marker_timestamp(value: Any) -> pd.Timestamp | None:
    if value in (None, "", "-"):
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    timestamp = pd.Timestamp(parsed)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp


def alpaca_paper_chart_markers(snapshot: dict[str, Any], chart_window: pd.DataFrame, symbol: str) -> pd.DataFrame:
    columns = ["ts", "price", "event", "side", "status", "label", "tone"]
    if chart_window.empty or "ts" not in chart_window.columns:
        return pd.DataFrame(columns=columns)
    clean_symbol = text_display(symbol).upper()
    if not clean_symbol or clean_symbol == "-":
        return pd.DataFrame(columns=columns)
    ts_series = pd.to_datetime(chart_window["ts"], errors="coerce").dropna()
    if ts_series.empty:
        return pd.DataFrame(columns=columns)
    first_raw = pd.Timestamp(ts_series.min())
    last_raw = pd.Timestamp(ts_series.max())
    first_ts = first_raw.tz_convert(None) if first_raw.tzinfo is not None else first_raw
    last_ts = last_raw.tz_convert(None) if last_raw.tzinfo is not None else last_raw
    rows: list[dict[str, Any]] = []

    def add_marker(ts_value: Any, price_value: Any, event: str, side: str, status: str, tone: str) -> None:
        ts = alpaca_marker_timestamp(ts_value)
        price = safe_float(price_value)
        if ts is None or price is None or price <= 0:
            return
        if ts < first_ts or ts > last_ts:
            return
        label = f"{event} {clean_symbol} {price:.2f}"
        rows.append(
            {"ts": ts, "price": price, "event": event, "side": side, "status": status, "label": label, "tone": tone}
        )

    for order in snapshot.get("orders") or []:
        order_symbol = text_display(order.get("symbol")).upper()
        if order_symbol != clean_symbol:
            continue
        side = text_display(order.get("side")).upper()
        status = text_display(order.get("status")).upper()
        if status not in {"FILLED", "PARTIALLY_FILLED"}:
            continue
        event = "Paper entrada" if side == "BUY" else "Paper salida"
        tone = "buy" if side == "BUY" else "avoid"
        price = safe_float(order.get("filled_avg_price")) or safe_float(order.get("limit_price")) or safe_float(order.get("stop_price"))
        add_marker(order.get("filled_at") or order.get("submitted_at"), price, event, side, status, tone)

    for position in snapshot.get("positions") or []:
        position_symbol = text_display(position.get("symbol")).upper()
        if position_symbol != clean_symbol:
            continue
        if any(row.get("side") == "BUY" for row in rows):
            continue
        ts = alpaca_marker_timestamp(position.get("entry_at")) or last_ts
        add_marker(ts, position.get("avg_entry") or position.get("current"), "Paper abierta", "BUY", "OPEN", "buy")

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).drop_duplicates(["ts", "price", "event", "side"]).sort_values("ts").reset_index(drop=True)


def alpaca_paper_open_position_plan(
    snapshot: dict[str, Any],
    opportunity_table: pd.DataFrame,
    *,
    limit: int = 6,
) -> pd.DataFrame:
    columns = [
        "symbol",
        "qty",
        "current",
        "avg_entry",
        "stop",
        "target",
        "risk_to_stop",
        "reward_to_target",
        "pnl",
        "pnl_pct",
        "time_in_trade",
        "strategy",
        "status",
        "tone",
    ]
    opportunities: dict[str, dict[str, Any]] = {}
    if not opportunity_table.empty and "symbol" in opportunity_table.columns:
        for row in opportunity_table.to_dict("records"):
            symbol = text_display(row.get("symbol")).upper()
            if not symbol or symbol == "-":
                continue
            entry = safe_float(row.get("entry"))
            target = safe_float(row.get("target_price") or row.get("recommended_target_price"))
            target_pct = safe_float(row.get("target_pct") or row.get("recommended_target_pct"))
            if target is None and entry is not None and target_pct is not None:
                target = entry * (1.0 + target_pct)
            opportunities.setdefault(
                symbol,
                {
                    "stop": safe_float(row.get("stop")),
                    "target": target,
                    "strategy": text_display(row.get("strategy_family") or row.get("Setup") or row.get("setup")),
                },
            )
    rows: list[dict[str, Any]] = []
    for position in snapshot.get("positions") or []:
        symbol = text_display(position.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        current = safe_float(position.get("current"))
        avg_entry = safe_float(position.get("avg_entry"))
        plan = opportunities.get(symbol, {})
        stop = safe_float(plan.get("stop"))
        target = safe_float(plan.get("target"))
        risk_to_stop = ((current - stop) / current) if current and stop is not None else None
        reward_to_target = ((target - current) / current) if current and target is not None else None
        pnl = safe_float(position.get("unrealized_pl")) or 0.0
        pnl_pct = safe_float(position.get("unrealized_plpc"))
        if stop is None or target is None:
            status = "Falta plan"
            tone = "watch"
        elif current is not None and current <= stop:
            status = "Stop tocado"
            tone = "avoid"
        elif current is not None and current >= target:
            status = "Target tocado"
            tone = "buy"
        elif risk_to_stop is not None and risk_to_stop > 0.035:
            status = "Riesgo alto"
            tone = "avoid"
        elif reward_to_target is not None and reward_to_target <= 0:
            status = "Sin upside"
            tone = "watch"
        else:
            status = "Controlado"
            tone = "buy" if pnl >= 0 else "watch"
        rows.append(
            {
                "symbol": symbol,
                "qty": safe_float(position.get("qty")),
                "current": current,
                "avg_entry": avg_entry,
                "stop": stop,
                "target": target,
                "risk_to_stop": risk_to_stop,
                "reward_to_target": reward_to_target,
                "pnl": round(pnl, 2),
                "pnl_pct": pnl_pct,
                "time_in_trade": text_display(position.get("time_in_trade")),
                "strategy": text_display(plan.get("strategy") or "Sin clasificar"),
                "status": status,
                "tone": tone,
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(["tone", "pnl"], ascending=[True, False]).head(limit).reset_index(drop=True)


def render_alpaca_paper_journal_panel(env: dict[str, str] | None = None) -> dict[str, Any]:
    snapshot = alpaca_paper_journal_snapshot(env, limit=8)
    st.session_state["alpaca_paper_journal_snapshot"] = snapshot
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    positions = snapshot.get("positions") if isinstance(snapshot.get("positions"), list) else []
    orders = snapshot.get("orders") if isinstance(snapshot.get("orders"), list) else []
    position_cards = []
    for row in positions[:4]:
        tone = text_display(row.get("tone"))
        position_cards.append(
            f'<section class="paper-journal-card paper-journal-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("symbol")))}</strong><span>{html.escape(text_display(row.get("time_in_trade")))}</span></header>'
            f'<div><b>Qty {html.escape(num_display(row.get("qty"), 2))}</b><b>Entry {html.escape(num_display(row.get("avg_entry"), 2))}</b><b>Now {html.escape(num_display(row.get("current"), 2))}</b></div>'
            f'<p>P&L {html.escape(num_display(row.get("unrealized_pl"), 2))} · {html.escape(pct_display(row.get("unrealized_plpc")))}</p>'
            "</section>"
        )
    order_rows = []
    for row in orders[:6]:
        order_rows.append(
            "<tr>"
            f"<td>{html.escape(text_display(row.get('symbol')))}</td>"
            f"<td>{html.escape(text_display(row.get('side')))}</td>"
            f"<td>{html.escape(text_display(row.get('status')))}</td>"
            f"<td>{html.escape(num_display(row.get('filled_qty') or row.get('qty'), 2))}</td>"
            f"<td>{html.escape(text_display(row.get('submitted')))}</td>"
            f"<td>{html.escape(text_display(row.get('type')))}</td>"
            "</tr>"
        )
    empty_positions = (
        '<section class="paper-journal-empty">Sin posiciones paper abiertas.</section>' if not position_cards else ""
    )
    empty_orders = '<tr><td colspan="6">Sin ordenes paper recientes.</td></tr>' if not order_rows else ""
    st.markdown(
        f'<section class="paper-journal-panel paper-journal-panel-{html.escape(text_display(snapshot.get("tone")))}">'
        f'<header><strong>Paper Trade Journal</strong><span>{html.escape(text_display(snapshot.get("status")))} · {html.escape(text_display(snapshot.get("detail")))}</span></header>'
        '<div class="paper-journal-summary">'
        f'<b><span>Posiciones</span><strong>{int(summary.get("open_positions") or 0)}</strong></b>'
        f'<b><span>P&L abierto</span><strong>{html.escape(num_display(summary.get("unrealized_pl"), 2))}</strong></b>'
        f'<b><span>Exposicion</span><strong>{html.escape(num_display(summary.get("exposure"), 2))}</strong></b>'
        f'<b><span>Ganadoras</span><strong>{int(summary.get("open_winners") or 0)}</strong></b>'
        f'<b><span>Ordenes</span><strong>{int(summary.get("recent_orders") or 0)}</strong></b>'
        "</div>"
        f'<div class="paper-journal-grid">{"".join(position_cards)}{empty_positions}</div>'
        '<div class="paper-journal-table"><table><thead><tr><th>Ticker</th><th>Side</th><th>Status</th><th>Qty</th><th>Hace</th><th>Tipo</th></tr></thead>'
        f'<tbody>{"".join(order_rows) or empty_orders}</tbody></table></div>'
        "</section>",
        unsafe_allow_html=True,
    )
    return snapshot


def render_alpaca_paper_strategy_ranking(snapshot: dict[str, Any], opportunity_table: pd.DataFrame) -> None:
    rows = alpaca_paper_strategy_ranking(snapshot, opportunity_table, limit=5)
    if rows.empty:
        st.markdown(
            '<section class="paper-strategy-panel"><header><strong>Paper Strategy Ranking</strong><span>Esperando posiciones u ordenes paper para medir edge real.</span></header>'
            '<div class="paper-strategy-empty">Cuando Roxy ejecute paper trades, aqui veras P&L, win-rate, exposicion y actividad por estrategia.</div></section>',
            unsafe_allow_html=True,
        )
        return
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<section class="paper-strategy-card paper-strategy-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("strategy")))}</strong><span>{html.escape(pct_display(row.get("win_rate")))}</span></header>'
            f'<div><b>P&L {html.escape(num_display(row.get("pnl"), 2))}</b><b>Expo {html.escape(num_display(row.get("exposure"), 2))}</b><b>Pos {int(row.get("open_positions") or 0)}</b><b>Ord {int(row.get("orders") or 0)}</b></div>'
            f'<p>{html.escape(text_display(row.get("symbols")))}</p>'
            "</section>"
        )
    st.markdown(
        '<section class="paper-strategy-panel"><header><strong>Paper Strategy Ranking</strong><span>Rentabilidad paper agrupada por estrategia aproximada de Roxy.</span></header><div class="paper-strategy-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )


def render_alpaca_paper_open_positions_panel(snapshot: dict[str, Any], opportunity_table: pd.DataFrame) -> None:
    rows = alpaca_paper_open_position_plan(snapshot, opportunity_table, limit=6)
    if rows.empty:
        st.markdown(
            '<section class="paper-position-panel"><header><strong>Paper Open Positions</strong>'
            '<span>Sin posiciones paper abiertas para controlar stop, target y tiempo.</span></header>'
            '<div class="paper-position-empty">Cuando haya una posicion abierta, Roxy mostrara riesgo a stop, upside a target, P&L y tiempo en trade.</div></section>',
            unsafe_allow_html=True,
        )
        return
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<section class="paper-position-card paper-position-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("symbol")))}</strong><span>{html.escape(text_display(row.get("status")))}</span></header>'
            f'<div><b>Now {html.escape(num_display(row.get("current"), 2))}</b><b>Stop {html.escape(num_display(row.get("stop"), 2))}</b>'
            f'<b>Target {html.escape(num_display(row.get("target"), 2))}</b><b>{html.escape(text_display(row.get("time_in_trade")))}</b></div>'
            f'<p>P&L {html.escape(num_display(row.get("pnl"), 2))} · {html.escape(pct_display(row.get("pnl_pct")))} '
            f'| Riesgo {html.escape(pct_display(row.get("risk_to_stop")))} | Upside {html.escape(pct_display(row.get("reward_to_target")))}</p>'
            f'<small>{html.escape(text_display(row.get("strategy")))}</small>'
            "</section>"
        )
    st.markdown(
        '<section class="paper-position-panel"><header><strong>Paper Open Positions</strong>'
        '<span>Control operativo: stop, target, P&L y tiempo en trade. Read-only.</span></header>'
        f'<div class="paper-position-grid">{"".join(cards)}</div></section>',
        unsafe_allow_html=True,
    )


def alpaca_paper_autotrade_enabled(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    raw = str(source.get("ROXY_ALPACA_PAPER_AUTOTRADE") or "").strip().lower()
    return raw in {"1", "true", "yes", "on", "paper"}


def alpaca_paper_order_candidates(
    table: pd.DataFrame,
    *,
    account_equity: float = 500.0,
    risk_pct: float = 0.01,
    limit: int = 3,
) -> pd.DataFrame:
    columns = ["symbol", "side", "qty", "entry", "stop", "take_profit", "risk_dollars", "notional", "reason"]
    if table.empty:
        return pd.DataFrame(columns=columns)
    risk_budget = max(0.0, safe_float(account_equity) or 0.0) * max(0.0, safe_float(risk_pct) or 0.0)
    rows: list[dict[str, Any]] = []
    for item in table.to_dict("records"):
        if not opportunity_is_trade_ready(item):
            continue
        symbol = text_display(item.get("symbol")).upper()
        market = text_display(item.get("market")).lower()
        if not symbol or symbol == "-" or market == "crypto" or "/" in symbol:
            continue
        entry = safe_float(item.get("entry"))
        stop = safe_float(item.get("stop"))
        target = safe_float(item.get("target_price"))
        target_pct = safe_float(item.get("target_pct"))
        if target is None and entry is not None and target_pct is not None:
            target = entry * (1.0 + target_pct)
        if entry is None or stop is None or target is None:
            continue
        per_share_risk = abs(entry - stop)
        if per_share_risk <= 0:
            continue
        qty = int(risk_budget // per_share_risk)
        if qty <= 0:
            qty = 1
        rows.append(
            {
                "symbol": symbol,
                "side": "buy",
                "qty": qty,
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "take_profit": round(target, 2),
                "risk_dollars": round(qty * per_share_risk, 2),
                "notional": round(qty * entry, 2),
                "reason": text_display(item.get("por_que") or item.get("raw_reason") or item.get("strategy_family")),
            }
        )
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows, columns=columns)


def alpaca_paper_execution_gaps(table: pd.DataFrame, *, limit: int = 4) -> pd.DataFrame:
    columns = ["symbol", "status", "next_step", "entry", "stop", "take_profit"]
    if table.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for item in table.to_dict("records"):
        symbol = text_display(item.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        market = text_display(item.get("market")).lower()
        entry = safe_float(item.get("entry"))
        stop = safe_float(item.get("stop"))
        target = safe_float(item.get("target_price"))
        target_pct = safe_float(item.get("target_pct"))
        if target is None and entry is not None and target_pct is not None:
            target = entry * (1.0 + target_pct)
        if market == "crypto" or "/" in symbol:
            status = "No soportado"
            next_step = "Alpaca paper equity solo opera acciones aqui; crypto queda como alerta/estudio."
        elif not opportunity_is_trade_ready(item):
            status = "Esperando setup"
            next_step = text_display(item.get("cambia_si") or opportunity_change_label(item))
        elif entry is None or stop is None or target is None:
            status = "Faltan niveles"
            next_step = "Necesita entrada, stop y take profit antes de armar bracket paper."
        elif abs(entry - stop) <= 0:
            status = "Stop invalido"
            next_step = "Stop debe estar separado de la entrada para medir riesgo real."
        else:
            continue
        rows.append(
            {
                "symbol": symbol,
                "status": status,
                "next_step": next_step,
                "entry": round(entry, 2) if entry is not None else "-",
                "stop": round(stop, 2) if stop is not None else "-",
                "take_profit": round(target, 2) if target is not None else "-",
            }
        )
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows, columns=columns)


def alpaca_paper_gap_checklist(table: pd.DataFrame, *, limit: int = 4) -> pd.DataFrame:
    columns = ["symbol", "status", "ready", "missing", "next_step", "tone"]
    if table.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for item in table.to_dict("records"):
        symbol = text_display(item.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        market = text_display(item.get("market")).lower()
        entry = safe_float(item.get("entry"))
        stop = safe_float(item.get("stop"))
        target = safe_float(item.get("target_price"))
        target_pct = safe_float(item.get("target_pct") or item.get("recommended_target_pct"))
        risk_pct = safe_float(item.get("risk_pct"))
        if target is None and entry is not None and target_pct is not None:
            target = entry * (1.0 + target_pct)
        ready: list[str] = []
        missing: list[str] = []

        if market == "crypto" or "/" in symbol:
            missing.append("Solo acciones paper")
        else:
            ready.append("Accion soportada")
        if opportunity_is_trade_ready(item):
            ready.append("Setup confirmado")
        else:
            missing.append("15m/1h BUY")
        if entry is not None:
            ready.append("Entrada")
        else:
            missing.append("Entrada")
        if stop is not None:
            ready.append("Stop")
        else:
            missing.append("Stop")
        if target is not None:
            ready.append("Target")
        else:
            missing.append("Target")
        if entry is not None and stop is not None and abs(entry - stop) > 0:
            ready.append("Riesgo medible")
        elif entry is not None and stop is not None:
            missing.append("Stop separado")
        if risk_pct is None:
            missing.append("Riesgo %")
        elif risk_pct <= 0.035:
            ready.append("Riesgo OK")
        else:
            missing.append("Riesgo <= 3.5%")
        if target_pct is None:
            missing.append("Target %")
        elif target_pct >= 0.02:
            ready.append("Target 2%")
        else:
            missing.append("Target >= 2%")

        if not missing:
            continue
        status = "Falta " + missing[0]
        tone = "avoid" if missing[0] in {"Solo acciones paper", "Riesgo <= 3.5%", "Stop separado"} else "watch"
        rows.append(
            {
                "symbol": symbol,
                "status": status,
                "ready": " · ".join(ready[:6]) or "-",
                "missing": " · ".join(dict.fromkeys(missing[:5])) or "-",
                "next_step": text_display(item.get("cambia_si") or opportunity_change_label(item)),
                "tone": tone,
            }
        )
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows, columns=columns)


def alpaca_paper_execution_summary(
    table: pd.DataFrame,
    *,
    account_equity: float = 500.0,
    risk_pct: float = 0.01,
) -> dict[str, Any]:
    candidates = alpaca_paper_order_candidates(table, account_equity=account_equity, risk_pct=risk_pct, limit=50)
    gaps = alpaca_paper_execution_gaps(table, limit=50)
    risk_budget = max(0.0, safe_float(account_equity) or 0.0) * max(0.0, safe_float(risk_pct) or 0.0)
    projected_risk = float(candidates["risk_dollars"].sum()) if not candidates.empty and "risk_dollars" in candidates.columns else 0.0
    projected_notional = float(candidates["notional"].sum()) if not candidates.empty and "notional" in candidates.columns else 0.0
    top_symbol = text_display(candidates.iloc[0].get("symbol")) if not candidates.empty else text_display(gaps.iloc[0].get("symbol")) if not gaps.empty else "-"
    return {
        "ready": len(candidates),
        "blocked": len(gaps),
        "risk_budget": round(risk_budget, 2),
        "projected_risk": round(projected_risk, 2),
        "projected_notional": round(projected_notional, 2),
        "risk_usage_pct": round((projected_risk / risk_budget) * 100, 1) if risk_budget > 0 else 0.0,
        "top_symbol": top_symbol,
    }


def render_alpaca_paper_execution_summary(summary: dict[str, Any]) -> str:
    return (
        '<div class="paper-exec-summary">'
        f'<b><span>Listas</span><strong>{int(summary.get("ready") or 0)}</strong></b>'
        f'<b><span>Bloqueadas</span><strong>{int(summary.get("blocked") or 0)}</strong></b>'
        f'<b><span>Riesgo usado</span><strong>{html.escape(num_display(summary.get("projected_risk"), 2))}</strong></b>'
        f'<b><span>Presupuesto</span><strong>{html.escape(num_display(summary.get("risk_budget"), 2))}</strong></b>'
        f'<b><span>Uso</span><strong>{html.escape(num_display(summary.get("risk_usage_pct"), 1))}%</strong></b>'
        f'<b><span>Top</span><strong>{html.escape(text_display(summary.get("top_symbol")))}</strong></b>'
        "</div>"
    )


def submit_alpaca_paper_bracket_order(
    candidate: dict[str, Any],
    env: dict[str, str] | None = None,
    client_factory: Any | None = None,
) -> dict[str, Any]:
    source = env if env is not None else os.environ
    gate = alpaca_operations_gate(source)
    if not gate.get("paper_orders_allowed"):
        return {"submitted": False, "status": "blocked", "detail": text_display(gate.get("next"))}
    symbol = text_display(candidate.get("symbol")).upper()
    qty = int(safe_float(candidate.get("qty")) or 0)
    stop = safe_float(candidate.get("stop"))
    take_profit = safe_float(candidate.get("take_profit"))
    if not symbol or symbol == "-" or qty <= 0 or stop is None or take_profit is None:
        return {"submitted": False, "status": "invalid", "detail": "Candidato paper incompleto."}
    key = str(source.get("ALPACA_API_KEY") or "").strip()
    secret = str(source.get("ALPACA_API_SECRET") or source.get("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        return {"submitted": False, "status": "missing_credentials", "detail": "Faltan credenciales paper en entorno."}
    try:
        if client_factory is None:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
            from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest

            def client_factory(api_key: str, secret_key: str):
                return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)

            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=round(take_profit, 2)),
                stop_loss=StopLossRequest(stop_price=round(stop, 2)),
            )
        else:
            order_data = {
                "symbol": symbol,
                "qty": qty,
                "side": "buy",
                "time_in_force": "day",
                "order_class": "bracket",
                "take_profit": round(take_profit, 2),
                "stop_loss": round(stop, 2),
            }
        client = client_factory(key, secret)
        order = client.submit_order(order_data=order_data)
    except Exception as exc:
        return {"submitted": False, "status": "error", "detail": f"Alpaca paper rechazo la orden: {type(exc).__name__}."}
    order_id = getattr(order, "id", None) if not isinstance(order, dict) else order.get("id")
    return {
        "submitted": True,
        "status": "submitted",
        "symbol": symbol,
        "qty": qty,
        "order_id": text_display(order_id),
        "detail": "Orden bracket enviada a Alpaca paper.",
    }


def render_alpaca_paper_execution_panel(
    table: pd.DataFrame,
    *,
    account_equity: float,
    risk_pct: float,
    env: dict[str, str] | None = None,
) -> None:
    candidates = alpaca_paper_order_candidates(table, account_equity=account_equity, risk_pct=risk_pct, limit=3)
    summary_html = render_alpaca_paper_execution_summary(
        alpaca_paper_execution_summary(table, account_equity=account_equity, risk_pct=risk_pct)
    )
    if candidates.empty:
        gaps = alpaca_paper_execution_gaps(table, limit=4)
        checklist = alpaca_paper_gap_checklist(table, limit=4)
        if gaps.empty and checklist.empty:
            return
        cards = [
            f'<section class="paper-gap-card"><header><strong>{html.escape(text_display(row.get("symbol")))}</strong><span>{html.escape(text_display(row.get("status")))}</span></header>'
            f'<div><b>Entry {html.escape(num_display(row.get("entry"), 2))}</b><b>Stop {html.escape(num_display(row.get("stop"), 2))}</b><b>TP {html.escape(num_display(row.get("take_profit"), 2))}</b></div>'
            f'<p>{html.escape(text_display(row.get("next_step")))}</p></section>'
            for row in gaps.to_dict("records")
        ]
        checklist_cards = [
            f'<section class="paper-check-card paper-check-{html.escape(text_display(row.get("tone")))}"><header><strong>{html.escape(text_display(row.get("symbol")))}</strong><span>{html.escape(text_display(row.get("status")))}</span></header>'
            f'<div><b>Listo</b><p>{html.escape(text_display(row.get("ready")))}</p></div>'
            f'<div><b>Falta</b><p>{html.escape(text_display(row.get("missing")))}</p></div>'
            f'<small>{html.escape(text_display(row.get("next_step")))}</small></section>'
            for row in checklist.to_dict("records")
        ]
        st.markdown(
            '<section class="paper-exec-panel paper-exec-muted"><header><strong>Paper Execution Gate</strong><span>Sin orden lista · Roxy muestra que falta antes de enviar a Alpaca paper.</span></header><div class="paper-exec-grid">'
            + summary_html
            + "".join(cards)
            + "".join(checklist_cards)
            + "</div></section>",
            unsafe_allow_html=True,
        )
        return
    auto_enabled = alpaca_paper_autotrade_enabled(env)
    cards = []
    for row in candidates.to_dict("records"):
        key = f"alpaca_paper_sent_{text_display(row.get('symbol'))}_{num_display(row.get('entry'), 2)}"
        status_line = "Auto paper armado" if auto_enabled else "Paper listo / auto OFF"
        if auto_enabled and key not in st.session_state:
            result = submit_alpaca_paper_bracket_order(row, env=env)
            st.session_state[key] = result
        result = st.session_state.get(key)
        if isinstance(result, dict):
            status_line = text_display(result.get("detail"))
        cards.append(
            f'<section class="paper-exec-card">'
            f'<header><strong>{html.escape(text_display(row.get("symbol")))}</strong><span>{html.escape(status_line)}</span></header>'
            f'<div><b>Qty {int(row.get("qty") or 0)}</b><b>Entry {html.escape(num_display(row.get("entry"), 2))}</b><b>Stop {html.escape(num_display(row.get("stop"), 2))}</b><b>TP {html.escape(num_display(row.get("take_profit"), 2))}</b></div>'
            f'<p>Riesgo {html.escape(num_display(row.get("risk_dollars"), 2))} · Notional {html.escape(num_display(row.get("notional"), 2))} · {html.escape(text_display(row.get("reason")))}</p>'
            "</section>"
        )
    state_label = "AUTO ON" if auto_enabled else "AUTO OFF"
    st.markdown(
        f'<section class="paper-exec-panel"><header><strong>Alpaca Paper Execution Queue</strong><span>{html.escape(state_label)} · Solo paper bracket orders: market + take profit + stop.</span></header><div class="paper-exec-grid">'
        + summary_html
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )


def render_live_provider_center(env: dict[str, str] | None = None) -> None:
    rows = live_provider_rows(env)
    cards = []
    for row in rows:
        tone = text_display(row.get("tone"))
        cards.append(
            f'<section class="provider-card provider-card-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("provider")))}</strong><span>{html.escape(text_display(row.get("status")))}</span></header>'
            f'<div><b>{html.escape(text_display(row.get("mode")))}</b><em>{html.escape(text_display(row.get("latency")))}</em></div>'
            f'<p>{html.escape(text_display(row.get("role")))}</p>'
            f'<small>{html.escape(text_display(row.get("next")))}</small>'
            f'<i>Faltan: {html.escape(text_display(row.get("missing")))}</i>'
            "</section>"
        )
    st.markdown(
        '<section class="provider-center"><header><strong>Live Provider Center</strong><span>Preparacion para datos live/paper sin activar trading real.</span></header>'
        + render_alpaca_operations_gate(env)
        + render_alpaca_paper_account_panel(env)
        + '<div class="provider-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )




def broker_simulation_rows() -> list[dict[str, str]]:
    return [
        {
            "name": "Robinhood",
            "mode": "Futuro broker",
            "assets": "Stocks · ETFs · Options · Crypto",
            "status": "Simulación solamente",
            "next": "Preparar OAuth/admin gate; sin órdenes reales.",
            "tone": "watch",
        },
        {
            "name": "Alpaca Paper",
            "mode": "Paper trading",
            "assets": "Stocks · ETFs",
            "status": "Analysis + forward-test",
            "next": "Usar para medir estrategias antes de live.",
            "tone": "buy",
        },
        {
            "name": "Alpaca Live",
            "mode": "Futuro live",
            "assets": "Stocks · ETFs",
            "status": "Bloqueado por admin",
            "next": "Solo habilitable luego desde settings admin.",
            "tone": "avoid",
        },
        {
            "name": "Interactive Brokers",
            "mode": "Futuro broker",
            "assets": "Global stocks · Options",
            "status": "Arquitectura preparada",
            "next": "Adapter preview-only antes de ejecución.",
            "tone": "watch",
        },
        {
            "name": "Binance/Coinbase",
            "mode": "Futuro crypto",
            "assets": "Crypto spot",
            "status": "Simulación solamente",
            "next": "Alertas y paper ledger antes de llaves live.",
            "tone": "watch",
        },
        {
            "name": "TradingView",
            "mode": "Chart bridge",
            "assets": "Charts · Webhooks",
            "status": "Futuro análisis",
            "next": "Recibir señales; no ejecutar desde webhook.",
            "tone": "watch",
        },
    ]


def render_broker_simulation_hub(table: pd.DataFrame, *, account_equity: float, risk_pct: float) -> None:
    equity = max(0.0, safe_float(account_equity) or 0.0)
    risk_fraction = max(0.0, safe_float(risk_pct) or 0.0)
    risk_budget = equity * risk_fraction
    rows = table.head(6).to_dict("records") if not table.empty else []
    ready_count = sum(1 for row in rows if opportunity_is_trade_ready(row))
    watch_count = max(0, len(rows) - ready_count)
    broker_cards = []
    for broker in broker_simulation_rows():
        tone = broker["tone"] if broker["tone"] in {"buy", "watch", "avoid"} else "watch"
        broker_cards.append(
            f'<article class="broker-sim-card broker-sim-{html.escape(tone)}">'
            f'<header><strong>{html.escape(broker["name"])}</strong><span>{html.escape(broker["mode"])}</span></header>'
            f'<p>{html.escape(broker["assets"])}</p>'
            f'<b>{html.escape(broker["status"])}</b>'
            f'<small>{html.escape(broker["next"])}</small>'
            "</article>"
        )
    feature_cards = [
        ("Portfolio Dashboard", f"Capital ${equity:,.0f}", "Equity simulado, riesgo abierto y P&L paper."),
        ("Asset Search Engine", "AAPL · TSLA · BTC", "Busca acción, ETF o crypto y abre la vista de activo."),
        ("Real-Time Charts", "1m–1M", "Velas interactivas con zoom, hover y fallback visible."),
        ("Technical Indicators", "RSI · MACD · EMA · BB", "Indicadores usados para tendencia y confirmación."),
        ("Signal Overlay", "Buy · Sell · Wait", "Entrada, stop, target y zonas pintadas en gráfica."),
        ("Risk Calculator", f"1R ${risk_budget:,.2f}", "Tamaño de posición según capital y stop."),
        ("Opportunity Scanner", f"{len(table)} setups", "Filtra por riesgo, readiness, volumen y setup."),
        ("Watchlist + Alerts", f"{watch_count} vigilancia", "Lista priorizada y centro de alertas educativas."),
        ("Voice Commands", "Global", "Comandos: resumen mercado, analiza activo, lee señal."),
        ("Trade Simulator", "Paper only", "Ensaya entradas/salidas; live trading OFF."),
        ("Portfolio Analytics", f"{ready_count} listas", "Win rate, estrategia, drawdown y retorno paper."),
        ("Admin Live Gate", "Disabled", "Trading real solo futuro desde settings admin."),
    ]
    feature_html = "".join(
        f'<div><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong><p>{html.escape(detail)}</p></div>'
        for label, value, detail in feature_cards
    )
    st.markdown(
        '<section class="broker-sim-hub">'
        '<header><div><strong>Roxy Trader Simulation Hub</strong>'
        '<span>Robinhood · Alpaca Paper · future brokers · live trading disabled</span></div>'
        '<em>Analysis + simulation mode only</em></header>'
        f'<div class="broker-sim-grid">{"".join(broker_cards)}</div>'
        f'<div class="broker-feature-grid">{feature_html}</div>'
        '</section>',
        unsafe_allow_html=True,
    )

def render_platform_logo_strip() -> None:
    badges = platform_badge_rows()
    if not badges:
        return
    badge_html = []
    for row in badges:
        tone = row["tone"] if row["tone"] in {"buy", "watch", "avoid"} else "neutral"
        badge_html.append(
            (
                f'<div class="platform-badge platform-badge-{tone}">'
                f'<div class="platform-mark" style="border-color:{html.escape(row["accent"])};color:{html.escape(row["accent"])}">'
                f'{html.escape(row["abbr"])}</div>'
                '<div class="platform-copy">'
                f'<div class="platform-name">{html.escape(row["name"])}</div>'
                f'<div class="platform-meta">{html.escape(row["asset"])} · {html.escape(row["mode"])}</div>'
                '</div></div>'
            )
        )
    st.markdown(
        f'<div class="platform-strip" aria-label="Plataformas">{"".join(badge_html)}</div>',
        unsafe_allow_html=True,
    )


def study_guides_with_lab(lab_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    lab_by_strategy = {str(row.get("strategy_family")): row for row in lab_rows or []}
    guides: list[dict[str, Any]] = []
    for strategy in CORE_STRATEGIES:
        guide = dict(STRATEGY_STUDY_GUIDES.get(strategy, {}))
        lab = lab_by_strategy.get(strategy, {})
        guides.append(
            {
                "strategy": strategy,
                "headline": guide.get("headline", "Estudiar la estructura, entrada, riesgo y salida del setup."),
                "works_when": guide.get("works_when", "-"),
                "entry": guide.get("entry", "-"),
                "avoid": guide.get("avoid", "-"),
                "option_note": guide.get("option_note", "-"),
                "practice": guide.get("practice", "-"),
                "requirements": guide.get("requirements", []),
                "requirements_text": guide.get("requirements_text") or " | ".join(guide.get("requirements", []) or []),
                "confirmation_timeframes": guide.get("confirmation_timeframes", []),
                "direction": guide.get("direction", "-"),
                "lab_state": lab.get("lab_state", "Collect data"),
                "evidence_score": lab.get("evidence_score"),
                "memory_bias": lab.get("memory_bias"),
                "adaptive_weight": lab.get("adaptive_weight"),
                "backtest_win_rate": lab.get("backtest_win_rate"),
                "backtest_profit_factor": lab.get("backtest_profit_factor"),
                "lab_decision": lab.get("lab_decision"),
                "experiment_rule": lab.get("experiment_rule"),
            }
        )
    return guides


def render_strategy_study_preview(strategy: str, lab_row: dict[str, Any] | None = None) -> None:
    guide = STRATEGY_STUDY_GUIDES.get(strategy)
    if not guide:
        st.info("No hay guia de estudio para esta estrategia todavia.")
        return
    lab_row = lab_row or {}
    lab_state = text_display(lab_row.get("lab_state"))
    evidence = safe_float(lab_row.get("evidence_score"))
    st.markdown(
        f"""
        <div class="study-hero study-hero-watch">
            <div>
                <div class="study-kicker">Estudio desde Roxy Lab</div>
                <h2>{html.escape(strategy)}</h2>
                <p>{html.escape(text_display(guide.get("headline")))}</p>
            </div>
            <div class="study-status">
                <span>Lab</span>
                <strong>{html.escape(lab_state)}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    with cols[0]:
        render_kpi_card("Evidencia", pct_display(evidence), tone="buy" if evidence and evidence >= 0.65 else "watch")
    with cols[1]:
        render_kpi_card("Entrada", guide.get("entry"), tone="watch")
    with cols[2]:
        render_kpi_card("No operar si", guide.get("avoid"), tone="avoid")
    with cols[3]:
        render_kpi_card("Practica", guide.get("practice"))
    rule = text_display(lab_row.get("experiment_rule") or lab_row.get("lab_decision"))
    if rule != "-":
        st.caption(rule)


def study_example_rows(confluence_df: pd.DataFrame, brief: dict, strategy: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in brief.get("opportunities", []):
        row_dict = dict(row)
        family = strategy_family_for_row(row_dict)
        if family == strategy:
            row_dict["strategy_family"] = family
            row_dict["source"] = "brief"
            rows.append(row_dict)
    if not confluence_df.empty:
        for _, item in confluence_df.head(200).iterrows():
            row_dict = item.to_dict()
            family = strategy_family_for_row(row_dict)
            if family == strategy:
                row_dict["strategy_family"] = family
                row_dict["source"] = "confluencia"
                rows.append(row_dict)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "confluence_score" in df.columns:
        df["sort_score"] = pd.to_numeric(df["confluence_score"], errors="coerce").fillna(0)
    elif "ai_score" in df.columns:
        df["sort_score"] = pd.to_numeric(df["ai_score"], errors="coerce").fillna(0)
    else:
        df["sort_score"] = 0
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.sort_values("sort_score", ascending=False).drop_duplicates(subset=["symbol"], keep="first")


def render_roxy_brand_header(
    *,
    scan_df: pd.DataFrame,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    daily_path: str | None,
    live_path: str | None,
    confluence_path: str | None,
    options_path: str | None,
    brief: dict,
) -> None:
    state = live_service_state()
    freshness = data_freshness_status([live_path, confluence_path], max_age_minutes=10.0)
    session = brief.get("market_session") or market_session_status()
    table = focused_opportunity_table(brief)
    best = table.iloc[0].to_dict() if not table.empty else {}
    best_symbol = text_display(best.get("symbol"))
    best_action = human_trade_action(best) if best else "Esperar"
    best_detail = text_display(best.get("waiting_for") or best.get("por_que"))
    source_time = latest_timestamp([daily_path, live_path, confluence_path, options_path])
    service_label = "Activo" if state.get("loaded") == "yes" else "Pausado"
    service_tone = "buy" if state.get("loaded") == "yes" else "watch"
    data_tone = freshness.get("tone", "watch")
    session_text = text_display(session.get("stock_session"))

    def chip(label: str, value: Any, tone: str = "neutral") -> str:
        tone = tone if tone in {"buy", "watch", "avoid", "neutral"} else "neutral"
        return (
            f'<div class="hero-chip hero-chip-{tone}">'
            f'<span>{html.escape(label)}</span><strong>{html.escape(text_display(value))}</strong>'
            f"</div>"
        )

    hero_html = (
        '<section class="roxy-hero">'
        '<div class="roxy-hero-left">'
        '<div class="roxy-brand-row">'
        f'{brand_logo_html()}'
        '<div><h1>Roxy Trading</h1>'
        '<p>Scanner profesional · SMA 20/40/100/200 · saltos · alertas IA 24h</p></div>'
        '</div>'
        '<div class="hero-flow">'
        '<div class="flow-step"><span>1</span>Detecta setup</div>'
        '<div class="flow-step"><span>2</span>Valida 1h + 15m</div>'
        '<div class="flow-step"><span>3</span>Plan de riesgo</div>'
        '<div class="flow-step"><span>4</span>Ticket manual</div>'
        '<div class="flow-step"><span>5</span>Memoria IA</div>'
        '</div></div>'
        '<div class="roxy-hero-right">'
        f'{chip("24h", service_label, service_tone)}'
        f'{chip("Datos", freshness.get("label"), data_tone)}'
        f'{chip("Sesion", session_text, "buy" if session.get("stock_alerts_allowed") else "watch")}'
        f'{chip("Top", f"{best_symbol} · {best_action}", signal_tone(best.get("signal", "")) if best else "watch")}'
        '</div></section>'
        '<div class="hero-subline">'
        f'<span>Ultima lectura: {html.escape(source_time)}</span>'
        f'<span>{html.escape(best_detail[:180])}</span>'
        '</div>'
    )
    st.markdown(hero_html, unsafe_allow_html=True)
    render_platform_logo_strip()



def notification_channel_display(rows: list[dict] | pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if "channel" in df.columns:
        df["channel"] = df["channel"].map(lambda value: NOTIFICATION_CHANNEL_LABELS.get(str(value), text_display(value)))
    if "configured" in df.columns:
        df["status"] = df["configured"].map(lambda value: "Listo" if value else "Falta configurar")
    if "notes" in df.columns:
        df["notes"] = df["notes"].map(lambda value: NOTIFICATION_NOTE_LABELS.get(str(value), text_display(value)))
    cols = [col for col in ["channel", "status", "requirements", "notes"] if col in df.columns]
    return df[cols].rename(
        columns={
            "channel": "Canal",
            "status": "Estado",
            "requirements": "Requisitos",
            "notes": "Notas",
        }
    )


def valid_lan_ip(value: Any) -> bool:
    text = str(value or "").strip()
    if not text or ":" in text:
        return False
    if text.startswith(("127.", "169.254.", "0.")):
        return False
    parts = text.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def local_ip_candidates() -> list[str]:
    candidates: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if valid_lan_ip(text) and text not in candidates:
            candidates.append(text)

    for iface in ["en0", "en1", "en2", "bridge100"]:
        try:
            result = subprocess.run(["ipconfig", "getifaddr", iface], text=True, capture_output=True, timeout=1.5, check=False)
            add(result.stdout)
        except Exception:
            pass
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            add(item[4][0])
    except Exception:
        pass
    return candidates


def build_mobile_access_rows(
    *,
    local_ips: list[str],
    port: int | None,
    lan_ready: bool,
    public_url: str | None = None,
) -> list[dict[str, str]]:
    rows = []
    for ip in local_ips:
        rows.append(
            {
                "modo": "Misma Wi-Fi",
                "url": f"http://{ip}:{int(port or 8501)}",
                "estado": "Listo" if lan_ready else "Requiere abrir Streamlit en 0.0.0.0",
                "uso": "Telefono/tablet conectado a la misma red que la Mac.",
            }
        )
    if public_url:
        rows.append(
            {
                "modo": "Fuera de casa",
                "url": public_url,
                "estado": "Configurar seguridad",
                "uso": "Usar solo con tunel/VPN seguro y autenticacion.",
            }
        )
    elif not rows:
        rows.append(
            {
                "modo": "Pendiente",
                "url": "-",
                "estado": "No se detecto IP local",
                "uso": "Conecta la Mac a Wi-Fi o Ethernet y vuelve a revisar.",
            }
        )
    return rows


def mobile_access_status() -> dict[str, Any]:
    try:
        from tools import streamlit_launchd

        launchd_status = streamlit_launchd.status()
    except Exception as exc:
        launchd_status = {
            "installed": False,
            "loaded": False,
            "address": "-",
            "port": 8501,
            "lan_ready": False,
            "error": str(exc),
        }
    port = safe_float(launchd_status.get("port")) or 8501
    public_url = text_display(st.session_state.get("roxy_public_url"))
    if public_url == "-":
        public_url = ""
    local_ips = local_ip_candidates()
    rows = build_mobile_access_rows(
        local_ips=local_ips,
        port=int(port),
        lan_ready=bool(launchd_status.get("lan_ready")),
        public_url=public_url,
    )
    return {
        "launchd": launchd_status,
        "local_ips": local_ips,
        "public_url": public_url,
        "rows": rows,
        "port": int(port),
    }


def safe_float(value) -> float | None:
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


def platform_status_label(status: Any) -> str:
    raw = str(status or "-").upper()
    return PLATFORM_STATUS_LABELS.get(raw, text_display(status))


def platform_reason_label(reason: Any) -> str:
    raw = text_display(reason)
    if raw in PLATFORM_REASON_LABELS:
        return PLATFORM_REASON_LABELS[raw]
    if raw.startswith("Stocks/options are in "):
        session = raw.split("Stocks/options are in ", 1)[1].split(";", 1)[0]
        return f"Acciones/opciones estan en {session}. Usa Roxy para estudio hasta que reabra la sesion."
    return raw


def asset_type_label(asset_type: Any) -> str:
    raw = str(asset_type or "-").lower()
    return ASSET_TYPE_LABELS.get(raw, text_display(asset_type))


def action_label(action: Any) -> str:
    raw = str(action or "-").upper()
    return ACTION_LABELS.get(raw, text_display(action))


def connection_mode_label(mode: Any) -> str:
    raw = str(mode or "-").upper()
    return CONNECTION_MODE_LABELS.get(raw, text_display(mode))


def adapter_status_label(status: Any) -> str:
    raw = str(status or "-").upper()
    return ADAPTER_STATUS_LABELS.get(raw, text_display(status))


def execution_blocker_label(blocker: Any) -> str:
    raw = text_display(blocker)
    if raw in EXECUTION_BLOCKER_LABELS:
        return EXECUTION_BLOCKER_LABELS[raw]
    if raw.endswith("=1 is not set."):
        return "La ejecucion real sigue apagada por seguridad."
    if raw.startswith("Roxy status is "):
        status = raw.split("Roxy status is ", 1)[1].split(";", 1)[0]
        return f"Estado Roxy: {platform_status_label(status)}. Solo se puede armar cuando esta Listo para preparar."
    return raw


def center_decision_summary(row: dict) -> dict[str, str]:
    signal = str(row.get("signal") or "").upper()
    decision = str(row.get("decision") or row.get("trade_decision") or "").upper()
    action = str(row.get("action") or row.get("ai_action") or "").upper()
    if opportunity_is_trade_ready(row):
        status = "Operar"
        tone = "buy"
        headline = "Hay setup accionable, pero la orden sigue manual."
    elif signal == "AVOID" or decision.startswith("NO_TRADE"):
        status = "No operar"
        tone = "avoid"
        headline = "Roxy bloquea la operacion hasta que cambie la estructura."
    else:
        status = "Esperar"
        tone = "watch"
        headline = "Roxy esta esperando el gatillo exacto antes de entrar."
    return {
        "status": status,
        "tone": tone,
        "headline": human_alert_reason(row) or headline,
        "action": human_trade_action(row) if action or signal or decision else action_label(action or signal),
        "why": human_alert_reason(row),
        "wait_for": watch_movement_label(row),
        "changes_when": opportunity_change_label(row),
    }


def compound_steps_required(starting_capital: float, target_capital: float, net_gain_pct: float) -> int | None:
    try:
        start = float(starting_capital)
        target = float(target_capital)
        gain = float(net_gain_pct)
    except (TypeError, ValueError):
        return None
    if start <= 0 or target <= start or gain <= 0:
        return 0
    return int(math.ceil(math.log(target / start) / math.log(1.0 + gain)))


def capital_growth_phase(equity: float) -> tuple[str, str, str]:
    if equity < 1_000:
        return (
            "Proteccion",
            "Fractional shares/crypto pequeno; opciones solo paper o debit muy bajo.",
            "La meta es sobrevivir y medir setups, no forzar trades.",
        )
    if equity < 5_000:
        return (
            "Base",
            "Acciones fraccionadas y calls/puts solo si max loss cabe en riesgo.",
            "Solo operar 1h + 15m confirmados; evitar revenge trades.",
        )
    if equity < 25_000:
        return (
            "Consistencia",
            "Acciones liquidas, opciones con DTE y spread controlado.",
            "Subir tamano solo despues de 20 senales cerradas con edge positivo.",
        )
    if equity < 100_000:
        return (
            "Escala controlada",
            "Acciones + opciones liquidas; evitar concentracion.",
            "Bajar riesgo despues de rachas negativas y proteger ganancias.",
        )
    if equity < 500_000:
        return (
            "Profesional",
            "Portafolio de setups, no una sola apuesta.",
            "Roxy prioriza drawdown bajo antes que crecimiento agresivo.",
        )
    return (
        "Preservacion",
        "Menos riesgo por trade, mas filtros y menos ruido.",
        "El objetivo cambia de crecer rapido a no devolver capital.",
    )


def build_million_growth_plan(
    starting_capital: float = 500.0,
    target_capital: float = 1_000_000.0,
    risk_per_trade_pct: float = 0.01,
) -> dict:
    start = max(1.0, float(starting_capital or 500.0))
    target = max(start, float(target_capital or 1_000_000.0))
    risk_pct = max(0.001, float(risk_per_trade_pct or 0.01))
    milestone_values = [500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000]
    milestone_values = sorted({float(value) for value in milestone_values if value >= start} | {target})

    previous = start
    rows = []
    for idx, milestone in enumerate(milestone_values, start=1):
        phase, products, rule = capital_growth_phase(previous)
        rows.append(
            {
                "stage": idx,
                "phase": phase,
                "from": previous,
                "target": milestone,
                "risk_per_trade": previous * risk_pct,
                "daily_stop": previous * risk_pct * 2.0,
                "trades_2pct": compound_steps_required(previous, milestone, 0.02),
                "trades_5pct": compound_steps_required(previous, milestone, 0.05),
                "trades_10pct": compound_steps_required(previous, milestone, 0.10),
                "products": products,
                "rule": rule,
            }
        )
        previous = milestone

    return {
        "starting_capital": start,
        "target_capital": target,
        "multiplier": target / start,
        "risk_per_trade_pct": risk_pct,
        "risk_per_trade": start * risk_pct,
        "daily_stop": start * risk_pct * 2.0,
        "max_option_debit": start * risk_pct,
        "guardrail": build_account_risk_guardrail(start, risk_pct),
        "steps_to_target": {
            "2%": compound_steps_required(start, target, 0.02),
            "5%": compound_steps_required(start, target, 0.05),
            "10%": compound_steps_required(start, target, 0.10),
        },
        "milestones": rows,
        "rules": [
            "No operar si Roxy no marca Operar o una alerta BUY con riesgo y target validos.",
            "Riesgo base 0.5% a 1% por trade; con $500, 1% son $5.",
            "Maximo 2R de perdida diaria; despues de eso Roxy debe pasar a modo esperar.",
            "Opciones solo si el max loss del contrato cabe en el riesgo definido; si no, mirar accion fraccionada o paper.",
            "Subir tamano solo cuando la memoria muestre que el setup llega a 2% mas veces de las que toca stop.",
            "Nunca promediar perdedor; el stop invalida la idea.",
        ],
    }


def build_account_risk_guardrail(
    account_equity: float = 500.0,
    risk_per_trade_pct: float = 0.01,
    *,
    planned_risk_dollars: float | None = None,
    realized_loss_today: float = 0.0,
    open_risk_dollars: float = 0.0,
) -> dict:
    equity = max(1.0, float(account_equity or 500.0))
    risk_pct = max(0.001, float(risk_per_trade_pct or 0.01))
    per_trade_budget = equity * risk_pct
    daily_stop = per_trade_budget * 2.0
    planned_risk = safe_float(planned_risk_dollars)
    if planned_risk is None:
        planned_risk = per_trade_budget
    used_risk = max(0.0, float(realized_loss_today or 0.0)) + max(0.0, float(open_risk_dollars or 0.0))
    remaining_daily_risk = max(0.0, daily_stop - used_risk)

    if used_risk >= daily_stop:
        status = "DAILY_STOP"
        allowed = False
        message = "Modo proteger capital: ya se alcanzo el stop diario 2R."
    elif planned_risk > per_trade_budget:
        status = "REDUCE_SIZE"
        allowed = False
        message = "Reducir tamano: el riesgo planeado supera el presupuesto por trade."
    elif planned_risk > remaining_daily_risk:
        status = "REDUCE_SIZE"
        allowed = False
        message = "Reducir tamano: no queda suficiente riesgo diario disponible."
    else:
        status = "OK"
        allowed = True
        message = "Riesgo permitido dentro del plan 1R por trade y 2R diario."

    return {
        "status": status,
        "allowed": allowed,
        "account_equity": equity,
        "risk_per_trade_pct": risk_pct,
        "per_trade_budget": per_trade_budget,
        "daily_stop": daily_stop,
        "used_risk": used_risk,
        "remaining_daily_risk": remaining_daily_risk,
        "planned_risk": planned_risk,
        "message": message,
    }


def small_account_product_plan(
    *,
    account_equity: float = 500.0,
    risk_per_trade_pct: float = 0.01,
    market: str = "stock",
    entry: float | None = None,
    stop: float | None = None,
    option: dict | None = None,
) -> dict:
    equity = max(1.0, float(account_equity or 500.0))
    risk_pct = max(0.001, float(risk_per_trade_pct or 0.01))
    risk_budget = equity * risk_pct
    entry_value = safe_float(entry)
    stop_value = safe_float(stop)
    market_value = str(market or "stock").lower()
    option = option or {}
    option_max_loss = safe_float(option.get("max_loss_per_contract"))
    option_contract = text_display(option.get("contractSymbol") or option.get("contract"))

    if entry_value is None or entry_value <= 0:
        return {
            "recommendation": "Solo paper",
            "allowed": False,
            "risk_budget": risk_budget,
            "message": "Falta precio de entrada para calcular tamano.",
            "next_step": "Esperar plan con entrada y stop.",
        }

    risk_per_unit = None
    if stop_value is not None and stop_value > 0 and stop_value < entry_value:
        risk_per_unit = entry_value - stop_value

    if market_value == "crypto":
        if risk_per_unit is None:
            units = risk_budget / entry_value
            return {
                "recommendation": "Crypto pequeno",
                "allowed": True,
                "risk_budget": risk_budget,
                "risk_per_unit": None,
                "units": units,
                "message": "Crypto permite tamano fraccionado, pero falta stop valido; usar posicion pequena.",
                "next_step": "Definir stop antes de operar.",
            }
        units = risk_budget / risk_per_unit
        return {
            "recommendation": "Crypto pequeno",
            "allowed": True,
            "risk_budget": risk_budget,
            "risk_per_unit": risk_per_unit,
            "units": units,
            "message": f"Tamano crypto calculado para no superar ${risk_budget:.2f} de riesgo.",
            "next_step": "Colocar orden manual solo si el exchange respeta stop y liquidez.",
        }

    option_allowed = option_max_loss is not None and option_max_loss <= risk_budget
    if option_contract != "-" and option_max_loss is not None and not option_allowed:
        option_message = (
            f"Opcion fuera de plan: max loss ${option_max_loss:.2f} supera 1R ${risk_budget:.2f}."
        )
    elif option_contract != "-" and option_allowed:
        option_message = f"Opcion permitida por riesgo: max loss ${option_max_loss:.2f} cabe en 1R ${risk_budget:.2f}."
    else:
        option_message = "Sin contrato de opcion validado para cuenta pequena."

    if option_contract != "-":
        if option_allowed:
            contracts = max(1, math.floor(risk_budget / max(option_max_loss or risk_budget, 0.01)))
            return {
                "recommendation": "Opcion",
                "allowed": True,
                "risk_budget": risk_budget,
                "risk_per_unit": option_max_loss,
                "units": contracts,
                "whole_shares": contracts,
                "option_allowed": True,
                "option_max_loss": option_max_loss,
                "option_message": option_message,
                "message": f"Contrato permitido por riesgo; max loss cabe en 1R ${risk_budget:.2f}.",
                "next_step": "Confirmar spread, volumen, open interest y DTE antes de entrar.",
            }
        return {
            "recommendation": "Solo paper",
            "allowed": False,
            "risk_budget": risk_budget,
            "risk_per_unit": option_max_loss,
            "units": 0,
            "whole_shares": 0,
            "option_allowed": False,
            "option_max_loss": option_max_loss,
            "option_message": option_message,
            "message": "Contrato fuera del plan de cuenta pequena.",
            "next_step": "Priorizar accion/fraccionada o esperar un contrato con max loss dentro de 1R.",
        }

    if risk_per_unit is None:
        return {
            "recommendation": "Solo paper",
            "allowed": False,
            "risk_budget": risk_budget,
            "option_allowed": option_allowed,
            "option_message": option_message,
            "message": "Falta stop valido; con cuenta pequena no se opera sin invalidacion clara.",
            "next_step": "Esperar stop tecnico y target 2% viable.",
        }

    max_by_risk = risk_budget / risk_per_unit
    max_by_cash = equity / entry_value
    units = min(max_by_risk, max_by_cash)
    whole_shares = math.floor(units)
    if whole_shares >= 1:
        recommendation = "Accion"
        message = f"Puedes usar hasta {whole_shares} accion(es) sin superar ${risk_budget:.2f} de riesgo."
        allowed = True
    elif units > 0:
        recommendation = "Accion fraccionada"
        message = f"Usar fraccion aproximada {units:.4f}; una accion completa supera efectivo o riesgo."
        allowed = True
    else:
        recommendation = "Solo paper"
        message = "El riesgo por accion no cabe en la cuenta; usar paper hasta mejor entrada."
        allowed = False

    if option_contract != "-" and not option_allowed:
        next_step = "Priorizar accion/fraccionada; no comprar esa opcion con cuenta pequena."
    elif option_contract != "-" and option_allowed:
        next_step = "Opcion solo si spread, volumen y DTE tambien pasan el filtro."
    else:
        next_step = "Confirmar entrada manual y respetar stop."

    return {
        "recommendation": recommendation,
        "allowed": allowed,
        "risk_budget": risk_budget,
        "risk_per_unit": risk_per_unit,
        "units": units,
        "whole_shares": whole_shares,
        "option_allowed": option_allowed,
        "option_max_loss": option_max_loss,
        "option_message": option_message,
        "message": message,
        "next_step": next_step,
    }


def setup_risk_pct(setup: dict) -> float | None:
    entry = safe_float(setup.get("entry"))
    stop = safe_float(setup.get("stop"))
    if entry is None or stop is None or entry <= 0 or stop <= 0 or stop >= entry:
        return None
    return (entry - stop) / entry


def signal_tone(value: str) -> str:
    normalized = str(value or "").upper()
    if normalized.startswith("BUY") or normalized.startswith("TRADE_FOR") or normalized.startswith("ENTER"):
        return "buy"
    if normalized.startswith("WATCH") or normalized.startswith("WAIT"):
        return "watch"
    if normalized.startswith("AVOID") or normalized.startswith("NO_"):
        return "avoid"
    return "neutral"


def render_kpi_card(label: str, value, *, tone: str = "neutral", detail: str | None = None) -> None:
    tone = tone if tone in {"neutral", "buy", "watch", "avoid"} else "neutral"
    value_text = html.escape(text_display(value))
    label_text = html.escape(str(label))
    detail_html = ""
    if detail:
        detail_html = f'<div class="symbol-kpi-detail">{html.escape(str(detail))}</div>'
    st.markdown(
        f"""
        <div class="symbol-kpi symbol-kpi-{tone}">
            <div class="symbol-kpi-label">{label_text}</div>
            <div class="symbol-kpi-value">{value_text}</div>
            {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_tone(value: str) -> str:
    normalized = str(value or "").upper()
    if normalized == "ACTIVE":
        return "buy"
    if normalized == "WATCH":
        return "watch"
    if normalized == "BLOCKED":
        return "avoid"
    return signal_tone(normalized)


def render_strategy_checklist(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    st.markdown("**Checklist de estrategias**")
    for start in range(0, len(rows), 3):
        cols = st.columns(3)
        for col, row in zip(cols, rows[start : start + 3]):
            detail = f"{row.get('trigger', '-')}. {row.get('action', '-')}"
            with col:
                render_kpi_card(
                    row.get("family", "-"),
                    row.get("status", "-"),
                    tone=status_tone(row.get("status", "")),
                    detail=detail,
                )
    with st.expander("Por que Roxy clasifica cada estrategia asi"):
        st.dataframe(pd.DataFrame(rows), width="stretch")


def render_chart_readout(
    setup: dict,
    confluence: dict | None,
    brief: dict | None,
    chart_df: pd.DataFrame,
    *,
    market: str | None = None,
    timeframe: str | None = None,
) -> None:
    confluence = confluence or {}
    brief = brief or {}
    market = market or str(brief.get("market") or confluence.get("market") or "stock")
    timeframe = timeframe or str(brief.get("timeframe") or confluence.get("tf") or "1h")
    latest = chart_df.iloc[-1].to_dict() if not chart_df.empty else {}
    close = safe_float(latest.get("close") or setup.get("close") or setup.get("entry"))
    sma20 = safe_float(latest.get("sma20") or setup.get("sma20"))
    sma40 = safe_float(latest.get("sma40") or setup.get("sma40"))
    sma100 = safe_float(latest.get("sma100") or setup.get("sma100"))
    sma200 = safe_float(latest.get("sma200") or setup.get("sma200"))
    rel_vol = safe_float(latest.get("relative_volume") or confluence.get("relative_volume_15m") or setup.get("relative_volume"))
    rsi14 = safe_float(latest.get("rsi14"))
    macd_hist = safe_float(latest.get("macd_hist"))
    risk = safe_float(brief.get("risk_pct")) or setup_risk_pct(setup)
    target = safe_float(brief.get("recommended_target_pct") or confluence.get("recommended_target_pct"))

    has_stack = close is not None and all(value is not None for value in [sma20, sma40, sma100, sma200])
    bullish_stack = bool(has_stack and sma20 > sma40 > sma100 > sma200 and close > sma20)
    bearish_stack = bool(has_stack and sma20 < sma40 < sma100 < sma200 and close < sma200)
    if bullish_stack:
        trend = "Bull channel"
        trend_tone = "buy"
    elif bearish_stack:
        trend = "Bear channel"
        trend_tone = "avoid"
    elif has_stack and close and sma200 and close > sma200:
        trend = "Above SMA200"
        trend_tone = "watch"
    else:
        trend = "No clean trend"
        trend_tone = "neutral"

    volume_state = "Strong" if rel_vol is not None and rel_vol >= 1.1 else "Weak" if rel_vol is not None and rel_vol < 0.8 else "Normal"
    volume_tone = "buy" if volume_state == "Strong" else "avoid" if volume_state == "Weak" else "neutral"
    risk_tone = "buy" if risk is not None and risk <= 0.025 else "avoid" if risk is not None and risk > 0.035 else "watch"
    target_tone = "buy" if target is not None and target >= 0.02 else "watch"
    if rsi14 is None:
        oscillator_state = "Sin datos"
        oscillator_tone = "neutral"
    elif rsi14 >= 75:
        oscillator_state = "Extendido"
        oscillator_tone = "avoid"
    elif rsi14 >= 45 and (macd_hist is None or macd_hist >= 0):
        oscillator_state = "Con espacio"
        oscillator_tone = "buy"
    elif macd_hist is not None and macd_hist < 0:
        oscillator_state = "Debil"
        oscillator_tone = "watch"
    else:
        oscillator_state = "Neutral"
        oscillator_tone = "neutral"

    fresh = chart_freshness_status(chart_df, market=market, timeframe=timeframe)

    st.markdown("**Lectura de grafica**")
    cols = st.columns([1, 1, 1, 1, 1, 1, 1])
    with cols[0]:
        trend = {
            "Bull channel": "Canal alcista",
            "Bear channel": "Canal bajista",
            "Above SMA200": "Sobre SMA200",
            "No clean trend": "Sin tendencia limpia",
        }.get(trend, trend)
        render_kpi_card("Estructura MA", trend, tone=trend_tone, detail="20 / 40 / 100 / 200")
    with cols[1]:
        render_kpi_card("Ultimo precio", num_display(close))
    with cols[2]:
        volume_state = {"Strong": "Fuerte", "Weak": "Debil", "Normal": "Normal"}.get(volume_state, volume_state)
        render_kpi_card("Volumen", volume_state, tone=volume_tone, detail=f"{num_display(rel_vol)}x" if rel_vol is not None else "Sin datos")
    with cols[3]:
        render_kpi_card("Riesgo a stop", pct_display(risk), tone=risk_tone)
    with cols[4]:
        render_kpi_card("Objetivo", pct_display(target), tone=target_tone)
    with cols[5]:
        macd_label = "+" if macd_hist is not None and macd_hist >= 0 else "-" if macd_hist is not None else "-"
        render_kpi_card("Oscilador", oscillator_state, tone=oscillator_tone, detail=f"RSI {num_display(rsi14, 0)} | MACD {macd_label}")
    with cols[6]:
        render_kpi_card("Tiempo real", fresh["label"], tone=fresh["tone"], detail=f"{fresh['detail']} | {fresh['latest']}")


def build_chart_level_plan(
    chart_df: pd.DataFrame,
    setup: dict,
    confluence: dict | None,
    brief: dict | None = None,
) -> list[dict[str, Any]]:
    confluence = confluence or {}
    brief = brief or {}
    latest = chart_df.iloc[-1].to_dict() if not chart_df.empty else {}
    entry = safe_float(brief.get("entry")) or safe_float(confluence.get("entry")) or safe_float(setup.get("entry"))
    stop = safe_float(brief.get("stop")) or safe_float(confluence.get("stop")) or safe_float(setup.get("stop"))
    close = safe_float(latest.get("close") or setup.get("close"))
    rows: list[dict[str, Any]] = []

    def add(level: str, price: Any, role: str, tone: str = "neutral") -> None:
        number = safe_float(price)
        if number is None:
            return
        rows.append({"nivel": level, "precio": number, "uso": role, "tone": tone})

    add("Precio", close, "Referencia actual", "neutral")
    add("Entrada", entry, "Zona valida solo si 15m/1h confirman", "buy")
    add("Stop", stop, "Invalida el trade si lo pierde", "avoid")

    ladder = brief.get("target_ladder") or []
    target_prices = {}
    for item in ladder:
        label = str(item.get("target") or "")
        price = safe_float(item.get("target_price"))
        if label and price is not None:
            target_prices[label] = price
    if entry is not None:
        target_prices.setdefault("2%", entry * 1.02)
        target_prices.setdefault("5%", entry * 1.05)
        target_prices.setdefault("10%", entry * 1.10)
    for label in ["2%", "5%", "10%"]:
        add(f"Objetivo {label}", target_prices.get(label), f"Salida parcial {label}", "buy")

    add("Soporte", latest.get("range_low_60"), "Zona donde debe aparecer rebote", "watch")
    add("Resistencia", latest.get("range_high_60"), "Ruptura valida con volumen", "watch")
    add("SMA20", latest.get("sma20") or setup.get("sma20"), "Media rapida: gatillo/pullback", "neutral")
    add("SMA40", latest.get("sma40") or setup.get("sma40"), "Confirmacion de tendencia corta", "neutral")
    add("SMA100", latest.get("sma100") or setup.get("sma100"), "Soporte medio", "neutral")
    add("SMA200", latest.get("sma200") or setup.get("sma200"), "Filtro principal de tendencia", "neutral")
    return rows


def render_chart_level_plan(chart_df: pd.DataFrame, setup: dict, confluence: dict | None, brief: dict | None = None) -> None:
    rows = build_chart_level_plan(chart_df, setup, confluence, brief)
    if not rows:
        return
    st.markdown("**Plan visual de niveles**")
    primary = [row for row in rows if row["nivel"] in {"Entrada", "Stop", "Objetivo 2%", "Objetivo 5%", "Objetivo 10%"}]
    cols = st.columns(len(primary) or 1)
    for col, row in zip(cols, primary):
        with col:
            render_kpi_card(row["nivel"], num_display(row["precio"]), tone=row["tone"], detail=row["uso"])
    with st.expander("Niveles completos de la grafica"):
        display = pd.DataFrame(rows).drop(columns=["tone"], errors="ignore")
        display["precio"] = display["precio"].map(lambda value: num_display(value))
        st.dataframe(display, width="stretch", hide_index=True)


def chart_zone_band(price: Any, chart_window: pd.DataFrame) -> float:
    reference = safe_float(price)
    if reference is None or reference <= 0:
        reference = safe_float(chart_window["close"].iloc[-1]) if not chart_window.empty and "close" in chart_window.columns else 1.0
    atr_pct = None
    if "atr_pct" in chart_window.columns and chart_window["atr_pct"].notna().any():
        atr_pct = safe_float(chart_window["atr_pct"].dropna().iloc[-1])
    pct = min(0.012, max(0.0025, (atr_pct or 0.006) * 0.35))
    return max(reference * pct, 0.01)


def chart_reference_price(chart_window: pd.DataFrame) -> float | None:
    if chart_window.empty or "close" not in chart_window.columns:
        return None
    close_series = pd.to_numeric(chart_window["close"], errors="coerce").dropna()
    if close_series.empty:
        return None
    reference = safe_float(close_series.iloc[-1])
    return reference if reference and reference > 0 else None


def chart_level_is_near(value: Any, reference: float | None, *, lower: float = 0.60, upper: float = 1.55) -> bool:
    number = safe_float(value)
    if number is None or number <= 0:
        return False
    if reference is None or reference <= 0:
        return True
    return reference * lower <= number <= reference * upper


def prepare_chart_window(chart_df: pd.DataFrame, *, limit: int = 260) -> pd.DataFrame:
    if chart_df.empty:
        return pd.DataFrame()
    window = chart_df.copy()
    if "ts" not in window.columns or "close" not in window.columns:
        return pd.DataFrame()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        window["ts"] = pd.to_datetime(window["ts"], errors="coerce")
    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
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
        "volume_sma20",
        "relative_volume",
        "atr_pct",
    ]
    for column in numeric_columns:
        if column in window.columns:
            window[column] = pd.to_numeric(window[column], errors="coerce")
    window = window.dropna(subset=["ts", "close"]).sort_values("ts").tail(limit).reset_index(drop=True)
    if window.empty:
        return pd.DataFrame()
    for column in ["open", "high", "low"]:
        if column not in window.columns:
            window[column] = window["close"]
    window["open"] = window["open"].fillna(window["close"])
    window["high"] = window["high"].fillna(window[["open", "close"]].max(axis=1))
    window["low"] = window["low"].fillna(window[["open", "close"]].min(axis=1))
    window["high"] = window[["high", "open", "close"]].max(axis=1)
    window["low"] = window[["low", "open", "close"]].min(axis=1)
    return window


def build_chart_level_values(
    chart_window: pd.DataFrame,
    setup: dict,
    confluence: dict | None,
    brief: dict | None = None,
    targets: list[dict[str, Any]] | None = None,
) -> list[float]:
    confluence = confluence or {}
    brief = brief or {}
    reference = chart_reference_price(chart_window)
    values: list[float] = []

    def add(value: Any, *, lower: float = 0.60, upper: float = 1.55) -> None:
        number = safe_float(value)
        if number is not None and math.isfinite(number) and number > 0 and chart_level_is_near(number, reference, lower=lower, upper=upper):
            values.append(number)

    for column in ["open", "close", "ema9", "sma20", "sma40", "sma100", "sma200", "bb_upper", "bb_lower"]:
        if column in chart_window.columns:
            for value in chart_window[column].dropna().tail(90).tolist():
                add(value)
    for column in ["high", "low"]:
        if column in chart_window.columns:
            series = pd.to_numeric(chart_window[column], errors="coerce").dropna().tail(90)
            if not series.empty:
                add(float(series.quantile(0.05)), lower=0.70, upper=1.35)
                add(float(series.quantile(0.95)), lower=0.70, upper=1.35)
    for column in ["range_high_60", "range_low_60"]:
        if column in chart_window.columns:
            for value in chart_window[column].dropna().tail(3).tolist():
                add(value, lower=0.75, upper=1.25)
    for source in [setup, confluence, brief]:
        for key in ["entry", "stop", "tp2", "recommended_target_price", "target_2", "target_5", "target_10"]:
            add(source.get(key), lower=0.55, upper=1.65)
    for item in (targets or []):
        add(item.get("price"), lower=0.55, upper=1.65)
    for item in brief.get("target_ladder", []) if isinstance(brief.get("target_ladder"), list) else []:
        add(item.get("target_price"), lower=0.55, upper=1.65)
    if reference:
        values.append(reference)
    return values


def chart_price_domain(
    chart_window: pd.DataFrame,
    setup: dict,
    confluence: dict | None,
    brief: dict | None = None,
    targets: list[dict[str, Any]] | None = None,
) -> list[float] | None:
    values = build_chart_level_values(chart_window, setup, confluence, brief, targets)
    if not values:
        return None
    series = pd.Series(values, dtype="float64").dropna()
    series = series[(series > 0) & series.map(math.isfinite)]
    if series.empty:
        return None
    low = float(series.quantile(0.01))
    high = float(series.quantile(0.99))
    if high <= low:
        base = high if high > 0 else 1.0
        return [max(0.0, base * 0.97), base * 1.03]
    padding = max((high - low) * 0.12, high * 0.008)
    return [max(0.0, low - padding), high + padding]


def build_visual_zone_rows(
    chart_window: pd.DataFrame,
    setup: dict,
    confluence: dict | None,
    brief: dict | None = None,
) -> list[dict[str, Any]]:
    if chart_window.empty:
        return []
    confluence = confluence or {}
    brief = brief or {}
    first_ts = chart_window["ts"].iloc[0]
    last_ts = chart_window["ts"].iloc[-1]
    latest = chart_window.iloc[-1].to_dict()
    latest_close = chart_reference_price(chart_window)
    entry = safe_float(brief.get("entry")) or safe_float(confluence.get("entry")) or safe_float(setup.get("entry"))
    stop = safe_float(brief.get("stop")) or safe_float(confluence.get("stop")) or safe_float(setup.get("stop"))
    resistance = safe_float(latest.get("range_high_60"))
    support = safe_float(latest.get("range_low_60"))
    zones: list[dict[str, Any]] = []

    def add(label: str, center: Any, tone: str, role: str, *, lower: float = 0.60, upper: float = 1.55) -> None:
        price = safe_float(center)
        if price is None or not chart_level_is_near(price, latest_close, lower=lower, upper=upper):
            return
        band = chart_zone_band(price, chart_window)
        zones.append(
            {
                "ts": first_ts,
                "ts2": last_ts,
                "low": price - band,
                "high": price + band,
                "center": price,
                "zone": label,
                "tone": tone,
                "role": role,
            }
        )

    add("Zona entrada", entry, "buy", "Comprar solo si 15m/1h y volumen confirman.", lower=0.55, upper=1.65)
    add("Zona stop", stop, "avoid", "Si pierde esta zona, el setup queda invalido.", lower=0.55, upper=1.65)
    add("Soporte", support, "watch", "Zona donde Roxy busca rebote o defensa.", lower=0.75, upper=1.25)
    add("Resistencia", resistance, "watch", "Ruptura valida solo con volumen.", lower=0.75, upper=1.25)
    return zones


def render_alert_noise_contract(brief: dict) -> None:
    opportunities = brief.get("opportunities") or []
    alert_rows = [row for row in opportunities if str(row.get("ai_action") or "").upper() == "ALERT"]
    top = opportunities[0] if opportunities else {}
    top_gate = alert_gate_label(top.get("alert_gate")) if top else "-"
    top_blocker = text_display(top.get("alert_primary_blocker") or ((top.get("alert_blockers") or ["-"])[0] if isinstance(top.get("alert_blockers"), list) and top.get("alert_blockers") else "-"))
    freshness = brief.get("source_freshness") or {}
    session = brief.get("market_session") or {}
    cols = st.columns(4)
    with cols[0]:
        render_kpi_card("Alertas reales", len(alert_rows), tone="buy" if alert_rows else "neutral", detail="Max 3 por brief")
    with cols[1]:
        render_kpi_card("Regla anti-ruido", "Todo o nada", tone="watch", detail="1h + 15m + volumen + riesgo + target")
    with cols[2]:
        render_kpi_card("Bloqueo principal", top_gate, tone="watch", detail=top_blocker)
    with cols[3]:
        session_text = session.get("stock_session") or "-"
        fresh_text = freshness.get("label") or "-"
        render_kpi_card("Contexto", f"{session_text} / {fresh_text}", tone="buy" if freshness.get("alerts_allowed", True) else "avoid")


def greek_quality_label(row: dict[str, Any]) -> tuple[str, str, str]:
    delta = safe_float(row.get("delta"))
    gamma = safe_float(row.get("gamma"))
    theta = safe_float(row.get("theta"))
    vega = safe_float(row.get("vega"))
    iv = safe_float(row.get("impliedVolatility"))
    has_full = all(value is not None for value in [delta, gamma, theta, vega])
    if has_full:
        return "Completo", "buy", "Delta, gamma, theta y vega disponibles."
    if delta is not None and iv is not None:
        return "Basico estimado", "watch", "Delta estimada con IV; faltan gamma/theta/vega reales."
    if delta is not None:
        return "Parcial", "watch", "Delta disponible; faltan Greeks completos."
    return "Incompleto", "avoid", "No tratar este contrato como setup profesional sin Greeks."


def annotate_option_greek_quality(options_df: pd.DataFrame) -> pd.DataFrame:
    if options_df.empty:
        return options_df
    data = options_df.copy()
    labels = data.apply(lambda row: greek_quality_label(row.to_dict()), axis=1)
    data["greek_quality"] = [item[0] for item in labels]
    data["greek_tone"] = [item[1] for item in labels]
    data["greek_note"] = [item[2] for item in labels]
    return data


def _option_greek_is_professional(row: dict[str, Any]) -> bool:
    quality = str(row.get("greek_quality") or "").upper()
    if quality in {"FULL_GREEKS", "COMPLETO"}:
        return True
    return all(safe_float(row.get(key)) is not None for key in ["delta", "gamma", "theta", "vega"])


def annotate_professional_options_contracts(options_df: pd.DataFrame) -> pd.DataFrame:
    if options_df.empty:
        return options_df
    data = options_df.copy()
    numeric_cols = [
        "bid",
        "ask",
        "mid",
        "strike",
        "underlying_price",
        "dte",
        "spread_pct",
        "spread_dollars",
        "volume",
        "openInterest",
        "breakeven_price",
        "breakeven_pct",
        "max_loss_per_contract",
    ]
    for column in numeric_cols:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    if "side" not in data.columns:
        data["side"] = data.apply(lambda row: option_side_from_row(row.to_dict()), axis=1)
    if {"bid", "ask"}.issubset(data.columns):
        if "mid" not in data.columns:
            data["mid"] = pd.Series(float("nan"), index=data.index, dtype="float64")
        else:
            data["mid"] = pd.to_numeric(data["mid"], errors="coerce")
        data["mid"] = data["mid"].fillna((data["bid"] + data["ask"]) / 2.0)
        if "spread_dollars" not in data.columns:
            data["spread_dollars"] = pd.Series(float("nan"), index=data.index, dtype="float64")
        else:
            data["spread_dollars"] = pd.to_numeric(data["spread_dollars"], errors="coerce")
        data["spread_dollars"] = data["spread_dollars"].fillna(data["ask"] - data["bid"])
        if "max_loss_per_contract" not in data.columns:
            data["max_loss_per_contract"] = pd.Series(float("nan"), index=data.index, dtype="float64")
        else:
            data["max_loss_per_contract"] = pd.to_numeric(data["max_loss_per_contract"], errors="coerce")
        data["max_loss_per_contract"] = data["max_loss_per_contract"].fillna(data["ask"] * 100.0)

    if {"strike", "ask", "side"}.issubset(data.columns):
        if "breakeven_price" not in data.columns:
            data["breakeven_price"] = pd.Series(float("nan"), index=data.index, dtype="float64")
        else:
            data["breakeven_price"] = pd.to_numeric(data["breakeven_price"], errors="coerce")
        call_be = data["strike"] + data["ask"]
        put_be = data["strike"] - data["ask"]
        computed_be = data["side"].astype(str).str.upper().map({"CALL": 1, "PUT": -1})
        computed_be = computed_be.where(computed_be.ne(1), call_be)
        computed_be = computed_be.where(data["side"].astype(str).str.upper().ne("PUT"), put_be)
        data["breakeven_price"] = data["breakeven_price"].fillna(computed_be)
    if {"breakeven_price", "underlying_price"}.issubset(data.columns):
        if "breakeven_pct" not in data.columns:
            data["breakeven_pct"] = pd.Series(float("nan"), index=data.index, dtype="float64")
        else:
            data["breakeven_pct"] = pd.to_numeric(data["breakeven_pct"], errors="coerce")
        data["breakeven_pct"] = data["breakeven_pct"].fillna((data["breakeven_price"] / data["underlying_price"]) - 1.0)

    rows = []
    for _, row in data.iterrows():
        row_dict = row.to_dict()
        blockers = []
        dte = safe_float(row_dict.get("dte"))
        spread = safe_float(row_dict.get("spread_pct"))
        volume = safe_float(row_dict.get("volume")) or 0.0
        open_interest = safe_float(row_dict.get("openInterest")) or 0.0
        max_loss = safe_float(row_dict.get("max_loss_per_contract"))
        fits_1r = row_dict.get("fits_1r")

        if dte is None or not (7 <= dte <= 45):
            blockers.append("DTE fuera de 7-45")
        if spread is None or spread > 0.18:
            blockers.append("Spread alto")
        if volume < 50 or open_interest < 100:
            blockers.append("Liquidez baja")
        if not _option_greek_is_professional(row_dict):
            blockers.append("Faltan Greeks completos")
        if max_loss is None or max_loss <= 0:
            blockers.append("Max loss no medible")
        elif isinstance(fits_1r, bool) and not fits_1r:
            blockers.append("No cabe en 1R")

        readiness = "Listo para revisar" if not blockers else "Solo paper" if "Faltan Greeks completos" not in blockers else "Faltan Greeks"
        rows.append(
            {
                "professional_readiness": readiness,
                "professional_blockers": "OK" if not blockers else " | ".join(blockers[:4]),
                "dte_ok": dte is not None and 7 <= dte <= 45,
                "spread_ok": spread is not None and spread <= 0.18,
                "liquidity_ok": volume >= 50 and open_interest >= 100,
                "greeks_ok": _option_greek_is_professional(row_dict),
                "max_loss_ok": max_loss is not None and max_loss > 0,
            }
        )

    extra = pd.DataFrame(rows, index=data.index)
    return pd.concat([data, extra], axis=1)


def lab_daily_summary_rows(lab_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not lab_rows:
        return []
    promoted = next((row for row in lab_rows if row.get("lab_state") == "Promote"), None)
    tighten = next((row for row in lab_rows if row.get("lab_state") == "Tighten filter"), None)
    watch = next((row for row in lab_rows if row.get("lab_state") == "Watch"), None)
    collect = next((row for row in lab_rows if row.get("lab_state") == "Collect data"), None)
    output: list[dict[str, str]] = []

    def add(label: str, row: dict[str, Any] | None, tone: str, fallback: str) -> None:
        if row:
            strategy = text_display(row.get("strategy_family"))
            action = text_display(row.get("production_action") or row.get("lab_decision"))
            evidence = pct_display(row.get("evidence_score"))
            detail = f"{action} | Evidencia {evidence}"
        else:
            strategy = fallback
            detail = "Roxy sigue recolectando datos."
        output.append({"label": label, "strategy": strategy, "detail": detail, "tone": tone})

    add("Promover", promoted, "buy", "Ninguna todavia")
    add("Endurecer", tighten, "avoid", "Ninguna todavia")
    add("Vigilar", watch, "watch", "Ninguna todavia")
    add("Estudiar", collect, "neutral", "Recolectar mas datos")
    return output


def render_lab_daily_summary(lab_rows: list[dict[str, Any]]) -> None:
    rows = lab_daily_summary_rows(lab_rows)
    if not rows:
        return
    st.markdown("**Decision diaria del laboratorio**")
    cols = st.columns(len(rows))
    for col, row in zip(cols, rows):
        with col:
            render_kpi_card(row["label"], row["strategy"], tone=row["tone"], detail=row["detail"])


def build_price_hover_layers(chart_window: pd.DataFrame, price_scale: alt.Scale | None = None) -> list[alt.Chart]:
    if chart_window.empty or not {"ts", "close"}.issubset(chart_window.columns):
        return []
    hover_cols = ["ts", "open", "high", "low", "close", "volume", "ema9", "sma20", "sma40", "sma100", "sma200"]
    hover_cols = [column for column in hover_cols if column in chart_window.columns]
    hover_df = chart_window[hover_cols].copy()
    hover = alt.selection_point(
        name="candle_hover",
        fields=["ts"],
        nearest=True,
        on="pointerover",
        clear="pointerout",
        empty=False,
    )
    y_encoding = alt.Y("close:Q", title="Precio", scale=price_scale or alt.Scale(zero=False))
    tooltips = [
        alt.Tooltip("ts:T", title="Tiempo"),
        alt.Tooltip("open:Q", title="Open", format=".2f"),
        alt.Tooltip("high:Q", title="High", format=".2f"),
        alt.Tooltip("low:Q", title="Low", format=".2f"),
        alt.Tooltip("close:Q", title="Close", format=".2f"),
    ]
    if "volume" in hover_df.columns:
        tooltips.append(alt.Tooltip("volume:Q", title="Volumen", format=",.0f"))
    for column, label in (("ema9", "EMA9"), ("sma20", "SMA20"), ("sma40", "SMA40"), ("sma100", "SMA100"), ("sma200", "SMA200")):
        if column in hover_df.columns:
            tooltips.append(alt.Tooltip(f"{column}:Q", title=label, format=".2f"))

    hover_base = alt.Chart(hover_df).encode(x=alt.X("ts:T", title="Tiempo"))
    selector = hover_base.mark_point(opacity=0, size=90).encode(y=y_encoding, tooltip=tooltips).add_params(hover)
    crosshair = hover_base.mark_rule(color="#e5e7eb", opacity=0.55, strokeDash=[3, 3]).transform_filter(hover)
    marker = (
        hover_base.mark_point(filled=True, size=78, color="#f8fafc", stroke="#0f172a", strokeWidth=1.2)
        .encode(y=y_encoding, tooltip=tooltips)
        .transform_filter(hover)
    )
    return [selector, crosshair, marker]


def build_alpaca_paper_marker_layers(
    chart_window: pd.DataFrame,
    paper_snapshot: dict[str, Any] | None,
    symbol: str,
    price_scale: alt.Scale,
) -> list[alt.Chart]:
    markers = alpaca_paper_chart_markers(paper_snapshot or {}, chart_window, symbol)
    if markers.empty:
        return []
    point_layer = (
        alt.Chart(markers)
        .mark_point(filled=True, size=155, stroke="#020617", strokeWidth=1.4)
        .encode(
            x=alt.X("ts:T", title="Tiempo"),
            y=alt.Y("price:Q", title="Precio", scale=price_scale),
            color=alt.Color(
                "tone:N",
                legend=None,
                scale=alt.Scale(domain=["buy", "avoid"], range=["#22c55e", "#ef4444"]),
            ),
            shape=alt.Shape(
                "side:N",
                legend=None,
                scale=alt.Scale(domain=["BUY", "SELL"], range=["triangle-up", "triangle-down"]),
            ),
            tooltip=[
                alt.Tooltip("event:N", title="Paper"),
                alt.Tooltip("side:N", title="Side"),
                alt.Tooltip("status:N", title="Estado"),
                alt.Tooltip("price:Q", title="Precio", format=".2f"),
                alt.Tooltip("ts:T", title="Tiempo"),
            ],
        )
    )
    label_layer = (
        alt.Chart(markers)
        .mark_text(align="left", dx=9, dy=-12, fontSize=11, fontWeight="bold")
        .encode(
            x=alt.X("ts:T", title="Tiempo"),
            y=alt.Y("price:Q", title="Precio", scale=price_scale),
            text="label:N",
            color=alt.Color(
                "tone:N",
                legend=None,
                scale=alt.Scale(domain=["buy", "avoid"], range=["#bbf7d0", "#fecaca"]),
            ),
        )
    )
    return [point_layer, label_layer]


def build_professional_price_chart(
    chart_df: pd.DataFrame,
    setup: dict,
    confluence: dict | None,
    brief: dict | None = None,
    *,
    paper_snapshot: dict[str, Any] | None = None,
    symbol: str | None = None,
) -> alt.LayerChart:
    chart_window = prepare_chart_window(chart_df)
    confluence = confluence or {}
    brief = brief or {}
    if chart_window.empty:
        fallback = pd.DataFrame({"ts": [pd.Timestamp.utcnow()], "price": [0.0], "message": ["Sin historial suficiente"]})
        return alt.Chart(fallback).mark_text(color="#cbd5e1", fontSize=16).encode(x="ts:T", y="price:Q", text="message:N")
    chart_window["direction"] = ["up" if close >= open_ else "down" for close, open_ in zip(chart_window["close"], chart_window["open"])]
    base = alt.Chart(chart_window).encode(x=alt.X("ts:T", title="Tiempo"))

    layers: list[alt.Chart] = []
    entry = safe_float(brief.get("entry")) or safe_float(confluence.get("entry")) or safe_float(setup.get("entry"))
    stop = safe_float(brief.get("stop")) or safe_float(confluence.get("stop")) or safe_float(setup.get("stop"))
    targets: list[dict[str, float | str]] = []
    for item in brief.get("target_ladder", []):
        price = safe_float(item.get("target_price"))
        if price is not None:
            targets.append({"price": price, "label": f"Objetivo {item.get('target', '-')}", "color": "#a78bfa"})
    if not targets and entry is not None:
        targets = [
            {"price": entry * 1.02, "label": "Objetivo 2%", "color": "#60a5fa"},
            {"price": entry * 1.05, "label": "Objetivo 5%", "color": "#a78bfa"},
            {"price": entry * 1.10, "label": "Objetivo 10%", "color": "#f472b6"},
        ]
    price_domain = chart_price_domain(chart_window, setup, confluence, brief, targets)
    price_scale = alt.Scale(zero=False, domain=price_domain) if price_domain else alt.Scale(zero=False)
    if entry is not None and not chart_window.empty:
        first_ts = chart_window["ts"].iloc[0]
        last_ts = chart_window["ts"].iloc[-1]
        if stop is not None and 0 < stop < entry:
            risk_zone = pd.DataFrame({"ts": [first_ts, last_ts], "low": [stop, stop], "high": [entry, entry]})
            layers.append(
                alt.Chart(risk_zone)
                .mark_area(color="#ef4444", opacity=0.07)
                .encode(x=alt.X("ts:T", title="Tiempo"), y=alt.Y("low:Q", title="Precio", scale=price_scale), y2="high:Q")
            )
        target_10 = next((safe_float(item.get("price")) for item in targets if "10%" in str(item.get("label"))), None)
        if target_10 is not None and target_10 > entry:
            reward_zone = pd.DataFrame({"ts": [first_ts, last_ts], "low": [entry, entry], "high": [target_10, target_10]})
            layers.append(
                alt.Chart(reward_zone)
                .mark_area(color="#22c55e", opacity=0.05)
                .encode(x=alt.X("ts:T", title="Tiempo"), y=alt.Y("low:Q", title="Precio", scale=price_scale), y2="high:Q")
            )
        entry_band = pd.DataFrame(
            {"ts": [first_ts, last_ts], "low": [entry * 0.995, entry * 0.995], "high": [entry * 1.005, entry * 1.005]}
        )
        layers.append(
            alt.Chart(entry_band)
            .mark_area(color="#22c55e", opacity=0.11)
            .encode(x=alt.X("ts:T", title="Tiempo"), y=alt.Y("low:Q", title="Precio", scale=price_scale), y2="high:Q")
        )

    visual_zones = build_visual_zone_rows(chart_window, setup, confluence, brief)
    if visual_zones:
        zone_df = pd.DataFrame(visual_zones)
        layers.append(
            alt.Chart(zone_df)
            .mark_rect(opacity=0.16)
            .encode(
                x=alt.X("ts:T", title="Tiempo"),
                x2="ts2:T",
                y=alt.Y("low:Q", title="Precio", scale=price_scale),
                y2="high:Q",
                color=alt.Color(
                    "tone:N",
                    legend=None,
                    scale=alt.Scale(domain=["buy", "watch", "avoid"], range=["#22c55e", "#38bdf8", "#ef4444"]),
                ),
                tooltip=[
                    alt.Tooltip("zone:N", title="Zona"),
                    alt.Tooltip("center:Q", title="Precio", format=".2f"),
                    alt.Tooltip("role:N", title="Uso"),
                ],
            )
        )
        zone_labels = zone_df.copy()
        zone_labels = zone_labels[zone_labels["zone"].isin(["Zona entrada", "Zona stop"])]
        zone_labels["label_text"] = zone_labels.apply(lambda row: f"{row['zone']} {row['center']:.2f}", axis=1)
        zone_labels["label_ts"] = chart_window["ts"].iloc[max(0, len(chart_window) - 52)]
        if not zone_labels.empty:
            layers.append(
                alt.Chart(zone_labels)
                .mark_text(align="left", dx=6, dy=-12, fontSize=11, fontWeight="bold")
                .encode(
                    x=alt.X("label_ts:T", title="Tiempo"),
                    y=alt.Y("center:Q", title="Precio", scale=price_scale),
                    text="label_text:N",
                    color=alt.Color(
                        "tone:N",
                        legend=None,
                        scale=alt.Scale(domain=["buy", "watch", "avoid"], range=["#22c55e", "#38bdf8", "#ef4444"]),
                    ),
                )
            )

    if {"bb_upper", "bb_lower"}.issubset(chart_window.columns):
        band_df = chart_window.dropna(subset=["bb_upper", "bb_lower"])
        if not band_df.empty:
            layers.append(
                alt.Chart(band_df)
                .mark_area(color="#94a3b8", opacity=0.18)
                .encode(
                    x=alt.X("ts:T", title="Tiempo"),
                    y=alt.Y("bb_lower:Q", title="Precio", scale=price_scale),
                    y2="bb_upper:Q",
                    tooltip=[
                        alt.Tooltip("ts:T", title="Tiempo"),
                        alt.Tooltip("bb_lower:Q", title="Banda baja", format=".2f"),
                        alt.Tooltip("bb_upper:Q", title="Banda alta", format=".2f"),
                    ],
                )
            )

    if {"range_high_60", "range_low_60"}.issubset(chart_window.columns):
        channel_df = chart_window.dropna(subset=["range_high_60", "range_low_60"])
        reference = chart_reference_price(chart_window)
        if reference:
            channel_df = channel_df[
                channel_df["range_high_60"].map(lambda value: chart_level_is_near(value, reference, lower=0.75, upper=1.25))
                & channel_df["range_low_60"].map(lambda value: chart_level_is_near(value, reference, lower=0.75, upper=1.25))
            ]
        if not channel_df.empty:
            layers.append(
                alt.Chart(channel_df)
                .mark_area(color="#22d3ee", opacity=0.045)
                .encode(
                    x=alt.X("ts:T", title="Tiempo"),
                    y=alt.Y("range_low_60:Q", title="Precio", scale=price_scale),
                    y2="range_high_60:Q",
                    tooltip=[
                        alt.Tooltip("ts:T", title="Tiempo"),
                        alt.Tooltip("range_low_60:Q", title="Soporte", format=".2f"),
                        alt.Tooltip("range_high_60:Q", title="Resistencia", format=".2f"),
                    ],
                )
            )

    candle_tooltips = [
        alt.Tooltip("ts:T", title="Tiempo"),
        alt.Tooltip("open:Q", title="Open", format=".2f"),
        alt.Tooltip("high:Q", title="High", format=".2f"),
        alt.Tooltip("low:Q", title="Low", format=".2f"),
        alt.Tooltip("close:Q", title="Close", format=".2f"),
        alt.Tooltip("volume:Q", title="Volumen", format=",.0f"),
    ]
    candle_color = alt.condition("datum.close >= datum.open", alt.value("#22c55e"), alt.value("#ef4444"))
    layers.append(
        base.mark_rule(size=1.2)
        .encode(
            y=alt.Y("low:Q", title="Precio", scale=price_scale),
            y2="high:Q",
            color=candle_color,
            tooltip=candle_tooltips,
        )
    )
    layers.append(
        base.mark_bar(size=5)
        .encode(
            y=alt.Y("open:Q", title="Precio", scale=price_scale),
            y2="close:Q",
            color=candle_color,
            tooltip=candle_tooltips,
        )
    )
    layers.extend(build_price_hover_layers(chart_window, price_scale))
    chart_symbol = text_display(symbol or brief.get("symbol") or confluence.get("symbol") or setup.get("symbol"))
    layers.extend(build_alpaca_paper_marker_layers(chart_window, paper_snapshot, chart_symbol, price_scale))

    event_rows = [row for row in latest_chart_strategy_events(chart_window, setup) if row.get("status") in {"ACTIVE", "WATCH"}]
    if event_rows:
        event_df = pd.DataFrame(event_rows)
        layers.append(
            alt.Chart(event_df)
            .mark_point(filled=True, size=120, stroke="#0f172a", strokeWidth=1)
            .encode(
                x=alt.X("ts:T", title="Time"),
                y=alt.Y("price:Q", title="Precio", scale=price_scale),
                color=alt.Color("marker:N", legend=None, scale=alt.Scale(range=event_df["color"].tolist())),
                shape=alt.Shape(
                    "status:N",
                    legend=None,
                    scale=alt.Scale(domain=["ACTIVE", "WATCH"], range=["triangle-up", "circle"]),
                ),
                tooltip=[
                    alt.Tooltip("marker:N", title="Marcador"),
                    alt.Tooltip("status:N", title="Estado"),
                    alt.Tooltip("event:N", title="Evento"),
                    alt.Tooltip("what_it_means:N", title="Lectura"),
                    alt.Tooltip("wait_for:N", title="Esperar"),
                    alt.Tooltip("price:Q", title="Precio", format=".2f"),
                ],
            )
        )

    line_cols = [col for col in ["ema9", "sma20", "sma40", "sma100", "sma200"] if col in chart_window.columns]
    if line_cols:
        chart_long = chart_window[["ts", *line_cols]].melt("ts", var_name="line", value_name="price").dropna()
        layers.append(
            alt.Chart(chart_long)
            .mark_line(size=1.8)
            .encode(
                x=alt.X("ts:T", title="Tiempo"),
                y=alt.Y("price:Q", title="Precio", scale=price_scale),
                color=alt.Color(
                    "line:N",
                    title="Media",
                    legend=alt.Legend(orient="bottom", columns=5),
                    scale=alt.Scale(
                        domain=["ema9", "sma20", "sma40", "sma100", "sma200"],
                        range=["#e879f9", "#22c55e", "#38bdf8", "#f59e0b", "#ef4444"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("ts:T", title="Tiempo"),
                    alt.Tooltip("line:N", title="Media"),
                    alt.Tooltip("price:Q", title="Precio", format=".2f"),
                ],
            )
        )

    levels = []
    for level, label, color in (
        (entry, "Entrada", "#22c55e"),
        (stop, "Stop", "#ef4444"),
        (confluence.get("recommended_target_price") if confluence else None, "Objetivo", "#a78bfa"),
    ):
        number = safe_float(level)
        if number is not None:
            levels.append({"price": number, "label": label, "color": color})
    for target in targets:
        number = safe_float(target.get("price"))
        if number is not None:
            levels.append({"price": number, "label": str(target.get("label")), "color": str(target.get("color"))})
    if not chart_window.empty:
        last = chart_window.iloc[-1]
        last_close = safe_float(last.get("close"))
        if last_close is not None:
            levels.append({"price": last_close, "label": "Actual", "color": "#f8fafc"})
        for level, label, color in (
            (last.get("range_high_60"), "Resistencia", "#22d3ee"),
            (last.get("range_low_60"), "Soporte", "#22d3ee"),
        ):
            number = safe_float(level)
            if number is not None and chart_level_is_near(number, last_close, lower=0.75, upper=1.25):
                levels.append({"price": number, "label": label, "color": color})
    if levels:
        deduped: list[dict[str, Any]] = []
        seen_levels: set[tuple[str, float]] = set()
        label_idx = max(0, len(chart_window) - 14)
        label_ts = chart_window["ts"].iloc[label_idx] if not chart_window.empty else None
        for item in levels:
            price = safe_float(item.get("price"))
            if price is None:
                continue
            key = (str(item.get("label")), round(price, 4))
            if key in seen_levels:
                continue
            seen_levels.add(key)
            deduped.append(
                {
                    **item,
                    "price": price,
                    "label_text": f"{item.get('label')} {price:.2f}",
                    "ts": label_ts,
                }
            )
        level_df = pd.DataFrame(deduped)
        labels = level_df["label"].tolist()
        colors = level_df["color"].tolist()
        layers.append(
            alt.Chart(level_df)
            .mark_rule(strokeDash=[6, 4], size=1.4)
            .encode(
                y=alt.Y("price:Q", title="Precio", scale=price_scale),
                color=alt.Color("label:N", legend=None, scale=alt.Scale(domain=labels, range=colors)),
                tooltip=[alt.Tooltip("label:N", title="Nivel"), alt.Tooltip("price:Q", title="Precio", format=".2f")],
            )
        )
        label_df = level_df[level_df["label"].isin(["Actual", "Entrada", "Stop", "Objetivo 2%"])]
        if not label_df.empty:
            layers.append(
                alt.Chart(label_df)
            .mark_text(align="left", dx=8, dy=-6, fontSize=12, fontWeight="bold")
            .encode(
                x=alt.X("ts:T", title="Tiempo"),
                y=alt.Y("price:Q", title="Precio", scale=price_scale),
                text="label_text:N",
                color=alt.Color("label:N", legend=None, scale=alt.Scale(domain=labels, range=colors)),
            )
            )

    if not chart_window.empty:
        latest = chart_window.iloc[-1].to_dict()
        callout_price = (
            safe_float(brief.get("entry"))
            or safe_float(confluence.get("entry"))
            or safe_float(setup.get("entry"))
            or safe_float(latest.get("close"))
        )
        if callout_price is not None:
            callout = chart_strategy_summary(setup, confluence, brief, chart_window)
            callout_df = pd.DataFrame(
                [
                    {
                        "ts": chart_window["ts"].iloc[max(0, len(chart_window) - 36)],
                        "price": callout_price,
                        "label": f"{callout['family']} · {callout['action']}",
                        "tone": callout["tone"],
                    }
                ]
            )
            layers.append(
                alt.Chart(callout_df)
                .mark_text(align="left", dx=8, dy=-18, fontSize=14, fontWeight="bold")
                .encode(
                    x=alt.X("ts:T", title="Tiempo"),
                    y=alt.Y("price:Q", title="Precio", scale=price_scale),
                    text="label:N",
                    color=alt.Color(
                        "tone:N",
                        legend=None,
                        scale=alt.Scale(domain=["buy", "watch", "avoid", "neutral"], range=["#22c55e", "#f59e0b", "#ef4444", "#cbd5e1"]),
                    ),
                )
            )

    return alt.layer(*layers).resolve_scale(color="independent")


def style_trading_chart(chart):
    return (
        chart.interactive()
        .configure(background="#0b1220")
        .configure_axis(
            grid=True,
            gridColor="rgba(148,163,184,0.16)",
            labelColor="#cbd5e1",
            titleColor="#cbd5e1",
            labelFontSize=10,
            titleFontSize=11,
            titlePadding=4,
        )
        .configure_axisX(
            title=None,
            labelAngle=0,
            labelFlush=True,
            tickColor="rgba(148,163,184,0.22)",
            domainColor="rgba(148,163,184,0.20)",
        )
        .configure_axisY(domainColor="rgba(148,163,184,0.20)", tickColor="rgba(148,163,184,0.22)")
        .configure_view(stroke="rgba(148,163,184,0.20)")
        .configure_legend(
            labelColor="#e5edf7",
            titleColor="#cbd5e1",
            orient="bottom",
            direction="horizontal",
            labelFontSize=10,
            titleFontSize=10,
            symbolSize=70,
        )
    )


def build_professional_volume_chart(chart_df: pd.DataFrame) -> alt.LayerChart | None:
    if "volume" not in chart_df.columns:
        return None
    volume_window = prepare_chart_window(chart_df).dropna(subset=["volume"]).copy()
    if volume_window.empty:
        return None
    volume_color = alt.condition("datum.close >= datum.open", alt.value("#22c55e"), alt.value("#ef4444"))
    layers: list[alt.Chart] = [
        alt.Chart(volume_window)
        .mark_bar(opacity=0.56)
        .encode(
            x=alt.X("ts:T", title="Tiempo"),
            y=alt.Y("volume:Q", title="Volumen"),
            color=volume_color,
            tooltip=[
                alt.Tooltip("ts:T", title="Tiempo"),
                alt.Tooltip("volume:Q", title="Volumen", format=",.0f"),
                alt.Tooltip("relative_volume:Q", title="Volumen relativo", format=".2f")
                if "relative_volume" in volume_window.columns
                else alt.Tooltip("volume:Q", title="Volumen", format=",.0f"),
            ],
        )
    ]
    if "volume_sma20" in volume_window.columns and volume_window["volume_sma20"].notna().any():
        layers.append(
            alt.Chart(volume_window.dropna(subset=["volume_sma20"]))
            .mark_line(color="#f59e0b", size=1.6)
            .encode(
                x=alt.X("ts:T", title="Tiempo"),
                y=alt.Y("volume_sma20:Q", title="Volumen"),
                tooltip=[
                    alt.Tooltip("ts:T", title="Tiempo"),
                    alt.Tooltip("volume_sma20:Q", title="Volumen SMA20", format=",.0f"),
                ],
            )
        )
    return alt.layer(*layers).resolve_scale(color="independent")


def build_professional_oscillator_chart(chart_df: pd.DataFrame) -> alt.LayerChart | None:
    oscillator_cols = [column for column in ("rsi14", "macd_hist") if column in chart_df.columns]
    if not oscillator_cols:
        return None
    window = prepare_chart_window(chart_df)
    subset = ["ts", *oscillator_cols]
    oscillator_window = window[subset].dropna(how="all", subset=oscillator_cols).copy() if not window.empty else pd.DataFrame()
    if oscillator_window.empty:
        return None

    layers: list[alt.Chart] = []
    if "rsi14" in oscillator_window.columns and oscillator_window["rsi14"].notna().any():
        rsi_df = oscillator_window.dropna(subset=["rsi14"]).copy()
        rsi_base = alt.Chart(rsi_df).encode(x=alt.X("ts:T", title="Tiempo"))
        layers.append(
            rsi_base.mark_line(color="#38bdf8", size=1.8).encode(
                y=alt.Y("rsi14:Q", title="RSI 14", scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    alt.Tooltip("ts:T", title="Tiempo"),
                    alt.Tooltip("rsi14:Q", title="RSI 14", format=".1f"),
                ],
            )
        )
        for value, label, color in ((70, "RSI 70", "#f59e0b"), (30, "RSI 30", "#22c55e")):
            layers.append(
                alt.Chart(pd.DataFrame({"level": [value], "label": [label]}))
                .mark_rule(strokeDash=[4, 4], color=color, opacity=0.65)
                .encode(y=alt.Y("level:Q", title="RSI 14", scale=alt.Scale(domain=[0, 100])), tooltip=["label:N"])
            )

    if "macd_hist" in oscillator_window.columns and oscillator_window["macd_hist"].notna().any():
        macd_df = oscillator_window.dropna(subset=["macd_hist"]).copy()
        macd_color = alt.condition("datum.macd_hist >= 0", alt.value("#22c55e"), alt.value("#ef4444"))
        layers.append(
            alt.Chart(macd_df)
            .mark_bar(opacity=0.38)
            .encode(
                x=alt.X("ts:T", title="Tiempo"),
                y=alt.Y("macd_hist:Q", title="MACD hist"),
                color=macd_color,
                tooltip=[
                    alt.Tooltip("ts:T", title="Tiempo"),
                    alt.Tooltip("macd_hist:Q", title="MACD hist", format=".4f"),
                ],
            )
        )

    if not layers:
        return None
    return alt.layer(*layers).resolve_scale(y="independent", color="independent")


def render_strategy_event_panel(chart_df: pd.DataFrame, setup: dict) -> None:
    events = latest_chart_strategy_events(chart_df, setup)
    if not events:
        return
    st.markdown("**Marcadores de estrategia**")
    status_label = {"ACTIVE": "Activo", "WATCH": "Vigilar", "BLOCKED": "Bloqueado"}
    display = pd.DataFrame(
        [
            {
                "Estado": status_label.get(str(row.get("status")), str(row.get("status") or "-")),
                "Marcador": row.get("marker"),
                "Lectura": row.get("what_it_means"),
                "Esperar": row.get("wait_for"),
                "Precio": num_display(row.get("price")),
            }
            for row in events
        ]
    )
    st.dataframe(display, width="stretch", hide_index=True)


def render_focus_action_brief(brief: dict) -> None:
    direct = brief.get("direct_plan") or {}
    decision = text_display(direct.get("status") or brief.get("decision"))
    action = text_display(brief.get("action"))
    tone = "buy" if action in {"BUY_STOCK", "WATCH_CALL"} else "avoid" if action == "NO_TRADE" else "watch"
    reason_text = text_display(direct.get("summary"))
    if reason_text == "-":
        reasons = [str(item) for item in brief.get("reasons", []) if str(item).strip()]
        reason_text = " ".join(reasons[:3]) or "Esperar una confirmacion mas limpia antes de operar."
    teaching = text_display(brief.get("teaching_note"))
    if teaching == "-":
        teaching = "Roxy esta comparando tendencia, medias moviles, volumen, riesgo y memoria antes de alertar."
    st.markdown(
        f"""
        <div class="trade-plan trade-plan-{tone}">
            <div class="trade-plan-title">Roxy: {html.escape(decision)}</div>
            <div class="trade-plan-line">{html.escape(reason_text)}</div>
            <div class="trade-plan-line">{html.escape(teaching)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_watch_plan(brief: dict) -> None:
    plan = brief.get("watch_plan") or {}
    movement = text_display(plan.get("movement"))
    if movement == "-":
        return
    st.markdown("**Movimiento que estamos esperando**")
    st.info(movement)
    confirmations = [str(item) for item in plan.get("confirmations", []) if str(item).strip()]
    levels = [str(item) for item in plan.get("levels", []) if str(item).strip()]
    if confirmations:
        cols = st.columns(min(3, len(confirmations)))
        for col, item in zip(cols, confirmations[:3]):
            with col:
                render_kpi_card("Falta", item, tone="watch")
    if levels:
        st.caption(" | ".join(levels[:5]))


def render_decision_reason(brief: dict) -> None:
    reason = brief.get("decision_reason") or {}
    title = text_display(reason.get("title"))
    summary = text_display(reason.get("summary"))
    if title == "-" and summary == "-":
        return
    tone = str(reason.get("tone") or "watch")
    tone = tone if tone in {"buy", "watch", "avoid", "neutral"} else "watch"
    st.markdown(f"**{html.escape(title if title != '-' else 'Por que Roxy decide esto')}**")
    if summary != "-":
        if tone == "buy":
            st.success(summary)
        elif tone == "avoid":
            st.warning(summary)
        else:
            st.info(summary)

    bullets = [str(item) for item in reason.get("bullets", []) if str(item).strip()]
    if bullets:
        cols = st.columns(min(3, len(bullets)))
        for col, item in zip(cols, bullets[:3]):
            with col:
                render_kpi_card("Razon", item[:140], tone=tone)

    next_steps = [str(item) for item in reason.get("next_steps", []) if str(item).strip()]
    if next_steps:
        st.caption("Siguiente: " + " | ".join(next_steps[:3]))


def render_decision_transition(brief: dict) -> None:
    transition = brief.get("decision_transition") or {}
    title = text_display(transition.get("title"))
    status = text_display(transition.get("status"))
    if title == "-" and status == "-":
        return
    tone = str(transition.get("tone") or "watch")
    tone = tone if tone in {"buy", "watch", "avoid", "neutral"} else "watch"
    st.markdown(f"**{html.escape(title if title != '-' else 'Que cambia la decision')}**")
    if status != "-":
        render_kpi_card("Regla", status, tone=tone)
    items = [str(item) for item in transition.get("items", []) if str(item).strip()]
    if items:
        cols = st.columns(min(3, len(items)))
        for col, item in zip(cols, items[:3]):
            with col:
                render_kpi_card("Condicion", item[:140], tone=tone)


def render_ai_trade_brief(brief: dict) -> None:
    action = str(brief.get("action", "WAIT"))
    tone = "buy" if action in {"BUY_STOCK", "WATCH_CALL"} else "avoid" if action == "NO_TRADE" else "watch"
    symbol = text_display(brief.get("symbol"))
    decision = text_display(brief.get("decision"))
    direct = brief.get("direct_plan") or {}
    direct_status = text_display(direct.get("status") or decision)
    direct_product = text_display(direct.get("product"))
    direct_summary = text_display(direct.get("summary"))
    direct_next = text_display(direct.get("next_step"))
    entry = safe_float(brief.get("entry"))
    stop = safe_float(brief.get("stop"))
    targets = brief.get("target_ladder", [])
    target_prices = [num_display(item.get("target_price")) for item in targets[:3]]
    while len(target_prices) < 3:
        target_prices.append("-")
    st.markdown("**Plan de operacion**")
    st.markdown(
        f"""
        <div class="trade-plan trade-plan-{tone}">
            <div class="trade-plan-title">{html.escape(symbol)} | {html.escape(direct_status)}</div>
            <div class="trade-plan-line">{html.escape(direct_summary if direct_summary != '-' else decision)}</div>
            <div class="trade-plan-line">
                Entrada {html.escape(num_display(entry))} | Stop {html.escape(num_display(stop))} |
                Objetivos {html.escape(" / ".join(target_prices))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns([1.1, 1, 0.8, 0.8, 0.8, 0.9])
    with cols[0]:
        render_kpi_card("Decision directa", direct_status, tone=tone, detail=direct_product if direct_product != "-" else None)
    with cols[1]:
        render_kpi_card("Estrategia", brief.get("strategy_family", "-"))
    with cols[2]:
        render_kpi_card("Score", num_display(brief.get("score"), 0))
    with cols[3]:
        render_kpi_card("Entrada", num_display(brief.get("entry")))
    with cols[4]:
        render_kpi_card("Stop", num_display(brief.get("stop")))
    with cols[5]:
        render_kpi_card("Riesgo", pct_display(brief.get("risk_pct")), tone="avoid" if tone == "avoid" else "neutral")

    message = direct_next if direct_next != "-" else " ".join(str(item) for item in brief.get("reasons", [])[:5])
    if action in {"BUY_STOCK", "WATCH_CALL"}:
        st.success(message)
    elif action == "NO_TRADE":
        st.warning(message)
    else:
        st.info(message)

    memory = brief.get("memory") or {}
    stats = memory.get("stats") if isinstance(memory, dict) else {}
    if isinstance(stats, dict) and (safe_float(stats.get("alerts")) or 0) > 0:
        st.caption(
            "Memoria real de esta estrategia: "
            f"{int(safe_float(stats.get('alerts')) or 0)} senales | "
            f"2%: {int(safe_float(stats.get('hit_2pct')) or 0)} | "
            f"5%: {int(safe_float(stats.get('hit_5pct')) or 0)} | "
            f"10%: {int(safe_float(stats.get('hit_10pct')) or 0)} | "
            f"Stop: {int(safe_float(stats.get('stops')) or 0)}."
        )
    else:
        st.caption("Memoria real de esta estrategia: Roxy todavia esta recolectando resultados cerrados.")

    render_decision_reason(brief)
    render_decision_transition(brief)

    if action not in {"BUY_STOCK", "WATCH_CALL"}:
        render_watch_plan(brief)

    explanation_lines = [str(item) for item in brief.get("strategy_explanation", []) if str(item).strip()]
    if explanation_lines:
        st.markdown("**Explicacion de Roxy**")
        for line in explanation_lines[:7]:
            st.write(f"- {line}")
        if st.button("Escuchar explicacion de Roxy", key=f"speak_trade_{symbol}_{brief.get('timeframe', '')}"):
            voice_text = f"{symbol}. {decision}. " + " ".join(explanation_lines[:6])
            speak_in_browser(voice_text, key=f"trade-{symbol}-{brief.get('timeframe', '')}")

    target_rows = brief.get("target_ladder", [])
    if target_rows:
        target_df = pd.DataFrame(target_rows)
        display = target_df.copy()
        display["target_price"] = display["target_price"].map(lambda value: num_display(value))
        display["reward_r"] = display["reward_r"].map(lambda value: "-" if pd.isna(value) else f"{value:.2f}R")
        st.dataframe(display[["target", "target_price", "reward_r"]], width="stretch", hide_index=True)

    sizing = brief.get("sizing", {})
    size_cols = st.columns(4)
    with size_cols[0]:
        render_kpi_card("Riesgo $", num_display(sizing.get("risk_dollars")))
    with size_cols[1]:
        render_kpi_card("Acciones", sizing.get("shares", 0))
    with size_cols[2]:
        render_kpi_card("Valor posicion", num_display(sizing.get("stock_notional")))
    with size_cols[3]:
        render_kpi_card("Contratos", sizing.get("contracts", 0))

    option = brief.get("option") or {}
    if option:
        option_cols = [
            "contractSymbol",
            "option_decision",
            "option_score",
            "expiry",
            "dte",
            "strike",
            "delta",
            "bid",
            "ask",
            "spread_pct",
            "volume",
            "openInterest",
            "breakeven_price",
            "breakeven_pct",
            "max_loss_per_contract",
        ]
        st.markdown("**Mejor contrato de opcion**")
        st.dataframe(pd.DataFrame([option])[[col for col in option_cols if col in option]], width="stretch")

    st.caption("Solo apoyo de decision. Roxy exige confirmacion, stop y tamano controlado antes de cualquier operacion real.")


def render_operation_gate(brief: dict) -> None:
    status = text_display(brief.get("operation_status"))
    tone = "buy" if status == "Operar" else "avoid" if status == "No operar" else "watch"
    st.markdown("**Solo operar si...**")
    cols = st.columns([1.1, 1, 1, 1, 1])
    with cols[0]:
        render_kpi_card("Decision final", status, tone=tone)
    checks = brief.get("condition_checks", [])
    for col, item in zip(cols[1:], checks[:4]):
        passed = bool(item.get("passed"))
        with col:
            render_kpi_card(
                str(item.get("label", "-")),
                "OK" if passed else "NO",
                tone="buy" if passed else "avoid",
                detail=str(item.get("detail", ""))[:80],
            )
    if len(checks) > 4:
        more_cols = st.columns(3)
        for col, item in zip(more_cols, checks[4:7]):
            passed = bool(item.get("passed"))
            with col:
                render_kpi_card(
                    str(item.get("label", "-")),
                    "OK" if passed else "NO",
                    tone="buy" if passed else "avoid",
                    detail=str(item.get("detail", ""))[:110],
                )


def render_trade_plan_platform_preview(ticket: dict) -> None:
    if not ticket:
        return
    raw_status = str(ticket.get("status") or "-")
    status = platform_status_label(raw_status)
    tone = "buy" if raw_status == "READY_TO_PREVIEW" else "watch" if raw_status == "WAIT_FOR_CONFIRMATION" else "avoid"
    st.markdown("**Ruta manual a plataforma**")
    cols = st.columns([1.1, 0.9, 1.0, 1.1, 0.8, 0.8])
    with cols[0]:
        render_kpi_card("Plataforma", ticket.get("platform", "-"), tone=tone)
    with cols[1]:
        render_kpi_card("Producto", asset_type_label(ticket.get("asset_type")), tone=tone)
    with cols[2]:
        render_kpi_card("Estado", status, tone=tone)
    with cols[3]:
        render_kpi_card("Orden", ticket.get("order_symbol", "-"))
    with cols[4]:
        render_kpi_card("Qty", num_display(ticket.get("quantity"), 4))
    with cols[5]:
        render_kpi_card("Riesgo $", num_display(ticket.get("risk_dollars")))

    reason = platform_reason_label(ticket.get("status_reason"))
    note = text_display(ticket.get("platform_note"))
    if tone == "buy":
        st.success(reason)
    elif tone == "avoid":
        st.warning(reason)
    else:
        st.info(reason)
    if note != "-":
        st.caption(note)

    option_quality = ticket.get("option_quality") or {}
    if option_quality:
        visible = {key: value for key, value in option_quality.items() if text_display(value) != "-"}
        if visible:
            st.caption(
                "Opcion: "
                + " | ".join(
                    f"{key}={num_display(value) if isinstance(value, (int, float)) else value}" for key, value in visible.items()
                )
            )

    guardrail = ticket.get("risk_guardrail") or {}
    if guardrail:
        guard_tone = "buy" if guardrail.get("allowed") else "avoid"
        guard_cols = st.columns(4)
        with guard_cols[0]:
            render_kpi_card("Control riesgo", platform_status_label(guardrail.get("status", "-")), tone=guard_tone)
        with guard_cols[1]:
            render_kpi_card("1R", num_display(guardrail.get("per_trade_budget")))
        with guard_cols[2]:
            render_kpi_card("2R diario", num_display(guardrail.get("daily_stop")), tone="avoid")
        with guard_cols[3]:
            render_kpi_card("Riesgo libre", num_display(guardrail.get("remaining_daily_risk")), tone=guard_tone)
        st.caption(str(guardrail.get("message") or ""))

    product_plan = ticket.get("small_account_plan") or {}
    if product_plan:
        product_tone = "buy" if product_plan.get("allowed") else "avoid"
        product_cols = st.columns(4)
        with product_cols[0]:
            render_kpi_card("Cuenta pequena", product_plan.get("recommendation", "-"), tone=product_tone)
        with product_cols[1]:
            render_kpi_card("Riesgo max", num_display(product_plan.get("risk_budget")), tone=product_tone)
        with product_cols[2]:
            render_kpi_card("Unidades", num_display(product_plan.get("whole_shares") or product_plan.get("units"), 4))
        with product_cols[3]:
            option_label = "OK" if product_plan.get("option_allowed") else "NO"
            render_kpi_card("Opcion", option_label, tone="buy" if product_plan.get("option_allowed") else "watch")
        st.caption(str(product_plan.get("message") or ""))
        option_message = text_display(product_plan.get("option_message"))
        if option_message != "-":
            st.caption(option_message)
        st.caption(str(product_plan.get("next_step") or ""))

    with st.expander("Ticket preview JSON", expanded=False):
        payload = {
            "platform": ticket.get("platform"),
            "asset_type": ticket.get("asset_type"),
            "order_symbol": ticket.get("order_symbol"),
            "side": ticket.get("side"),
            "order_type": ticket.get("order_type"),
            "time_in_force": ticket.get("time_in_force"),
            "entry": ticket.get("entry"),
            "stop": ticket.get("stop"),
            "target_price": ticket.get("target_price"),
            "risk_dollars": ticket.get("risk_dollars"),
            "quantity": ticket.get("quantity"),
            "status": ticket.get("status"),
            "execution_gate": ticket.get("execution_gate"),
            "manual_only": ticket.get("manual_only"),
            "risk_guardrail": ticket.get("risk_guardrail"),
            "small_account_plan": ticket.get("small_account_plan"),
        }
        st.code(json.dumps(payload, indent=2), language="json")


def show_sma_symbol_analyzer(scan_df: pd.DataFrame, confluence_df: pd.DataFrame, options_df: pd.DataFrame) -> None:
    st.subheader("Analizador por simbolo")
    control_cols = st.columns([1.2, 0.8, 0.8, 0.8])
    with control_cols[0]:
        query = st.text_input("Simbolo o compania", value="AAPL", key="sma_symbol_query")
    with control_cols[1]:
        market = st.selectbox("Mercado", ["stock", "crypto"], key="sma_symbol_market")
    with control_cols[2]:
        timeframe = st.selectbox("Marco", TIMEFRAME_OPTIONS, index=1, key="sma_symbol_tf")
    with control_cols[3]:
        run = st.button("Analizar simbolo", key="sma_symbol_analyze")

    risk_cols = st.columns([1, 1, 2])
    with risk_cols[0]:
        account_equity = st.number_input(
            "Capital de cuenta",
            min_value=100.0,
            value=float(DEFAULT_ACCOUNT_EQUITY),
            step=50.0,
            key="sma_account_equity",
        )
    with risk_cols[1]:
        risk_per_trade_pct = st.number_input(
            "Riesgo por trade %",
            min_value=0.1,
            max_value=5.0,
            value=1.0,
            step=0.1,
            key="sma_risk_per_trade_pct",
        )

    symbol = resolve_symbol_query(query, market)
    if not run:
        st.caption("Ejemplo: escribe Apple o AAPL, elige 1h o 15m y analiza el simbolo.")
        return
    if not symbol:
        st.warning("Primero escribe un simbolo.")
        return

    with st.spinner(f"Analizando {symbol} con SMA 20/40/100/200..."):
        try:
            history = fetch_symbol_history(symbol, market=market, timeframe=timeframe)
            chart_df = prepare_symbol_chart_data(history)
            setup = analyze_moving_average_setup(history) if not history.empty else {}
        except Exception as exc:
            st.error(f"No se pudo analizar {symbol}: {exc}")
            return

    if chart_df.empty or not setup:
        st.warning(f"No hay suficiente historial de precio para {symbol}.")
        return

    signal = text_display(setup.get("signal"))
    setup_name = text_display(setup.get("setup"))
    risk_pct = setup_risk_pct(setup)
    confluence = latest_confluence_row(confluence_df, symbol)
    confluence_signal = text_display(confluence.get("signal")) if confluence else "-"
    trade_decision = text_display(confluence.get("trade_decision")) if confluence else "-"

    metric_cols = st.columns(6)
    with metric_cols[0]:
        render_kpi_card("Simbolo", symbol)
    with metric_cols[1]:
        render_kpi_card("Senal / setup", f"{signal} | {setup_name}", tone=signal_tone(signal))
    with metric_cols[2]:
        render_kpi_card("Score", num_display(setup.get("score"), 0))
    with metric_cols[3]:
        render_kpi_card("Entrada", num_display(setup.get("entry")))
    with metric_cols[4]:
        render_kpi_card("Stop", num_display(setup.get("stop")))
    with metric_cols[5]:
        render_kpi_card(
            "Riesgo",
            pct_display(risk_pct),
            tone="avoid" if risk_pct is not None and risk_pct > 0.03 else "neutral",
            detail="Alto" if risk_pct is not None and risk_pct > 0.03 else None,
        )

    if confluence:
        confluence_cols = st.columns(5)
        with confluence_cols[0]:
            render_kpi_card("Confluencia", confluence_signal, tone=signal_tone(confluence_signal))
        with confluence_cols[1]:
            render_kpi_card("Decision", trade_decision, tone=signal_tone(trade_decision))
        with confluence_cols[2]:
            render_kpi_card("Score confluencia", num_display(confluence.get("confluence_score"), 0))
        with confluence_cols[3]:
            render_kpi_card("Objetivo", pct_display(confluence.get("recommended_target_pct")))
        with confluence_cols[4]:
            render_kpi_card("Precio objetivo", num_display(confluence.get("recommended_target_price")))

        if signal == "BUY" and not (confluence_signal == "BUY" and str(trade_decision).startswith("TRADE_FOR")):
            st.warning(
                "Setup fuerte en la grafica, pero 15m/1h todavia no confirma entrada. "
                "Tratalo como watchlist; para opciones espera confluence BUY."
            )
        elif signal == "BUY":
            st.success("Setup y confluence alineados. La entrada se maneja con stop, objetivo y tamano controlado.")
    elif signal == "BUY":
        st.info("Setup fuerte, pero no hay confluence 15m/1h para este simbolo. Espera confirmacion intradia antes de opciones.")

    ai_trade_brief = build_symbol_trade_brief(
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        setup=setup,
        confluence=confluence,
        options_df=options_df,
        account_equity=float(account_equity),
        account_risk_pct=float(risk_per_trade_pct) / 100.0,
        memory=load_memory(),
    )
    render_ai_trade_brief(ai_trade_brief)
    render_operation_gate(ai_trade_brief)

    playbook = classify_strategy_playbook(setup, confluence=confluence, market=market, timeframe=timeframe)
    st.markdown("**Manual de estrategia**")
    playbook_cols = st.columns([1, 1, 1.3, 1.5, 1.5])
    with playbook_cols[0]:
        render_kpi_card("Regimen", playbook["regime"])
    with playbook_cols[1]:
        render_kpi_card("Estrategia", playbook["strategy"])
    with playbook_cols[2]:
        render_kpi_card("Regla entrada", playbook["entry_rule"])
    with playbook_cols[3]:
        render_kpi_card("Plan accion", playbook["stock_plan"], tone=signal_tone(signal))
    with playbook_cols[4]:
        render_kpi_card("Plan opciones", playbook["options_plan"], tone="watch" if market == "stock" else "neutral")

    reference_rows = detect_reference_strategies(chart_df, setup)
    render_strategy_checklist(reference_rows)

    st.markdown("**Grafica profesional de estrategia**")
    st.caption(
        "Velas, nube de volatilidad, EMA9, SMA20/40/100/200, soporte/resistencia, zona de entrada, stop, objetivos 2%/5%/10% y volumen."
    )
    render_chart_readout(setup, confluence, ai_trade_brief, chart_df)
    render_chart_strategy_summary(setup, confluence, ai_trade_brief, chart_df)
    price_chart = build_professional_price_chart(
        chart_df,
        setup,
        confluence,
        ai_trade_brief,
        paper_snapshot=st.session_state.get("alpaca_paper_journal_snapshot"),
        symbol=symbol,
    ).properties(height=460)
    volume_chart = build_professional_volume_chart(chart_df)
    oscillator_chart = build_professional_oscillator_chart(chart_df)
    chart_panels = [price_chart]
    if volume_chart is not None:
        chart_panels.append(volume_chart.properties(height=130))
    if oscillator_chart is not None:
        chart_panels.append(oscillator_chart.properties(height=115))
    if len(chart_panels) > 1:
        combined_chart = alt.vconcat(*chart_panels).resolve_scale(x="shared")
        st.altair_chart(
            style_trading_chart(combined_chart),
            width="stretch",
        )
    else:
        st.altair_chart(style_trading_chart(price_chart), width="stretch")

    reasons = setup.get("reasons") or []
    if reasons:
        st.markdown("**Strategy read:** " + " · ".join(str(reason) for reason in reasons[:6]))

    scan_rows = latest_symbol_rows(scan_df, symbol)
    if not scan_rows.empty:
        cols = [
            "market",
            "symbol",
            "tf",
            "signal",
            "raw_signal",
            "setup",
            "score",
            "close",
            "sma20",
            "sma40",
            "sma100",
            "sma200",
            "relative_volume",
            "atr_pct",
            "backtest_eligible",
        ]
        cols = [col for col in cols if col in scan_rows.columns]
        st.dataframe(scan_rows[cols], width="stretch")

    if market == "stock" and not options_df.empty and "symbol" in options_df.columns:
        symbol_options = options_df[options_df["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
        if not symbol_options.empty:
            st.markdown("**Option candidates for this symbol**")
            option_cols = [
                "contractSymbol",
                "option_decision",
                "option_score",
                "expiry",
                "dte",
                "strike",
                "bid",
                "ask",
                "spread_pct",
                "target_pct",
                "breakeven_pct",
                "max_loss_per_contract",
            ]
            option_cols = [col for col in option_cols if col in symbol_options.columns]
            st.dataframe(symbol_options[option_cols], width="stretch")


def show_sma_strategy_tab() -> None:
    st.header("SMA 20/40/100/200 Strategy")

    daily_scan_path, daily_scan_df = load_latest_ma_scan("ma_strategy")
    live_scan_path, live_scan_df = load_latest_ma_scan("ma_live_strategy")
    confluence_path, confluence_df = load_latest_ma_confluence()
    options_path, options_df = load_latest_options_candidates()
    daily_summary = read_summary_json("alerts/ma_daily_summary.json")
    live_summary = read_summary_json("alerts/ma_live_summary.json")
    confluence_summary = read_summary_json("alerts/ma_confluence_summary.json")
    options_summary = read_summary_json("alerts/options_summary.json")

    source_options = [LIVE_SOURCE_LABEL, "Daily 1d"] if live_scan_path else ["Daily 1d"]
    selected_source = st.radio("Source", source_options, horizontal=True)
    if selected_source == LIVE_SOURCE_LABEL:
        scan_path, scan_df = live_scan_path, live_scan_df
        summary = live_summary
        report_path = Path("alerts/ma_live_report.txt")
    else:
        scan_path, scan_df = daily_scan_path, daily_scan_df
        summary = daily_summary
        report_path = Path("alerts/ma_daily_report.txt")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Rows", summary.get("rows", len(scan_df) if not scan_df.empty else 0))
    with col2:
        st.metric("BUY", summary.get("buy_count", 0))
    with col3:
        st.metric("Raw BUY", summary.get("raw_signal_counts", {}).get("BUY", 0))
    with col4:
        st.metric("Downgraded", summary.get("filtered_buy_count", 0))
    with col5:
        st.metric("Confluence BUY", confluence_summary.get("buy_count", 0) if selected_source == LIVE_SOURCE_LABEL else 0)
    with col6:
        st.metric("Options", options_summary.get("candidate_count", 0) if selected_source == LIVE_SOURCE_LABEL else 0)

    controls = st.columns([1, 1, 1, 2])
    with controls[0]:
        if st.button("Run SMA Daily"):
            try:
                import subprocess
                import sys

                with st.spinner("Running daily SMA workflow..."):
                    result = subprocess.run(
                        [sys.executable, "tools/ma_daily.py"],
                        cwd=Path(__file__).resolve().parent,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                if result.returncode == 0:
                    st.success("Daily workflow completed")
                    if result.stdout:
                        st.code(result.stdout)
                else:
                    st.error("Daily workflow failed")
                    st.code(result.stderr or result.stdout)
            except Exception as e:
                st.error(f"Failed to run daily workflow: {e}")
    with controls[1]:
        if st.button("Run SMA Live Once"):
            try:
                import subprocess
                import sys

                with st.spinner("Running live SMA cycle..."):
                    result = subprocess.run(
                        [sys.executable, "tools/ma_live.py", "--once"],
                        cwd=Path(__file__).resolve().parent,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                if result.returncode == 0:
                    st.success("Live cycle completed")
                    if result.stdout:
                        st.code(result.stdout)
                else:
                    st.error("Live cycle failed")
                    st.code(result.stderr or result.stdout)
            except Exception as e:
                st.error(f"Failed to run live cycle: {e}")
    with controls[2]:
        if st.button("Refresh Report"):
            try:
                import subprocess
                import sys

                cmd = [sys.executable, "tools/ma_report.py"]
                if scan_path:
                    cmd.extend(["--scan-csv", scan_path])
                result = subprocess.run(
                    cmd,
                    cwd=Path(__file__).resolve().parent,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    st.success("Report refreshed")
                else:
                    st.error(result.stderr or result.stdout)
            except Exception as e:
                st.error(f"Failed to refresh report: {e}")
    with controls[3]:
        if scan_path:
            st.caption(f"Latest scan: {scan_path}")
        else:
            st.caption("No SMA scan CSV found.")

    if scan_df.empty:
        st.info("No SMA scan data found. Run the daily workflow or one live cycle to create the first report.")
        return

    if selected_source == LIVE_SOURCE_LABEL:
        brief = best_confluence_candidate(confluence_df)
        st.subheader("Decision Brief")
        if brief:
            decision = text_display(brief.get("trade_decision"))
            signal = text_display(brief.get("signal"))
            symbol = text_display(brief.get("symbol"))
            market = text_display(brief.get("market"))

            status_cols = st.columns([1.2, 1.1, 0.8, 0.8, 0.8, 1.2])
            with status_cols[0]:
                st.metric("Focus", f"{market} {symbol}")
            with status_cols[1]:
                if decision.startswith("TRADE_FOR") or signal == "BUY":
                    st.success(f"{signal} | {decision}")
                elif signal == "WATCH":
                    st.info(f"{signal} | {decision}")
                else:
                    st.warning(f"{signal} | {decision}")
            with status_cols[2]:
                st.metric("Score", num_display(brief.get("confluence_score"), 0))
            with status_cols[3]:
                st.metric("Risk", pct_display(brief.get("risk_pct")))
            with status_cols[4]:
                st.metric("Target", pct_display(brief.get("recommended_target_pct")))
            with status_cols[5]:
                st.metric("Target Price", num_display(brief.get("recommended_target_price")))

            plan_cols = st.columns([1, 1, 2])
            with plan_cols[0]:
                st.metric("Entry", num_display(brief.get("entry")))
            with plan_cols[1]:
                st.metric("Stop", num_display(brief.get("stop")))
            with plan_cols[2]:
                st.caption(text_display(brief.get("exit_plan")))
        else:
            st.info("No confluence data found yet.")

    show_sma_symbol_analyzer(scan_df, confluence_df, options_df)

    table_tabs = st.tabs(["Signals", "Confluence", "Options", "Downgraded", "Eligible Watch", "Report"])

    display_cols = [
        "market",
        "symbol",
        "tf",
        "signal",
        "raw_signal",
        "backtest_eligible",
        "setup",
        "score",
        "close",
        "stop",
        "backtest_total_return_pct",
        "backtest_buy_hold_edge_pct",
        "backtest_profit_factor",
        "backtest_trades",
    ]
    display_cols = [col for col in display_cols if col in scan_df.columns]

    with table_tabs[0]:
        chart_cols = st.columns([1, 1])
        signal_mix = signal_counts_by_timeframe(scan_df)
        setup_mix = setup_counts_by_timeframe(scan_df)
        with chart_cols[0]:
            if not signal_mix.empty:
                signal_chart = (
                    alt.Chart(signal_mix)
                    .mark_bar()
                    .encode(
                        x=alt.X("tf:N", title="Timeframe", sort=None),
                        y=alt.Y("count:Q", title="Rows"),
                        color=alt.Color(
                            "signal:N",
                            title="Signal",
                            scale=alt.Scale(
                                domain=["BUY", "WATCH", "AVOID"],
                                range=["#16a34a", "#f59e0b", "#dc2626"],
                            ),
                        ),
                        tooltip=["tf:N", "signal:N", "count:Q"],
                    )
                )
                st.altair_chart(signal_chart.properties(height=260), width="stretch")
        with chart_cols[1]:
            if not setup_mix.empty:
                setup_chart = (
                    alt.Chart(setup_mix)
                    .mark_bar()
                    .encode(
                        x=alt.X("count:Q", title="Rows"),
                        y=alt.Y("setup:N", title="Setup", sort="-x"),
                        color=alt.Color("tf:N", title="Timeframe", scale=alt.Scale(range=["#2563eb", "#14b8a6"])),
                        tooltip=["tf:N", "setup:N", "count:Q"],
                    )
                )
                st.altair_chart(setup_chart.properties(height=260), width="stretch")

        score_points = score_distribution(scan_df)
        if not score_points.empty:
            score_chart = (
                alt.Chart(score_points)
                .mark_bar(opacity=0.85)
                .encode(
                    x=alt.X("score:Q", bin=alt.Bin(step=10), title="Score"),
                    y=alt.Y("count():Q", title="Rows"),
                    color=alt.Color(
                        "signal:N",
                        title="Signal",
                        scale=alt.Scale(domain=["BUY", "WATCH", "AVOID"], range=["#16a34a", "#f59e0b", "#dc2626"]),
                    ),
                    tooltip=["signal:N", "count():Q"],
                )
            )
            st.altair_chart(score_chart.properties(height=200), width="stretch")

        signals = scan_df.copy()
        if "signal" in signals.columns:
            selected_signal = st.selectbox(
                "Signal", options=["All"] + sorted(signals["signal"].dropna().unique().tolist())
            )
            if selected_signal != "All":
                signals = signals[signals["signal"] == selected_signal]
        st.dataframe(signals[display_cols], width="stretch")

    confluence_cols = [
        "market",
        "symbol",
        "signal",
        "action",
        "trade_decision",
        "confluence_score",
        "recommended_target_pct",
        "recommended_target_price",
        "entry",
        "stop",
        "risk_pct",
        "risk_level",
        "target_2pct_ok",
        "target_2pct_price",
        "target_2pct_reward_r",
        "target_5pct_ok",
        "target_5pct_price",
        "target_5pct_reward_r",
        "target_10pct_ok",
        "target_10pct_price",
        "target_10pct_reward_r",
        "target_1r",
        "target_2r",
        "relative_volume_15m",
        "atr_pct_15m",
        "trigger_setup",
        "trigger_score",
        "trend_setup",
        "trend_score",
        "higher_tf_bias",
        "higher_tf_confirmations",
        "higher_tf_blocks",
        "higher_tf_score",
        "htf_2h_signal",
        "htf_2h_setup",
        "htf_2h_score",
        "htf_4h_signal",
        "htf_4h_setup",
        "htf_4h_score",
        "backtest_eligible",
        "reasons",
    ]
    confluence_cols = [col for col in confluence_cols if col in confluence_df.columns]

    with table_tabs[1]:
        confluence_report_path = Path("alerts/ma_confluence_report.txt")
        if selected_source != LIVE_SOURCE_LABEL:
            st.info("Confluence is built from the live intraday scan.")
        elif confluence_df.empty:
            st.info("No confluence data found yet.")
        else:
            st.caption(f"Latest confluence: {confluence_path}")
            confluence_chart_cols = st.columns([1, 1])
            target_counts = target_ladder_counts(confluence_df)
            with confluence_chart_cols[0]:
                target_chart = (
                    alt.Chart(target_counts)
                    .mark_bar()
                    .encode(
                        x=alt.X("target:N", title="Target", sort=["2%", "5%", "10%"]),
                        y=alt.Y("count:Q", title="Setups"),
                        color=alt.Color(
                            "target:N", legend=None, scale=alt.Scale(range=["#16a34a", "#0891b2", "#7c3aed"])
                        ),
                        tooltip=["target:N", "count:Q"],
                    )
                )
                st.altair_chart(target_chart.properties(height=230), width="stretch")
            with confluence_chart_cols[1]:
                decision_counts = trade_decision_counts(confluence_df)
                if not decision_counts.empty:
                    decision_chart = (
                        alt.Chart(decision_counts)
                        .mark_bar()
                        .encode(
                            x=alt.X("count:Q", title="Setups"),
                            y=alt.Y("trade_decision:N", title="Decision", sort="-x"),
                            color=alt.value("#475569"),
                            tooltip=["trade_decision:N", "count:Q"],
                        )
                    )
                    st.altair_chart(decision_chart.properties(height=230), width="stretch")
                if "higher_tf_bias" in confluence_df.columns:
                    htf_counts = (
                        confluence_df["higher_tf_bias"]
                        .fillna("NO_DATA")
                        .astype(str)
                        .str.upper()
                        .value_counts()
                        .rename_axis("higher_tf_bias")
                        .reset_index(name="count")
                    )
                    htf_chart = (
                        alt.Chart(htf_counts)
                        .mark_bar()
                        .encode(
                            x=alt.X("count:Q", title="Setups"),
                            y=alt.Y("higher_tf_bias:N", title="2h/4h", sort="-x"),
                            color=alt.Color(
                                "higher_tf_bias:N",
                                legend=None,
                                scale=alt.Scale(
                                    domain=["CONFIRMED", "PARTIAL", "BLOCKED", "NO_DATA"],
                                    range=["#16a34a", "#f59e0b", "#dc2626", "#94a3b8"],
                                ),
                            ),
                            tooltip=["higher_tf_bias:N", "count:Q"],
                        )
                    )
                    st.altair_chart(htf_chart.properties(height=190), width="stretch")

            risk_points = risk_score_points(confluence_df)
            if not risk_points.empty:
                risk_chart = (
                    alt.Chart(risk_points)
                    .mark_circle(size=110, opacity=0.82)
                    .encode(
                        x=alt.X("risk_display_pct:Q", title="Risk % to Stop"),
                        y=alt.Y("confluence_score:Q", title="Confluence Score", scale=alt.Scale(domain=[0, 100])),
                        color=alt.Color(
                            "signal:N",
                            title="Signal",
                            scale=alt.Scale(domain=["BUY", "WATCH", "AVOID"], range=["#16a34a", "#f59e0b", "#dc2626"]),
                        ),
                        tooltip=[
                            "market:N",
                            "symbol:N",
                            "signal:N",
                            "trade_decision:N",
                            alt.Tooltip("risk_display_pct:Q", title="Risk %", format=".2f"),
                            alt.Tooltip("confluence_score:Q", title="Score", format=".0f"),
                        ],
                    )
                )
                st.altair_chart(risk_chart.properties(height=280), width="stretch")
            st.dataframe(confluence_df[confluence_cols], width="stretch")
        if confluence_report_path.exists():
            with st.expander("Confluence report"):
                st.text(confluence_report_path.read_text())

    with table_tabs[2]:
        options_report_path = Path("alerts/options_report.txt")
        option_cols = [
            "symbol",
            "contractSymbol",
            "option_decision",
            "option_score",
            "expiry",
            "dte",
            "strike",
            "bid",
            "ask",
            "spread_pct",
            "volume",
            "openInterest",
            "moneyness_pct",
            "target_pct",
            "target_reaches_strike",
            "breakeven_pct",
            "max_loss_per_contract",
            "underlying_trade_decision",
            "underlying_confluence_score",
        ]
        option_cols = [col for col in option_cols if col in options_df.columns]
        if selected_source != LIVE_SOURCE_LABEL:
            st.info("Options candidates are built from the live confluence trade plan.")
        elif options_df.empty:
            st.info(
                "No options candidates found. The scanner only fetches contracts when confluence has actionable stock BUY setups."
            )
        else:
            st.caption(f"Latest options scan: {options_path}")
            option_chart_cols = st.columns([1, 1])
            quality_points = option_quality_points(options_df)
            with option_chart_cols[0]:
                if not quality_points.empty:
                    quality_chart = (
                        alt.Chart(quality_points)
                        .mark_circle(size=95, opacity=0.82)
                        .encode(
                            x=alt.X("spread_display_pct:Q", title="Spread %"),
                            y=alt.Y("option_score:Q", title="Option Score", scale=alt.Scale(domain=[0, 100])),
                            color=alt.Color(
                                "option_decision:N",
                                title="Decision",
                                scale=alt.Scale(range=["#16a34a", "#f59e0b", "#64748b"]),
                            ),
                            tooltip=[
                                "symbol:N",
                                "contractSymbol:N",
                                "option_decision:N",
                                alt.Tooltip("spread_display_pct:Q", title="Spread %", format=".2f"),
                                alt.Tooltip("option_score:Q", title="Score", format=".0f"),
                                alt.Tooltip("dte:Q", title="DTE", format=".0f"),
                            ],
                        )
                    )
                    st.altair_chart(quality_chart.properties(height=250), width="stretch")
            with option_chart_cols[1]:
                expiry_counts = option_expiry_counts(options_df)
                if not expiry_counts.empty:
                    expiry_chart = (
                        alt.Chart(expiry_counts)
                        .mark_bar()
                        .encode(
                            x=alt.X("expiry:N", title="Expiry", sort=None),
                            y=alt.Y("count:Q", title="Contracts"),
                            color=alt.value("#0891b2"),
                            tooltip=["expiry:N", "count:Q"],
                        )
                    )
                    st.altair_chart(expiry_chart.properties(height=250), width="stretch")
            st.dataframe(options_df[option_cols], width="stretch")
        if options_report_path.exists():
            with st.expander("Options report"):
                st.text(options_report_path.read_text())

    with table_tabs[3]:
        if {"raw_signal", "signal"}.issubset(scan_df.columns):
            downgraded = scan_df[(scan_df["raw_signal"] == "BUY") & (scan_df["signal"] != "BUY")]
        else:
            downgraded = pd.DataFrame()
        st.write(f"{len(downgraded)} raw BUY signals were downgraded by the historical filter.")
        if not downgraded.empty:
            st.dataframe(downgraded[display_cols], width="stretch")

    with table_tabs[4]:
        if "backtest_eligible" in scan_df.columns:
            eligible = scan_df[scan_df["backtest_eligible"].astype(bool) & (scan_df["signal"] != "BUY")]
        else:
            eligible = pd.DataFrame()
        st.write(f"{len(eligible)} historically eligible symbols are not BUY today.")
        if not eligible.empty:
            st.dataframe(eligible[display_cols], width="stretch")

    with table_tabs[5]:
        if report_path.exists():
            st.text(report_path.read_text())
        else:
            st.info("No SMA daily report found.")
        if summary:
            with st.expander("Summary JSON"):
                st.json(summary)


def run_local_command(args: list[str]) -> tuple[int, str]:
    import subprocess
    import sys

    command = [sys.executable, *args]
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parent,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    return result.returncode, output.strip()


def latest_timestamp(paths: list[str | None]) -> str:
    existing = [Path(path) for path in paths if path and Path(path).exists()]
    if not existing:
        return "-"
    latest = max(existing, key=lambda path: path.stat().st_mtime)
    return datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def file_age_minutes(path: str | None, *, now: datetime | None = None) -> float | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    now = now or datetime.now()
    age_seconds = (now - datetime.fromtimestamp(file_path.stat().st_mtime)).total_seconds()
    return max(0.0, age_seconds / 60.0)


def data_freshness_status(
    paths: list[str | None],
    *,
    max_age_minutes: float = 10.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    ages = [file_age_minutes(path, now=now) for path in paths if path]
    ages = [age for age in ages if age is not None]
    if not ages:
        return {
            "label": "Sin datos",
            "tone": "avoid",
            "age_minutes": None,
            "detail": "Live/confluencia no encontrados",
        }

    age = max(ages)
    if age <= max_age_minutes:
        label = "Frescos"
        tone = "buy"
    elif age <= max_age_minutes * 3:
        label = "Revisar"
        tone = "watch"
    else:
        label = "Estancados"
        tone = "avoid"

    return {
        "label": label,
        "tone": tone,
        "age_minutes": age,
        "detail": f"{age:.0f} min",
    }


def timeframe_minutes(timeframe: str) -> int:
    return shared_timeframe_minutes(timeframe)


def latest_chart_timestamp(chart_df: pd.DataFrame) -> pd.Timestamp | None:
    return shared_latest_chart_timestamp(chart_df)


def chart_freshness_status(
    chart_df: pd.DataFrame,
    *,
    market: str,
    timeframe: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    return shared_chart_freshness_status(chart_df, market=market, timeframe=timeframe, now=now)


def live_service_state() -> dict[str, str]:
    try:
        from tools import ma_live_launchd

        label = ma_live_launchd.DEFAULT_LABEL
        path = ma_live_launchd.plist_path_for_label(label)
        loaded = ma_live_launchd.is_loaded(label)
        return {
            "label": label,
            "installed": "yes" if path.exists() else "no",
            "loaded": "yes" if loaded else "no",
            "path": str(path),
        }
    except Exception:
        return {"label": "com.roxy.ma_live", "installed": "unknown", "loaded": "unknown", "path": "-"}


def live_backend_status(
    live_path: str | None,
    confluence_path: str | None,
    *,
    service_state: dict[str, str] | None = None,
    heartbeat: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    state = service_state or live_service_state()
    freshness = data_freshness_status([live_path, confluence_path], max_age_minutes=10.0, now=now)
    loaded = state.get("loaded") == "yes"
    installed = state.get("installed") == "yes"
    heartbeat = heartbeat or {}
    heartbeat_status = text_display(heartbeat.get("status")).upper()
    heartbeat_error = text_display(heartbeat.get("error"))
    heartbeat_error = "" if heartbeat_error == "-" else heartbeat_error
    duration = safe_float(heartbeat.get("duration_seconds"))
    duration_text = f" | {duration:.1f}s" if duration is not None else ""

    if heartbeat_status == "RUNNING":
        return {
            "label": "Corriendo",
            "tone": "watch",
            "detail": f"Backend ejecutando scan live{duration_text}",
            "loaded": loaded,
            "installed": installed,
            "freshness": freshness,
            "heartbeat": heartbeat,
        }
    if heartbeat_status == "FAILED":
        return {
            "label": "Fallo",
            "tone": "avoid",
            "detail": heartbeat_error or "Ultima corrida live fallo",
            "loaded": loaded,
            "installed": installed,
            "freshness": freshness,
            "heartbeat": heartbeat,
        }
    if heartbeat_status == "NO_SCAN":
        return {
            "label": "Sin CSV",
            "tone": "avoid",
            "detail": heartbeat_error or "Ultima corrida no produjo scan",
            "loaded": loaded,
            "installed": installed,
            "freshness": freshness,
            "heartbeat": heartbeat,
        }

    if loaded and freshness["tone"] == "buy":
        label = "Operativo"
        tone = "buy"
        detail = f"24h ON | {freshness['detail']}{duration_text}"
    elif loaded:
        label = "Atrasado"
        tone = freshness["tone"]
        detail = f"24h ON | {freshness['detail']}{duration_text}"
    elif freshness["tone"] == "buy":
        label = "Manual fresco"
        tone = "watch"
        detail = f"24h OFF | {freshness['detail']}{duration_text}"
    elif installed:
        label = "Instalado OFF"
        tone = "watch"
        detail = freshness["detail"]
    else:
        label = "24h OFF"
        tone = "avoid"
        detail = freshness["detail"]

    return {
        "label": label,
        "tone": tone,
        "detail": detail,
        "loaded": loaded,
        "installed": installed,
        "freshness": freshness,
        "heartbeat": heartbeat,
    }


def realtime_check_status(report: dict[str, Any] | None) -> dict[str, str]:
    if not report:
        return {"label": "No corrido", "tone": "watch", "detail": "Ejecuta verificacion RT"}
    status = text_display(report.get("status")).upper()
    checks = report.get("checks") or []
    fail_count = sum(1 for item in checks if str(item.get("status") or "").upper() == "FAIL")
    warn_count = sum(1 for item in checks if str(item.get("status") or "").upper() == "WARN")
    top_issue = next(
        (
            item
            for item in checks
            if str(item.get("status") or "").upper() in {"FAIL", "WARN"}
        ),
        None,
    )
    issue_detail = ""
    if top_issue:
        issue_detail = f"{text_display(top_issue.get('name'))}: {text_display(top_issue.get('detail'))}"
    if status == "OK":
        return {"label": "OK", "tone": "buy", "detail": f"{len(checks)} checks"}
    if status == "WARN":
        detail = issue_detail or f"{warn_count} warning(s)"
        return {"label": "Revisar", "tone": "watch", "detail": detail}
    if status == "FAIL":
        detail = issue_detail or f"{fail_count} fallo(s), {warn_count} warning(s)"
        return {"label": "Falla", "tone": "avoid", "detail": detail}
    return {"label": status or "Desconocido", "tone": "watch", "detail": f"{len(checks)} checks"}


def operational_mode_dashboard_status(
    realtime_report: dict[str, Any] | None,
    alert_quality_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    realtime_report = realtime_report or {}
    summary = realtime_report.get("operational_summary") if isinstance(realtime_report.get("operational_summary"), dict) else {}
    if summary:
        return {
            "label": text_display(summary.get("label") or summary.get("mode") or "-"),
            "tone": text_display(summary.get("tone") or "watch"),
            "detail": text_display(summary.get("detail") or summary.get("mode") or "-"),
            "mode": text_display(summary.get("mode")),
        }
    health = realtime_check_status(realtime_report)
    if health["tone"] == "avoid":
        return {"label": "Sistema falla", "tone": "avoid", "detail": health["detail"], "mode": "SYSTEM_FAIL"}
    if health["tone"] == "watch":
        return {"label": "Sistema revisar", "tone": "watch", "detail": health["detail"], "mode": "SYSTEM_WARN"}
    quality = alert_quality_report_dashboard_status(alert_quality_report)
    if quality.get("state") == "READY":
        return {"label": "Alertas listas", "tone": "buy", "detail": quality["detail"], "mode": "READY_TO_REVIEW"}
    if quality.get("state") == "WAITING":
        return {"label": "Mercado espera", "tone": "watch", "detail": quality["detail"], "mode": "MARKET_WAITING"}
    return {"label": "Sistema OK", "tone": "buy", "detail": health["detail"], "mode": "SYSTEM_OK"}


def check_from_report(report: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if not report:
        return {}
    for item in report.get("checks") or []:
        if str(item.get("name") or "") == name:
            return dict(item)
    return {}


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.replace(tzinfo=None)
    return parsed


def output_maintenance_dashboard_status(
    realtime_report: dict[str, Any] | None,
    maintenance_report: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    check_item = check_from_report(realtime_report, "output_maintenance_report")
    maintenance_report = maintenance_report or {}
    status = text_display(check_item.get("status") or maintenance_report.get("status")).upper()
    if not status or status == "-":
        status = "OK" if maintenance_report else ""

    if status == "OK":
        label = "OK"
        tone = "buy"
    elif status == "FAIL":
        label = "Falla"
        tone = "avoid"
    elif status == "WARN":
        label = "Revisar"
        tone = "watch"
    else:
        label = "Sin reporte"
        tone = "watch"

    age_hours = safe_float(check_item.get("age_hours"))
    if age_hours is None and maintenance_report:
        generated = parse_iso_datetime(maintenance_report.get("generated_at"))
        if generated is not None:
            current = now or datetime.now()
            if current.tzinfo is not None:
                current = current.replace(tzinfo=None)
            age_hours = max(0.0, (current - generated).total_seconds() / 3600.0)

    removed_count = safe_float(check_item.get("removed_count"))
    if removed_count is None:
        removed_count = safe_float(maintenance_report.get("removed_count"))
    output_archive_count = safe_float(check_item.get("output_archive_count"))
    if output_archive_count is None:
        output_archive_count = safe_float(maintenance_report.get("output_archive_count"))
    output_archive_error_count = safe_float(check_item.get("output_archive_error_count"))
    if output_archive_error_count is None:
        output_archive_error_count = safe_float(maintenance_report.get("output_archive_error_count"))
    output_archive_dir = text_display(check_item.get("output_archive_dir") or maintenance_report.get("output_archive_dir"))
    prepared_dir_count = safe_float(maintenance_report.get("prepared_dir_count"))
    prepared_dir_error_count = safe_float(maintenance_report.get("prepared_dir_error_count"))
    output_archive_exists = bool(maintenance_report.get("output_archive_exists"))
    log_snapshot_dir_exists = bool(maintenance_report.get("log_snapshot_dir_exists"))
    stale_output_removed = safe_float(check_item.get("stale_output_removed_count"))
    if stale_output_removed is None:
        stale_output_removed = safe_float(maintenance_report.get("stale_output_removed_count"))
    trimmed_logs = safe_float(check_item.get("trimmed_log_count"))
    if trimmed_logs is None:
        trimmed_logs = safe_float(maintenance_report.get("trimmed_log_count"))
    trimmed_histories = safe_float(check_item.get("trimmed_history_count"))
    if trimmed_histories is None:
        trimmed_histories = safe_float(maintenance_report.get("trimmed_history_count"))
    removed_alert_reports = safe_float(check_item.get("removed_alert_report_count"))
    if removed_alert_reports is None:
        removed_alert_reports = safe_float(maintenance_report.get("removed_alert_report_count"))
    dry_run = bool(check_item.get("dry_run") or maintenance_report.get("dry_run"))
    if dry_run and tone == "buy":
        label = "Revisar"
        tone = "watch"
    if output_archive_error_count and tone == "buy":
        label = "Revisar"
        tone = "watch"
    if prepared_dir_error_count and tone == "buy":
        label = "Revisar"
        tone = "watch"

    details = []
    if age_hours is not None:
        details.append(f"{age_hours:.1f}h")
    if removed_count is not None:
        details.append(f"removidos {int(removed_count)}")
    if output_archive_count is not None:
        details.append(f"archivados {int(output_archive_count)}")
    if output_archive_error_count:
        details.append(f"errores archivo {int(output_archive_error_count)}")
    if prepared_dir_error_count:
        details.append(f"errores dirs {int(prepared_dir_error_count)}")
    elif output_archive_exists and log_snapshot_dir_exists:
        details.append("dirs OK")
    elif prepared_dir_count:
        details.append(f"dirs {int(prepared_dir_count)}")
    if stale_output_removed is not None:
        details.append(f"stale {int(stale_output_removed)}")
    if trimmed_logs is not None:
        details.append(f"logs {int(trimmed_logs)}")
    if trimmed_histories is not None:
        details.append(f"hist {int(trimmed_histories)}")
    if removed_alert_reports is not None:
        details.append(f"reportes {int(removed_alert_reports)}")
    if dry_run:
        details.append("dry-run")
    if check_item.get("detail") and not details:
        details.append(text_display(check_item.get("detail")))

    return {
        "label": label,
        "tone": tone,
        "detail": " | ".join(details) if details else "Ejecuta mantenimiento",
        "age_hours": age_hours,
        "removed_count": int(removed_count) if removed_count is not None else None,
        "output_archive_count": int(output_archive_count) if output_archive_count is not None else None,
        "output_archive_error_count": int(output_archive_error_count) if output_archive_error_count is not None else None,
        "output_archive_dir": output_archive_dir,
        "prepared_dir_count": int(prepared_dir_count) if prepared_dir_count is not None else None,
        "prepared_dir_error_count": int(prepared_dir_error_count) if prepared_dir_error_count is not None else None,
        "output_archive_exists": output_archive_exists,
        "log_snapshot_dir_exists": log_snapshot_dir_exists,
        "stale_output_removed_count": int(stale_output_removed) if stale_output_removed is not None else None,
        "trimmed_log_count": int(trimmed_logs) if trimmed_logs is not None else None,
        "trimmed_history_count": int(trimmed_histories) if trimmed_histories is not None else None,
        "removed_alert_report_count": int(removed_alert_reports) if removed_alert_reports is not None else None,
        "dry_run": dry_run,
        "check": check_item,
    }


def runtime_backup_dashboard_status(
    realtime_report: dict[str, Any] | None,
    backup_report: dict[str, Any] | None,
    daemon_heartbeat: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    check_item = check_from_report(realtime_report, "runtime_backup_report")
    service_item = check_from_report(realtime_report, "runtime_backup_service")
    backup_report = backup_report or {}
    daemon_heartbeat = daemon_heartbeat or {}
    status = text_display(check_item.get("status") or backup_report.get("status")).upper()
    if not status or status == "-":
        status = "OK" if backup_report else ""

    if status == "OK":
        label = "OK"
        tone = "buy"
    elif status == "FAIL":
        label = "Falla"
        tone = "avoid"
    elif status in {"WARN", "DRY_RUN"}:
        label = "Revisar"
        tone = "watch"
    else:
        label = "Sin reporte"
        tone = "watch"

    age_hours = safe_float(check_item.get("age_hours"))
    if age_hours is None and backup_report:
        generated = parse_iso_datetime(backup_report.get("generated_at"))
        if generated is not None:
            current = now or datetime.now()
            if current.tzinfo is not None:
                current = current.replace(tzinfo=None)
            age_hours = max(0.0, (current - generated).total_seconds() / 3600.0)

    archive_size = safe_float(check_item.get("archive_size_bytes"))
    if archive_size is None:
        archive_size = safe_float(backup_report.get("archive_size_bytes"))
    removed_count = safe_float(check_item.get("removed_count"))
    if removed_count is None:
        removed_count = safe_float(backup_report.get("removed_count"))
    dry_run = bool(check_item.get("dry_run") or backup_report.get("dry_run"))
    archive_exists = bool(check_item.get("archive_exists") if check_item else backup_report.get("archive_exists"))
    archive_verified = bool(check_item.get("archive_verified") if check_item else backup_report.get("archive_verified"))
    archive_member_count = safe_float(check_item.get("archive_member_count"))
    if archive_member_count is None:
        archive_member_count = safe_float(backup_report.get("archive_member_count"))
    verified_paths = check_item.get("archive_verified_paths") if check_item else backup_report.get("archive_verified_paths")
    if not isinstance(verified_paths, list):
        verified_paths = []
    if dry_run and tone == "buy":
        label = "Revisar"
        tone = "watch"

    daemon_status = text_display(daemon_heartbeat.get("status") or service_item.get("daemon_status")).upper()
    daemon_running = bool(service_item.get("daemon_running"))
    if not daemon_running and daemon_heartbeat:
        daemon_running = daemon_status in {"RUNNING", "DEGRADED"}
    last_backup_at = parse_iso_datetime(daemon_heartbeat.get("last_backup_at") or service_item.get("daemon_last_backup_at"))
    next_backup_at = parse_iso_datetime(daemon_heartbeat.get("next_backup_at") or service_item.get("daemon_next_backup_at"))
    current = now or datetime.now()
    if current.tzinfo is not None:
        current = current.replace(tzinfo=None)
    last_backup_age_hours = max(0.0, (current - last_backup_at).total_seconds() / 3600.0) if last_backup_at else None
    next_backup_in_hours = (next_backup_at - current).total_seconds() / 3600.0 if next_backup_at else None

    details = []
    if age_hours is not None:
        details.append(f"{age_hours:.1f}h")
    if daemon_running:
        details.append(f"daemon {daemon_status.lower() or 'running'}")
    elif daemon_heartbeat:
        details.append("daemon revisar")
        if tone == "buy":
            label = "Revisar"
            tone = "watch"
    if last_backup_age_hours is not None:
        details.append(f"last {last_backup_age_hours:.1f}h")
    if next_backup_in_hours is not None:
        if next_backup_in_hours >= 0:
            details.append(f"next {next_backup_in_hours:.1f}h")
        else:
            details.append(f"atrasado {abs(next_backup_in_hours):.1f}h")
            if tone == "buy":
                label = "Revisar"
                tone = "watch"
    if archive_size is not None:
        size_mb = float(archive_size) / (1024**2)
        details.append(f"{size_mb:.1f} MB")
    if removed_count is not None:
        details.append(f"rotados {int(removed_count)}")
    if archive_verified:
        if verified_paths:
            details.append(f"verificado {len(verified_paths)} rutas")
        elif archive_member_count is not None:
            details.append(f"verificado {int(archive_member_count)} archivos")
    if dry_run:
        details.append("dry-run")
    if not archive_exists and backup_report:
        details.append("archivo no encontrado")
    elif archive_exists and not archive_verified and not dry_run:
        details.append("sin verificar")
    if check_item.get("detail") and not details:
        details.append(text_display(check_item.get("detail")))

    return {
        "label": label,
        "tone": tone,
        "detail": " | ".join(details) if details else "Ejecuta backup",
        "age_hours": age_hours,
        "archive_size_bytes": int(archive_size) if archive_size is not None else None,
        "removed_count": int(removed_count) if removed_count is not None else None,
        "dry_run": dry_run,
        "archive_exists": archive_exists,
        "archive_verified": archive_verified,
        "archive_member_count": int(archive_member_count) if archive_member_count is not None else None,
        "archive_verified_paths": verified_paths,
        "daemon_running": daemon_running,
        "daemon_status": daemon_status,
        "last_backup_at": str(daemon_heartbeat.get("last_backup_at") or service_item.get("daemon_last_backup_at") or ""),
        "next_backup_at": str(daemon_heartbeat.get("next_backup_at") or service_item.get("daemon_next_backup_at") or ""),
        "last_backup_age_hours": last_backup_age_hours,
        "next_backup_in_hours": next_backup_in_hours,
        "check": check_item,
    }


def autoheal_dashboard_status(realtime_report: dict[str, Any] | None) -> dict[str, Any]:
    realtime_report = realtime_report or {}
    launchd = realtime_report.get("launchd_autoheal") if isinstance(realtime_report.get("launchd_autoheal"), dict) else {}
    backup = realtime_report.get("runtime_backup_autoheal") if isinstance(realtime_report.get("runtime_backup_autoheal"), dict) else {}
    backup_report_recovery = realtime_report.get("runtime_backup_report_autoheal") if isinstance(realtime_report.get("runtime_backup_report_autoheal"), dict) else {}
    streamlit_recovery = realtime_report.get("streamlit_app_autoheal") if isinstance(realtime_report.get("streamlit_app_autoheal"), dict) else {}
    chart_recovery = realtime_report.get("chart_health_autoheal") if isinstance(realtime_report.get("chart_health_autoheal"), dict) else {}
    live_data_recovery = realtime_report.get("live_data_autoheal") if isinstance(realtime_report.get("live_data_autoheal"), dict) else {}
    storage_recovery = realtime_report.get("storage_migration_autoheal") if isinstance(realtime_report.get("storage_migration_autoheal"), dict) else {}
    maintenance_recovery = realtime_report.get("output_maintenance_autoheal") if isinstance(realtime_report.get("output_maintenance_autoheal"), dict) else {}
    ai_brief_recovery = realtime_report.get("ai_brief_autoheal") if isinstance(realtime_report.get("ai_brief_autoheal"), dict) else {}
    alert_quality_recovery = realtime_report.get("alert_quality_autoheal") if isinstance(realtime_report.get("alert_quality_autoheal"), dict) else {}
    yfinance_cache_recovery = realtime_report.get("yfinance_cache_autoheal") if isinstance(realtime_report.get("yfinance_cache_autoheal"), dict) else {}
    if not launchd and not backup and not backup_report_recovery and not streamlit_recovery and not chart_recovery and not live_data_recovery and not storage_recovery and not maintenance_recovery and not ai_brief_recovery and not alert_quality_recovery and not yfinance_cache_recovery:
        if str(realtime_report.get("status") or "").upper() == "OK" and realtime_report.get("checks"):
            return {
                "label": "Sin acciones",
                "tone": "buy",
                "detail": "Health OK; no hizo falta autoheal",
                "recovered": [],
                "failed": [],
                "routine_refresh": True,
            }
        return {"label": "Sin dato", "tone": "watch", "detail": "Watchdog aun sin autoheal"}

    recovered = list(launchd.get("recovered") or [])
    failed = list(launchd.get("failed") or [])
    service_count = int(launchd.get("service_count") or 0)
    backup_action = text_display(backup.get("action")) if backup else ""
    backup_status = backup.get("status") if isinstance(backup.get("status"), dict) else {}
    backup_healthy = bool(backup_status.get("healthy")) if backup_status else backup_action == "healthy"
    backup_report_action = text_display(backup_report_recovery.get("action")) if backup_report_recovery else ""
    backup_report_ok = bool(backup_report_recovery.get("ok")) if backup_report_recovery else True
    streamlit_action = text_display(streamlit_recovery.get("action")) if streamlit_recovery else ""
    streamlit_ok = bool(streamlit_recovery.get("ok")) if streamlit_recovery else True
    chart_action = text_display(chart_recovery.get("action")) if chart_recovery else ""
    chart_ok = bool(chart_recovery.get("ok")) if chart_recovery else True
    live_data_action = text_display(live_data_recovery.get("action")) if live_data_recovery else ""
    live_data_ok = bool(live_data_recovery.get("ok")) if live_data_recovery else True
    storage_action = text_display(storage_recovery.get("action")) if storage_recovery else ""
    storage_ok = bool(storage_recovery.get("ok")) if storage_recovery else True
    maintenance_action = text_display(maintenance_recovery.get("action")) if maintenance_recovery else ""
    maintenance_ok = bool(maintenance_recovery.get("ok")) if maintenance_recovery else True
    ai_brief_action = text_display(ai_brief_recovery.get("action")) if ai_brief_recovery else ""
    ai_brief_ok = bool(ai_brief_recovery.get("ok")) if ai_brief_recovery else True
    alert_quality_action = text_display(alert_quality_recovery.get("action")) if alert_quality_recovery else ""
    alert_quality_ok = bool(alert_quality_recovery.get("ok")) if alert_quality_recovery else True
    yfinance_cache_action = text_display(yfinance_cache_recovery.get("action")) if yfinance_cache_recovery else ""
    yfinance_cache_ok = bool(yfinance_cache_recovery.get("ok")) if yfinance_cache_recovery else True
    routine_refresh = bool(
        str(realtime_report.get("status") or "").upper() == "OK"
        and not recovered
        and not failed
        and backup_action not in {"restarted", "started", "error"}
        and not backup_report_action
        and not streamlit_action
        and not chart_action
        and live_data_action in {"", "skipped_running_service"}
        and not storage_action
        and not maintenance_action
        and not yfinance_cache_action
        and (ai_brief_action in {"", "regenerated"})
        and (alert_quality_action in {"", "regenerated"})
    )

    if (
        failed
        or backup_action == "error"
        or (backup_report_recovery and not backup_report_ok)
        or (streamlit_recovery and not streamlit_ok)
        or (chart_recovery and not chart_ok)
        or (live_data_recovery and not live_data_ok)
        or (storage_recovery and not storage_ok)
        or (maintenance_recovery and not maintenance_ok)
        or (ai_brief_recovery and not ai_brief_ok)
        or (alert_quality_recovery and not alert_quality_ok)
        or (yfinance_cache_recovery and not yfinance_cache_ok)
    ):
        label = "Falla"
        tone = "avoid"
    elif (
        recovered
        or backup_action in {"restarted", "started"}
        or backup_report_action == "regenerated"
        or streamlit_action in {"restart", "bootstrapped"}
        or chart_action == "regenerated"
        or live_data_action == "ran_live_scan"
        or storage_action == "created_missing_destination"
        or maintenance_action == "regenerated"
        or ai_brief_action == "regenerated"
        or alert_quality_action == "regenerated"
        or yfinance_cache_action == "recovered"
    ):
        if routine_refresh:
            label = "OK"
            tone = "buy"
        else:
            label = f"Recupero {len(recovered)}"
            tone = "watch"
    else:
        label = "OK"
        tone = "buy"

    details = []
    if service_count:
        details.append(f"servicios {service_count}")
    details.append(f"recuperados {len(recovered)}")
    if failed:
        details.append(f"fallos {len(failed)}")
    if backup_action:
        details.append(f"backup {backup_action}")
    elif backup_healthy:
        details.append("backup healthy")
    if backup_report_action:
        details.append(f"backup report {backup_report_action}")
    if streamlit_action:
        details.append(f"web {streamlit_action}")
    if chart_action:
        details.append(f"graficas {chart_action}")
    if live_data_action:
        details.append(f"live {live_data_action}")
    if storage_action:
        details.append(f"storage {storage_action}")
    if maintenance_action:
        details.append(f"limpieza {maintenance_action}")
    if ai_brief_action:
        details.append(f"brief {ai_brief_action}")
    if alert_quality_action:
        details.append(f"alertas {alert_quality_action}")
    if yfinance_cache_action:
        details.append(f"cache yf {yfinance_cache_action}")
    return {
        "label": label,
        "tone": tone,
        "detail": " | ".join(details),
        "recovered": recovered,
        "failed": failed,
        "backup_action": backup_action,
        "backup_report_action": backup_report_action,
        "streamlit_action": streamlit_action,
        "chart_action": chart_action,
        "live_data_action": live_data_action,
        "storage_action": storage_action,
        "maintenance_action": maintenance_action,
        "ai_brief_action": ai_brief_action,
        "alert_quality_action": alert_quality_action,
        "yfinance_cache_action": yfinance_cache_action,
        "routine_refresh": routine_refresh,
    }


def realtime_report_check_card(
    realtime_report: dict[str, Any] | None,
    check_name: str,
    *,
    ok_label: str = "OK",
    missing_label: str = "Sin dato",
) -> dict[str, str]:
    item = check_from_report(realtime_report, check_name)
    if not item:
        return {"label": missing_label, "tone": "watch", "detail": "No esta en el reporte RT"}
    status = text_display(item.get("status")).upper()
    if status == "OK":
        return {"label": ok_label, "tone": "buy", "detail": text_display(item.get("detail"))}
    if status == "FAIL":
        return {"label": "Falla", "tone": "avoid", "detail": text_display(item.get("detail"))}
    if status == "WARN":
        return {"label": "Revisar", "tone": "watch", "detail": text_display(item.get("detail"))}
    if status == "INFO":
        return {"label": "Info", "tone": "neutral", "detail": text_display(item.get("detail"))}
    return {"label": status or missing_label, "tone": "watch", "detail": text_display(item.get("detail"))}


def storage_migration_dashboard_status(realtime_report: dict[str, Any] | None) -> dict[str, str]:
    item = check_from_report(realtime_report, "storage_migration")
    if not item:
        return {"label": "Sin check", "tone": "watch", "detail": "No esta en el reporte RT"}
    status = text_display(item.get("status")).upper()
    state = text_display(item.get("state")).upper()
    detail = text_display(item.get("detail"))
    if status == "FAIL":
        return {"label": "Falla", "tone": "avoid", "detail": detail}
    if state in {"MIGRATED", "NOT_PRESENT"}:
        return {"label": "OK", "tone": "buy", "detail": detail}
    if state == "WAITING_FOR_PARALLELS":
        return {"label": "Pendiente", "tone": "watch", "detail": detail}
    if state in {"LOCAL_ONLY", "COPY_PRESENT", "DESTINATION_ONLY"}:
        return {"label": "Revisar", "tone": "watch", "detail": detail}
    return {"label": status or "Revisar", "tone": "watch", "detail": detail}


def local_training_media_dashboard_status(realtime_report: dict[str, Any] | None) -> dict[str, Any]:
    item = check_from_report(realtime_report, "local_training_media")
    if not item:
        return {"label": "Sin check", "tone": "watch", "detail": "No esta en el reporte RT", "size_gb": None}
    status = text_display(item.get("status")).upper()
    state = text_display(item.get("state")).upper()
    size_gb = safe_float(item.get("size_gb"))
    detail = text_display(item.get("detail"))
    if status == "FAIL":
        label = "Mover"
        tone = "avoid"
    elif status == "WARN":
        label = "Crece"
        tone = "watch"
    elif state == "ABSENT":
        label = "Libre"
        tone = "buy"
    elif state == "EXTERNAL_LINKED":
        label = "Externa"
        tone = "buy"
    elif size_gb is not None:
        label = f"{size_gb:.2f} GB"
        tone = "buy"
    else:
        label = "OK"
        tone = "buy"
    return {
        "label": label,
        "tone": tone,
        "detail": detail,
        "size_gb": size_gb,
        "state": state,
        "external_suggestion": text_display(item.get("external_suggestion")),
    }


def health_notify_dashboard_status(state: dict[str, Any] | None) -> dict[str, str]:
    state = state or {}
    if not state:
        return {"label": "Sin estado", "tone": "watch", "detail": "Aun no corrio notify-health"}
    status = text_display(state.get("last_status")).upper()
    result = state.get("last_result") if isinstance(state.get("last_result"), dict) else {}
    reason = text_display(result.get("reason") if result else "")
    sent = bool(result.get("sent")) if result else False
    if status == "OK":
        return {"label": "Silencioso", "tone": "buy", "detail": "Health OK; sin aviso necesario"}
    if sent:
        return {"label": "Avisado", "tone": "avoid" if status == "FAIL" else "watch", "detail": reason or status}
    if reason == "cooldown":
        return {"label": "Cooldown", "tone": "watch", "detail": "Aviso reciente ya enviado"}
    if reason == "recorded_local":
        return {"label": "Registrado", "tone": "watch", "detail": "Sin canal externo; guardado localmente"}
    return {"label": status or "Revisar", "tone": "watch", "detail": text_display(state.get("last_message"))}


def realtime_lock_dashboard_status(lock_report: dict[str, Any] | None) -> dict[str, str]:
    lock_report = lock_report or {}
    if not lock_report:
        return {"label": "Sin dato", "tone": "neutral", "detail": "Aun sin estado de lock"}
    event = text_display(lock_report.get("event")).lower()
    pid = text_display(lock_report.get("pid"))
    age = safe_float(lock_report.get("age_minutes"))
    age_detail = f"{age:.1f}m" if age is not None else "-"
    generated = text_display(lock_report.get("generated_at"))
    if event == "blocked":
        return {"label": "Ocupado", "tone": "watch", "detail": f"pid {pid} | age {age_detail}"}
    if event == "acquired":
        stale_replaced = bool(lock_report.get("stale_replaced"))
        label = "Reemplazo" if stale_replaced else "Activo"
        tone = "watch" if stale_replaced else "neutral"
        return {"label": label, "tone": tone, "detail": f"pid {pid} | {generated}"}
    if event == "released":
        return {"label": "Libre", "tone": "buy", "detail": text_display(lock_report.get("released_at") or generated)}
    return {"label": text_display(lock_report.get("event") or "-"), "tone": "watch", "detail": generated}


def load_health_history(path: str = "alerts/roxy_realtime_history.jsonl", limit: int = 100) -> list[dict[str, Any]]:
    p = runtime_path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = p.read_text(errors="replace").splitlines()
    except Exception:
        return []
    for line in lines[-max(1, int(limit)) :]:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def health_history_dashboard_status(rows: list[dict[str, Any]] | None, *, limit: int = 50) -> dict[str, Any]:
    rows = list(rows or [])[-max(1, int(limit)) :]
    if not rows:
        return {
            "label": "Sin historial",
            "tone": "watch",
            "detail": "Watchdog aun sin historial",
            "fail_count": 0,
            "warn_count": 0,
            "ok_rate": None,
            "current_streak_status": "-",
            "current_streak_count": 0,
        }
    fail_count = sum(1 for item in rows if str(item.get("status") or "").upper() == "FAIL" or int(item.get("fail_count") or 0) > 0)
    warn_count = sum(1 for item in rows if str(item.get("status") or "").upper() == "WARN" or int(item.get("warn_count") or 0) > 0)
    ok_count = sum(1 for item in rows if str(item.get("status") or "").upper() == "OK" and int(item.get("fail_count") or 0) == 0 and int(item.get("warn_count") or 0) == 0)
    ok_rate = ok_count / len(rows) if rows else 0.0
    latest = rows[-1]
    latest_status = text_display(latest.get("status")).upper()
    streak_count = 0
    for item in reversed(rows):
        if text_display(item.get("status")).upper() == latest_status:
            streak_count += 1
        else:
            break
    recovered = latest_status == "OK" and streak_count >= 3 and bool(fail_count or warn_count)
    if recovered:
        label = "Recuperado"
        tone = "watch"
    elif fail_count:
        label = "Inestable"
        tone = "avoid"
    elif warn_count:
        label = "Con avisos"
        tone = "watch"
    else:
        label = "Estable"
        tone = "buy"
    top_issue = latest.get("top_issue") if isinstance(latest.get("top_issue"), dict) else {}
    issue_name = text_display(top_issue.get("name") if top_issue else "")
    detail = f"OK {ok_rate * 100:.1f}% | racha {latest_status} x{streak_count} | {len(rows)} checks"
    if latest_status in {"FAIL", "WARN"} and issue_name:
        detail = f"{detail} | ultimo {issue_name}"
    return {
        "label": label,
        "tone": tone,
        "detail": detail,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "ok_count": ok_count,
        "ok_rate": ok_rate,
        "sample_size": len(rows),
        "latest_status": latest_status,
        "current_streak_status": latest_status,
        "current_streak_count": streak_count,
        "recovered": recovered,
    }


def health_history_display_table(rows: list[dict[str, Any]] | pd.DataFrame, *, limit: int = 50) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        source_rows = rows.to_dict(orient="records")
    else:
        source_rows = list(rows or [])
    display_rows: list[dict[str, Any]] = []
    for item in source_rows[-max(1, int(limit)) :]:
        if not isinstance(item, dict):
            continue
        top_issue = item.get("top_issue") if isinstance(item.get("top_issue"), dict) else {}
        detail = text_display(top_issue.get("detail") if top_issue else "")
        issue_name = text_display(top_issue.get("name") if top_issue else "")
        if "Traceback" in detail:
            detail = "Ver historial tecnico: fallo Python recuperado"
        elif len(detail) > 140:
            detail = detail[:137].rstrip() + "..."
        display_rows.append(
            {
                "generated_at": text_display(item.get("generated_at")),
                "status": text_display(item.get("status")).upper(),
                "mode": text_display(item.get("operational_mode")),
                "label": text_display(item.get("operational_label")),
                "ok": bool(item.get("ok")),
                "fail_count": int(item.get("fail_count") or 0),
                "warn_count": int(item.get("warn_count") or 0),
                "top_issue": issue_name or "-",
                "top_detail": detail or "-",
            }
        )
    return pd.DataFrame(display_rows)


def stability_summary_dashboard_status(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary = summary or {}
    sample_size = int(summary.get("sample_size") or 0)
    if not sample_size:
        return {"label": "Sin historial", "tone": "watch", "detail": "Watchdog aun sin historial"}
    fail_count = int(summary.get("fail_count") or 0)
    warn_count = int(summary.get("warn_count") or 0)
    latest_status = text_display(summary.get("current_streak_status") or summary.get("status")).upper()
    streak_count = int(summary.get("current_streak_count") or 0)
    ok_rate = safe_float(summary.get("ok_rate"))
    recovered = latest_status == "OK" and streak_count >= 3 and bool(fail_count or warn_count)
    if recovered:
        label = "Recuperado"
        tone = "watch"
    elif fail_count:
        label = "Inestable"
        tone = "avoid"
    elif warn_count:
        label = "Con avisos"
        tone = "watch"
    else:
        label = "Estable"
        tone = "buy"
    ok_text = f"{ok_rate * 100:.1f}%" if ok_rate is not None else "-"
    detail = f"OK {ok_text} | racha {latest_status} x{streak_count} | {sample_size} checks"
    incident_free_minutes = safe_float(summary.get("incident_free_minutes"))
    current_streak_minutes = safe_float(summary.get("current_streak_minutes"))
    if incident_free_minutes is not None:
        detail += f" | recuperado {incident_free_minutes:.1f}m"
    elif current_streak_minutes is not None and latest_status == "OK":
        detail += f" | OK {current_streak_minutes:.1f}m"
    last_issue = summary.get("last_issue") if isinstance(summary.get("last_issue"), dict) else {}
    if latest_status in {"FAIL", "WARN"} and last_issue:
        detail += f" | ultimo {text_display(last_issue.get('name'))}"
    dominant_issue = summary.get("dominant_issue") if isinstance(summary.get("dominant_issue"), dict) else {}
    if dominant_issue.get("name"):
        issue_prefix = "hist" if latest_status == "OK" else "recurrente"
        detail += f" | {issue_prefix} {text_display(dominant_issue.get('name'))} x{int(dominant_issue.get('count') or 0)}"
    return {
        "label": label,
        "tone": tone,
        "detail": detail,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "ok_rate": ok_rate,
        "sample_size": sample_size,
        "latest_status": latest_status,
        "current_streak_status": latest_status,
        "current_streak_count": streak_count,
        "current_streak_minutes": current_streak_minutes,
        "incident_free_minutes": incident_free_minutes,
        "dominant_issue": dominant_issue,
        "recovered": recovered,
    }


def disk_dashboard_status(path: str | Path, *, warn_free_gb: float = 20.0, fail_free_gb: float = 5.0) -> dict[str, Any]:
    disk_path = Path(path)
    if not disk_path.exists():
        return {"label": "No montado", "tone": "avoid", "detail": str(disk_path), "free_gb": None}
    try:
        usage = shutil.disk_usage(disk_path)
    except Exception as exc:
        return {"label": "Sin lectura", "tone": "watch", "detail": str(exc), "free_gb": None}
    free_gb = usage.free / (1024**3)
    total_gb = usage.total / (1024**3)
    used_pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
    if free_gb <= fail_free_gb:
        label = "Critico"
        tone = "avoid"
    elif free_gb <= warn_free_gb:
        label = "Bajo"
        tone = "watch"
    else:
        label = "OK"
        tone = "buy"
    return {
        "label": label,
        "tone": tone,
        "detail": f"{free_gb:.1f} GB libres | {used_pct:.0f}% usado",
        "free_gb": free_gb,
        "total_gb": total_gb,
        "used_pct": used_pct,
    }


def alert_gate_summary_dashboard_status(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary = summary or {}
    total = int(summary.get("total_opportunities") or 0)
    ready = int(summary.get("notifications_ready") or 0)
    blocked_realtime = int(summary.get("blocked_realtime_count") or 0)
    top_gate = text_display(summary.get("top_gate_label") or summary.get("top_gate"))
    avg_readiness = safe_float(summary.get("avg_readiness"))
    if not total:
        return {"label": "Sin setups", "tone": "neutral", "detail": "No hay oportunidades en brief"}
    if blocked_realtime:
        tone = "avoid"
        label = "Datos bloquean"
    elif ready:
        tone = "buy"
        label = f"{ready} lista(s)"
    else:
        tone = "watch"
        label = "Esperando"
    detail = f"{total} setups | {top_gate}"
    if avg_readiness is not None:
        detail += f" | readiness {avg_readiness:.0f}%"
    return {"label": label, "tone": tone, "detail": detail}


def alert_quality_report_dashboard_status(report: dict[str, Any] | None) -> dict[str, Any]:
    report = report or {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    entry = report.get("latest_entry") if isinstance(report.get("latest_entry"), dict) else {}
    if not entry:
        entry = report.get("entry") if isinstance(report.get("entry"), dict) else {}
    if not summary and not entry:
        return {"label": "Sin historial", "tone": "watch", "detail": "Aun no hay reporte de calidad"}
    state = text_display(summary.get("state") or entry.get("state")).upper()
    ready = int(summary.get("latest_notifications_ready") or entry.get("notifications_ready") or 0)
    total = int(summary.get("latest_total_opportunities") or entry.get("total_opportunities") or 0)
    waiting_streak = int(summary.get("waiting_streak") or 0)
    blocker_streak = int(summary.get("latest_top_blocker_streak") or 0)
    persistent_blocker_minutes = safe_float(summary.get("persistent_blocker_minutes"))
    diagnostic_severity = text_display(summary.get("diagnostic_severity") or "OK").upper()
    diagnostic_label = text_display(summary.get("diagnostic_label") or "")
    diagnostic_detail = text_display(summary.get("diagnostic_detail") or "")
    blocker_category = text_display(summary.get("blocker_category") or "")
    recommended_action = text_display(summary.get("recommended_action") or "")
    avg_readiness = safe_float(summary.get("avg_readiness"))
    readiness_delta = safe_float(summary.get("readiness_delta"))
    dominant_blocker = summary.get("dominant_blocker") if isinstance(summary.get("dominant_blocker"), dict) else {}
    blocker = text_display(summary.get("latest_top_blocker") or entry.get("top_blocker"))
    top_symbol = text_display(entry.get("top_symbol"))
    top_next_action = text_display(entry.get("top_next_action"))
    if state == "READY" or ready:
        label = f"{ready} lista(s)"
        tone = "buy"
    elif state in {"BLOCKED_DATA", "BLOCKED_REALTIME"}:
        label = "Datos bloquean"
        tone = "avoid"
    elif state == "NO_SETUPS":
        label = "Sin setups"
        tone = "neutral"
    elif diagnostic_severity == "ATTENTION" and diagnostic_label:
        label = diagnostic_label
        tone = "avoid"
    elif diagnostic_severity == "WATCH" and diagnostic_label:
        label = diagnostic_label
        tone = "watch"
    else:
        label = "Esperando"
        tone = "watch"
    detail = f"{ready}/{total} listas"
    if waiting_streak:
        detail += f" | racha espera {waiting_streak}"
    if blocker_streak:
        detail += f" | bloqueador x{blocker_streak}"
    if persistent_blocker_minutes is not None:
        detail += f" | persistente {persistent_blocker_minutes:.1f}m"
    if avg_readiness is not None:
        detail += f" | readiness {avg_readiness:.0f}%"
    if readiness_delta is not None:
        sign = "+" if readiness_delta > 0 else ""
        detail += f" | trend {sign}{readiness_delta:.1f}"
    if dominant_blocker.get("name"):
        dominant_name = text_display(dominant_blocker.get("name"))
        dominant_count = int(dominant_blocker.get("count") or 0)
        detail += f" | recurrente {dominant_name} x{dominant_count}"
    if blocker_category:
        detail += f" | tipo {blocker_category}"
    if top_symbol and top_symbol != "-":
        detail += f" | top {top_symbol}"
    if diagnostic_detail and diagnostic_detail not in {"-", blocker}:
        detail += f" | {diagnostic_detail}"
    elif blocker and blocker != "-":
        detail += f" | {blocker}"
    if top_next_action and top_next_action not in {"-", blocker, diagnostic_detail}:
        detail += f" | {top_next_action}"
    if recommended_action and recommended_action not in {"-", blocker, diagnostic_detail, top_next_action}:
        detail += f" | {recommended_action}"
    return {
        "label": label,
        "tone": tone,
        "detail": detail,
        "state": state,
        "waiting_streak": waiting_streak,
        "readiness_delta": readiness_delta,
        "dominant_blocker": dominant_blocker,
        "blocker_category": blocker_category,
        "recommended_action": recommended_action,
    }


def notification_history_dashboard_status(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary = summary or {}
    sample_size = int(summary.get("sample_size") or 0)
    if not sample_size:
        return {"label": "Sin historial", "tone": "watch", "detail": "Aun no hay intentos registrados"}
    cooldown = int(summary.get("cooldown_skipped") or 0)
    sent = int(summary.get("sent_count") or 0)
    channel_count = int(summary.get("channel_count") or 0)
    local_recorded = int(summary.get("local_recorded_count") or 0)
    last_age_minutes = safe_float(summary.get("last_age_minutes"))
    last_reason = text_display(summary.get("last_reason"))
    if channel_count == 0 and local_recorded:
        tone = "watch"
        label = "Local"
    elif cooldown:
        tone = "watch"
        label = f"{cooldown} cooldown"
    elif sent:
        tone = "buy"
        label = f"{sent} enviadas"
    else:
        tone = "neutral"
        label = "Sin envio"
    detail = f"{sample_size} eventos | ultimo {last_reason}"
    if last_age_minutes is not None:
        detail += f" hace {last_age_minutes:.1f}m"
    if channel_count == 0:
        detail += f" | local {local_recorded} | sin canal externo"
    elif channel_count:
        detail += f" | canales {channel_count}"
    if cooldown and "cooldown" not in label:
        detail += f" | cooldown {cooldown}"
    return {
        "label": label,
        "tone": tone,
        "detail": detail,
        "channel_count": channel_count,
        "local_recorded_count": local_recorded,
        "last_age_minutes": last_age_minutes,
    }


def notification_history_display_table(history: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    if isinstance(history, pd.DataFrame):
        table = history.copy()
    else:
        table = pd.DataFrame(history or [])
    if table.empty:
        return table
    rows = table.to_dict(orient="records")
    table["effective_sent"] = [notifier.notification_effectively_sent(row) for row in rows]
    if "message" in table.columns:
        table["message"] = table["message"].astype(str).str.replace("\n", " | ", regex=False).str.slice(0, 260)
    if "cooldown_skipped" in table.columns:
        table["cooldown_skipped"] = pd.to_numeric(table["cooldown_skipped"], errors="coerce").fillna(0).astype(int)
    return table


def chart_realtime_dashboard_status(report: dict[str, Any] | None) -> dict[str, Any]:
    report = report or {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if not summary:
        return {"label": "Sin reporte", "tone": "watch", "detail": "Ejecuta chart realtime health"}
    label = text_display(summary.get("label"))
    tone = text_display(summary.get("tone")) or "watch"
    checked = int(summary.get("checked_count") or 0)
    fail_count = int(summary.get("fail_count") or 0)
    warn_count = int(summary.get("warn_count") or 0)
    stale_count = int(summary.get("stale_count") or 0)
    data_quality_issue_count = int(summary.get("data_quality_issue_count") or 0)
    max_age_minutes = safe_float(summary.get("max_age_minutes"))
    avg_age_minutes = safe_float(summary.get("avg_age_minutes"))
    max_cadence_lag_minutes = safe_float(summary.get("max_cadence_lag_minutes"))
    max_health_lag_minutes = safe_float(summary.get("max_health_lag_minutes"))
    next_expected_update_in_minutes = safe_float(summary.get("next_expected_update_in_minutes"))
    detail = f"{checked} charts | fallos {fail_count} | warnings {warn_count}"
    if max_age_minutes is not None:
        detail += f" | max {max_age_minutes:.1f}m"
    if avg_age_minutes is not None:
        detail += f" | avg {avg_age_minutes:.1f}m"
    if max_cadence_lag_minutes is not None and max_cadence_lag_minutes > 0:
        detail += f" | lag max {max_cadence_lag_minutes:.1f}m"
    elif next_expected_update_in_minutes is not None:
        detail += f" | next vela {next_expected_update_in_minutes:.1f}m"
    if max_health_lag_minutes is not None and max_health_lag_minutes > 0:
        detail += f" | health lag {max_health_lag_minutes:.1f}m"
    if stale_count:
        detail += f" | estancadas {stale_count}"
    if data_quality_issue_count:
        detail += f" | calidad {data_quality_issue_count}"
    stalest_chart = summary.get("stalest_chart") if isinstance(summary.get("stalest_chart"), dict) else {}
    if stalest_chart and not summary.get("top_issue") and not (max_cadence_lag_minutes is not None and max_cadence_lag_minutes > 0):
        detail += f" | mas vieja {text_display(stalest_chart.get('symbol'))} {text_display(stalest_chart.get('timeframe'))}"
    top_issue = summary.get("top_issue") if isinstance(summary.get("top_issue"), dict) else {}
    if top_issue:
        detail += f" | {text_display(top_issue.get('symbol'))} {text_display(top_issue.get('timeframe'))}"
    most_overdue_chart = summary.get("most_overdue_chart") if isinstance(summary.get("most_overdue_chart"), dict) else {}
    if most_overdue_chart and max_cadence_lag_minutes is not None and max_cadence_lag_minutes > 0 and not top_issue:
        detail += f" | tarde {text_display(most_overdue_chart.get('symbol'))} {text_display(most_overdue_chart.get('timeframe'))}"
    return {
        "label": label or "Graficas",
        "tone": tone,
        "detail": detail,
        "max_age_minutes": max_age_minutes,
        "avg_age_minutes": avg_age_minutes,
        "max_cadence_lag_minutes": max_cadence_lag_minutes,
        "max_health_lag_minutes": max_health_lag_minutes,
        "next_expected_update_in_minutes": next_expected_update_in_minutes,
        "stalest_chart": stalest_chart,
        "most_overdue_chart": most_overdue_chart,
    }


def ai_brief_from_latest(
    scan_df: pd.DataFrame,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    *,
    source_files: dict[str, str | None] | None = None,
) -> dict:
    brief = build_brief(
        confluence_df=confluence_df,
        options_df=options_df,
        scan_df=scan_df,
        memory=load_memory(),
    )
    if source_files:
        brief["source_files"] = source_files
        brief["source_freshness"] = source_freshness_status(source_files)
    brief["market_session"] = market_session_status()
    brief["realtime_health"] = realtime_health_status()
    brief = apply_global_alert_context(brief)
    write_brief(brief)
    return brief


def normalize_realtime_refresh_interval(value: Any, *, default: int = DEFAULT_REALTIME_REFRESH_SECONDS) -> int:
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = int(default)
    allowed = sorted({int(item) for item in REALTIME_REFRESH_SECONDS})
    if interval in allowed:
        return interval
    return min(allowed, key=lambda item: abs(item - interval))


def build_realtime_refresh_script(interval_seconds: Any) -> str:
    interval = normalize_realtime_refresh_interval(interval_seconds)
    interval_ms = max(1, interval) * 1000
    return f"""
    <script>
    (() => {{
        const intervalMs = {interval_ms};
        const timerKey = "__roxyRealtimeRefreshTimer";
        const getRoot = () => {{
            try {{
                return window.parent && window.parent !== window ? window.parent : window;
            }} catch (error) {{
                return window;
            }}
        }};
        const root = getRoot();
        try {{
            if (root[timerKey]) {{
                root.clearTimeout(root[timerKey]);
            }}
        }} catch (error) {{}}
        const shouldDelayReload = () => {{
            try {{
                const doc = root.document;
                if (!doc || doc.visibilityState === "hidden") return true;
                const active = doc.activeElement;
                const tag = active && active.tagName ? active.tagName.toUpperCase() : "";
                return ["INPUT", "TEXTAREA", "SELECT"].includes(tag);
            }} catch (error) {{
                return false;
            }}
        }};
        const schedule = () => {{
            const timer = root.setTimeout(() => {{
                if (shouldDelayReload()) {{
                    schedule();
                    return;
                }}
                root.location.reload();
            }}, intervalMs);
            try {{
                root[timerKey] = timer;
            }} catch (error) {{}}
        }};
        schedule();
    }})();
    </script>
    """


def realtime_refresh_dashboard_status(realtime: dict[str, Any] | None) -> dict[str, Any]:
    realtime = realtime or {}
    enabled = bool(realtime.get("enabled"))
    interval = normalize_realtime_refresh_interval(realtime.get("interval_seconds"))
    if enabled:
        return {"label": "ON", "tone": "buy", "detail": f"{interval}s | pausa al escribir"}
    return {"label": "OFF", "tone": "watch", "detail": "manual"}


def configure_realtime_refresh() -> dict[str, Any]:
    st.sidebar.markdown("**Tiempo real**")
    enabled = st.sidebar.toggle("Auto-refresh", value=True, key="roxy_realtime_enabled")
    interval = st.sidebar.selectbox(
        "Intervalo",
        REALTIME_REFRESH_SECONDS,
        index=1,
        format_func=lambda value: f"{value}s",
        key="roxy_realtime_interval",
    )
    interval = normalize_realtime_refresh_interval(interval)
    st.sidebar.caption("Recarga la app y vuelve a leer CSV/live data. Pausa si escribes en un control.")
    if enabled:
        st.components.v1.html(build_realtime_refresh_script(interval), height=0)
    return {"enabled": enabled, "interval_seconds": int(interval)}


def show_focused_sidebar() -> None:
    state = live_service_state()
    channels = notifier.configured_channels()
    st.sidebar.title("Roxy")
    st.sidebar.caption("SMA 20/40/100/200 + 15m/1h/2h/4h")
    st.sidebar.markdown("**Estado operativo**")
    st.sidebar.write(f"Escaner 24h: `{'ON' if state['loaded'] == 'yes' else 'OFF'}`")
    st.sidebar.write("Alertas: `" + (", ".join(channels) if channels else "archivo local") + "`")
    st.sidebar.write("Watchlist IA/dev: `data/watchlist_ai_core.txt`")
    st.sidebar.markdown("**Regla principal**")
    st.sidebar.write("Solo alertar cuando 1h confirma, 15m da entrada, volumen acompana, riesgo <= 3.5% y target 2% es viable.")
    with st.sidebar.expander("Configuracion avanzada", expanded=False):
        st.write(f"Instalado: `{state['installed']}`")
        st.write(f"Activo: `{state['loaded']}`")
        st.write("Email: `SMTP_HOST` + `ALERT_EMAIL_TO`")
        st.write("Discord: `DISCORD_WEBHOOK_URL`")
        st.write("Slack: `SLACK_WEBHOOK_URL`")
        st.write("Webhook: `WEBHOOK_URL`")
        st.write("Mac: `MACOS_NOTIFICATIONS=1`")
        st.write("Estrategias: `" + "`, `".join(CORE_STRATEGIES) + "`")


def show_ai_status_cards(
    *,
    scan_df: pd.DataFrame,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    daily_path: str | None,
    live_path: str | None,
    confluence_path: str | None,
    options_path: str | None,
    brief: dict,
) -> None:
    state = live_service_state()
    alerts = int(brief.get("alert_count", 0) or 0)
    opportunities = brief.get("opportunities", [])
    best = opportunities[0] if opportunities else {}
    freshness = data_freshness_status([live_path, confluence_path], max_age_minutes=10.0)
    heartbeat = read_summary_json("alerts/ma_live_heartbeat.json")
    backend = live_backend_status(live_path, confluence_path, service_state=state, heartbeat=heartbeat)
    realtime_check = read_summary_json("alerts/roxy_realtime_check.json")
    check_status = realtime_check_status(realtime_check)
    autoheal_status = autoheal_dashboard_status(realtime_check)
    maintenance_report = read_summary_json("alerts/output_maintenance.json")
    maintenance_status = output_maintenance_dashboard_status(realtime_check, maintenance_report)
    runtime_backup_report = read_summary_json("alerts/runtime_backup.json")
    runtime_backup_daemon = read_summary_json("alerts/runtime_backup_daemon_heartbeat.json")
    runtime_backup_status = runtime_backup_dashboard_status(realtime_check, runtime_backup_report, runtime_backup_daemon)
    streamlit_service_status = realtime_report_check_card(
        realtime_check,
        "streamlit_service_24h",
        ok_label="24h ON",
        missing_label="Sin check",
    )
    daily_service_status = realtime_report_check_card(
        realtime_check,
        "daily_service",
        ok_label="Programado",
        missing_label="Sin check",
    )
    health_watchdog_status = realtime_report_check_card(
        realtime_check,
        "health_watchdog_service",
        ok_label="Vigilando",
        missing_label="Sin check",
    )
    lock_status = realtime_lock_dashboard_status(read_summary_json("alerts/roxy_realtime_lock.json"))
    health_notify_status = health_notify_dashboard_status(read_summary_json("alerts/roxy_health_notify_state.json"))
    health_history = load_health_history()
    health_history_status = (
        stability_summary_dashboard_status(realtime_check.get("stability_summary"))
        if isinstance(realtime_check.get("stability_summary"), dict)
        else health_history_dashboard_status(health_history)
    )
    mac_disk_status = disk_dashboard_status(Path.home())
    local_media_status = local_training_media_dashboard_status(realtime_check)
    external_disk_status = disk_dashboard_status("/Volumes/RoxyData", warn_free_gb=100.0, fail_free_gb=20.0)
    gate_summary = brief.get("alert_gate_summary") or summarize_alert_gates(brief)
    gate_summary_status = alert_gate_summary_dashboard_status(gate_summary)
    alert_quality_report = read_summary_json("alerts/alert_quality.json")
    alert_quality_status = alert_quality_report_dashboard_status(alert_quality_report)
    operational_mode_status = operational_mode_dashboard_status(realtime_check, alert_quality_report)
    delivery_summary = notifier.notification_history_summary(limit=50)
    delivery_summary_status = notification_history_dashboard_status(delivery_summary)
    chart_health_report = read_summary_json("alerts/chart_realtime_health.json")
    chart_health_status = chart_realtime_dashboard_status(chart_health_report)
    external_disk_check_status = realtime_report_check_card(
        realtime_check,
        "external_disk",
        ok_label="OK",
        missing_label=external_disk_status["label"],
    )
    storage_migration_status = storage_migration_dashboard_status(realtime_check)
    runtime_cache_status = realtime_report_check_card(
        realtime_check,
        "runtime_cache_migration",
        ok_label="Externa",
        missing_label="Sin check",
    )
    notification_delivery_status = realtime_report_check_card(
        realtime_check,
        "notification_delivery",
        ok_label="Lista",
        missing_label="Sin check",
    )
    operational_logs_status = realtime_report_check_card(
        realtime_check,
        "operational_logs",
        ok_label="Limpios",
        missing_label="Sin check",
    )
    session = brief.get("market_session") or market_session_status()
    realtime = brief.get("realtime") or {}
    realtime_refresh_status = realtime_refresh_dashboard_status(realtime)
    show_technical_reports = st.sidebar.toggle(
        "Mostrar diagnostico tecnico",
        value=False,
        key="roxy_support_mode_enabled",
        help="Solo para soporte: muestra JSON crudos, health, backups y reportes. Mantener apagado durante trading.",
    )
    if not show_technical_reports:
        st.sidebar.caption("Modo trading limpio: JSON y reportes tecnicos ocultos.")
    with st.expander("Estado operativo de Roxy", expanded=False):
        primary_cols = st.columns(6)
        with primary_cols[0]:
            render_kpi_card("Modo ops", operational_mode_status["label"], tone=operational_mode_status["tone"], detail=operational_mode_status["detail"])
        with primary_cols[1]:
            render_kpi_card("Backend live", backend["label"], tone=backend["tone"], detail=backend["detail"])
        with primary_cols[2]:
            render_kpi_card("Alertas", alerts, tone="buy" if alerts else "neutral")
        with primary_cols[3]:
            render_kpi_card("Datos live", freshness["label"], tone=freshness["tone"], detail=freshness["detail"])
        with primary_cols[4]:
            session_tone = "buy" if session.get("stock_alerts_allowed") else "watch"
            render_kpi_card("Sesion stock", session.get("stock_session", "-"), tone=session_tone, detail=session.get("local_time"))
        with primary_cols[5]:
            render_kpi_card(
                "Auto-refresh",
                realtime_refresh_status["label"],
                tone=realtime_refresh_status["tone"],
                detail=realtime_refresh_status["detail"],
            )

        data_cols = st.columns(11)
        with data_cols[0]:
            label = safe_float(best.get("ai_score")) if best else None
            render_kpi_card("Mejor IA", num_display(label, 0) if label is not None else "-")
        with data_cols[1]:
            render_kpi_card("Filas live", len(scan_df) if not scan_df.empty else 0)
        with data_cols[2]:
            render_kpi_card("Confluencia", len(confluence_df) if not confluence_df.empty else 0)
        with data_cols[3]:
            render_kpi_card("Opciones", len(options_df) if not options_df.empty else 0)
        with data_cols[4]:
            render_kpi_card("Check RT", check_status["label"], tone=check_status["tone"], detail=check_status["detail"])
        with data_cols[5]:
            render_kpi_card(
                "Pagina 24h",
                streamlit_service_status["label"],
                tone=streamlit_service_status["tone"],
                detail=streamlit_service_status["detail"],
            )
        with data_cols[6]:
            render_kpi_card(
                "Scan diario",
                daily_service_status["label"],
                tone=daily_service_status["tone"],
                detail=daily_service_status["detail"],
            )
        with data_cols[7]:
            render_kpi_card(
                "Watchdog RT",
                health_watchdog_status["label"],
                tone=health_watchdog_status["tone"],
                detail=health_watchdog_status["detail"],
            )
        with data_cols[8]:
            render_kpi_card(
                "Avisos health",
                health_notify_status["label"],
                tone=health_notify_status["tone"],
                detail=health_notify_status["detail"],
            )
        with data_cols[9]:
            render_kpi_card(
                "Entrega alertas",
                notification_delivery_status["label"],
                tone=notification_delivery_status["tone"],
                detail=notification_delivery_status["detail"],
            )
        with data_cols[10]:
            render_kpi_card(
                "Limpieza",
                maintenance_status["label"],
                tone=maintenance_status["tone"],
                detail=maintenance_status["detail"],
            )

        if show_technical_reports:
            ops_cols = st.columns(4)
            with ops_cols[0]:
                render_kpi_card(
                    "Estabilidad RT",
                    health_history_status["label"],
                    tone=health_history_status["tone"],
                    detail=health_history_status["detail"],
                )
            with ops_cols[1]:
                render_kpi_card(
                    "Ultimo estado",
                    text_display(realtime_check.get("status") if realtime_check else "-"),
                    tone=check_status["tone"],
                    detail=text_display(realtime_check.get("generated_at") if realtime_check else "Sin reporte"),
                )
            with ops_cols[2]:
                history_path = str(runtime_path("alerts/roxy_realtime_history.jsonl"))
                render_kpi_card("Historial health", len(health_history), tone="neutral", detail=history_path)
            with ops_cols[3]:
                mac_media_tone = mac_disk_status["tone"]
                mac_media_label = mac_disk_status["label"]
                if mac_media_tone == "buy" and local_media_status["tone"] != "buy":
                    mac_media_tone = local_media_status["tone"]
                    mac_media_label = local_media_status["label"]
                render_kpi_card(
                    "Mac/media",
                    mac_media_label,
                    tone=mac_media_tone,
                    detail=f"Mac {mac_disk_status['detail']} | Media {local_media_status['detail']}",
                )

        if show_technical_reports:
            with st.expander("Infraestructura tecnica", expanded=False):
                ops_cols_2 = st.columns(11)
                with ops_cols_2[0]:
                    render_kpi_card(
                        "RoxyData",
                        external_disk_check_status["label"],
                        tone=external_disk_check_status["tone"] if external_disk_check_status["label"] != external_disk_status["label"] else external_disk_status["tone"],
                        detail=external_disk_check_status["detail"] if external_disk_check_status["detail"] != "No esta en el reporte RT" else external_disk_status["detail"],
                    )
                with ops_cols_2[1]:
                    render_kpi_card(
                        "Migracion espacio",
                        storage_migration_status["label"],
                        tone=storage_migration_status["tone"],
                        detail=storage_migration_status["detail"],
                    )
                with ops_cols_2[2]:
                    render_kpi_card(
                        "Cache runtime",
                        runtime_cache_status["label"],
                        tone=runtime_cache_status["tone"],
                        detail=runtime_cache_status["detail"],
                    )
                with ops_cols_2[3]:
                    render_kpi_card("Calidad alertas", gate_summary_status["label"], tone=gate_summary_status["tone"], detail=gate_summary_status["detail"])
                with ops_cols_2[4]:
                    render_kpi_card("Racha alertas", alert_quality_status["label"], tone=alert_quality_status["tone"], detail=alert_quality_status["detail"])
                with ops_cols_2[5]:
                    render_kpi_card("Delivery alertas", delivery_summary_status["label"], tone=delivery_summary_status["tone"], detail=delivery_summary_status["detail"])
                with ops_cols_2[6]:
                    render_kpi_card("Graficas RT", chart_health_status["label"], tone=chart_health_status["tone"], detail=chart_health_status["detail"])
                with ops_cols_2[7]:
                    render_kpi_card("Backup", runtime_backup_status["label"], tone=runtime_backup_status["tone"], detail=runtime_backup_status["detail"])
                with ops_cols_2[8]:
                    render_kpi_card("Autoheal", autoheal_status["label"], tone=autoheal_status["tone"], detail=autoheal_status["detail"])
                with ops_cols_2[9]:
                    render_kpi_card("Lock RT", lock_status["label"], tone=lock_status["tone"], detail=lock_status["detail"])
                with ops_cols_2[10]:
                    render_kpi_card(
                        "Logs ops",
                        operational_logs_status["label"],
                        tone=operational_logs_status["tone"],
                        detail=operational_logs_status["detail"],
                    )

        else:
            st.caption("Infraestructura tecnica oculta en modo trading limpio. Activa `Mostrar diagnostico tecnico` solo para soporte.")
        st.caption(
            "Datos recientes: "
            f"diario `{daily_path or '-'}` | live `{live_path or '-'}` | confluencia `{confluence_path or '-'}` | "
            f"opciones `{options_path or '-'}` | actualizado {latest_timestamp([daily_path, live_path, confluence_path, options_path])}"
        )
        if freshness["tone"] == "avoid":
            st.warning("Datos live/confluencia estancados. Roxy puede seguir leyendo memoria, pero no conviene operar hasta refrescar el scan.")
        if heartbeat and show_technical_reports:
            with st.expander("Heartbeat backend live", expanded=False):
                st.json(heartbeat)
        if realtime_check and show_technical_reports:
            with st.expander("Diagnostico tecnico avanzado", expanded=False):
                st.caption("Reportes crudos para depuracion. Mantener cerrado durante trading para reducir ruido visual.")
                with st.expander("Reporte verificacion realtime", expanded=False):
                    st.json(realtime_check)
                autoheal_keys = AUTOHEAL_REPORT_KEYS
                if any(realtime_check.get(key) for key in autoheal_keys):
                    with st.expander("Reporte autoheal", expanded=False):
                        st.json({key: realtime_check.get(key) for key in autoheal_keys})
                if health_history:
                    with st.expander("Historial health realtime", expanded=False):
                        history_display = health_history_display_table(health_history, limit=50)
                        if not history_display.empty:
                            st.dataframe(history_display, width="stretch", hide_index=True, height=320)
                        with st.expander("JSON tecnico del historial", expanded=False):
                            st.json(health_history[-50:])
                if maintenance_report:
                    with st.expander("Reporte limpieza output", expanded=False):
                        st.json(maintenance_report)
                if runtime_backup_report:
                    with st.expander("Reporte backup runtime", expanded=False):
                        st.json(runtime_backup_report)
                if gate_summary:
                    with st.expander("Resumen compuertas de alertas", expanded=False):
                        st.json(gate_summary)
                if alert_quality_report:
                    with st.expander("Historial calidad de alertas", expanded=False):
                        st.json(alert_quality_report)
                if delivery_summary:
                    with st.expander("Resumen delivery de alertas", expanded=False):
                        st.json(delivery_summary)
                if chart_health_report:
                    with st.expander("Reporte graficas realtime", expanded=False):
                        st.json(chart_health_report)


def show_focused_controls() -> None:
    control_cols = st.columns([1, 1, 1, 1, 1.2, 1])
    with control_cols[0]:
        if st.button("Live completo", key="focused_run_full_live"):
            with st.spinner("Corriendo scan live y reconstruyendo brief IA..."):
                code_scan, output_scan = run_local_command(["tools/ma_live.py", "--once"])
                code_brief, output_brief = run_local_command(["tools/roxy_ai_watch.py", "--notify"]) if code_scan == 0 else (1, "")
            if code_scan == 0 and code_brief == 0:
                st.success("Live completo actualizado")
            else:
                st.error("Live completo fallo")
            output = "\n".join(item for item in [output_scan, output_brief] if item)
            if output:
                st.code(output[-7000:])
    with control_cols[1]:
        if st.button("Escanear live ahora", key="focused_run_live"):
            with st.spinner("Corriendo scan intradia, confluencia, opciones y lectura IA..."):
                code, output = run_local_command(["tools/ma_live.py", "--once"])
            if code == 0:
                st.success("Scan live completado")
            else:
                st.error("Scan live fallo")
            if output:
                st.code(output[-5000:])
    with control_cols[2]:
        if st.button("Actualizar brief IA", key="focused_refresh_ai"):
            with st.spinner("Construyendo brief IA..."):
                code, output = run_local_command(["tools/roxy_ai_watch.py", "--notify"])
            if code == 0:
                st.success("Brief IA actualizado")
            else:
                st.error("Brief IA fallo")
            if output:
                st.code(output[-3000:])
    with control_cols[3]:
        if st.button("Activar 24h", key="focused_enable_24h"):
            with st.spinner("Instalando servicio 24h de macOS..."):
                code, output = run_local_command(
                    [
                        "tools/ma_live_launchd.py",
                        "install",
                        "--stock-intervals",
                        "15m,1h,2h,4h",
                        "--crypto-timeframes",
                        "15m,1h,2h,4h",
                        "--poll-seconds",
                        "300",
                        "--limit",
                        "30",
                        "--report-limit",
                        "12",
                        "--retention-count",
                        "96",
                        "--health-check",
                        "--health-app-url",
                        "http://127.0.0.1:8501",
                        "--health-chart-symbol",
                        "AAPL",
                        "--health-chart-timeframe",
                        "1h",
                    ]
                )
            if code == 0:
                st.success("Escaner 24h activado")
            else:
                st.error("No se pudo activar el escaner 24h")
            if output:
                st.code(output[-5000:])
    with control_cols[4]:
        if st.button("Detener 24h", key="focused_stop_24h"):
            with st.spinner("Deteniendo servicio 24h..."):
                code, output = run_local_command(["tools/ma_live_launchd.py", "uninstall"])
            if code == 0:
                st.success("Escaner 24h detenido")
            else:
                st.error("No se pudo detener el escaner 24h")
            if output:
                st.code(output[-3000:])
    with control_cols[5]:
        if st.button("Verificar RT", key="focused_realtime_check"):
            with st.spinner("Verificando pipeline realtime..."):
                code, output = run_local_command(
                    [
                        "tools/roxy_realtime_check.py",
                        "--app-url",
                        "http://127.0.0.1:8501",
                        "--chart-symbol",
                        "AAPL",
                        "--chart-timeframe",
                        "1h",
                        "--no-fail",
                    ]
                )
            if code == 0:
                st.success("Verificacion RT actualizada")
            else:
                st.error("Verificacion RT fallo antes de escribir reporte")
            if output:
                st.code(output[-5000:])


def watch_movement_label(row: dict) -> str:
    signal = str(row.get("signal") or "").upper()
    decision = str(row.get("trade_decision") or row.get("decision") or "").upper()
    trigger = str(row.get("trigger_setup") or row.get("trigger") or row.get("setup") or "").upper()
    trend = str(row.get("trend_setup") or row.get("trend") or "").upper()
    action = str(row.get("ai_action") or row.get("action") or "").upper()
    alert_movement = str(row.get("alert_movement") or row.get("movement") or "").strip()
    if action == "ALERT" or (signal == "BUY" and decision.startswith("TRADE_FOR")):
        return "BUY porque 15m/1h confirman, riesgo esta medido y target minimo es viable."
    if alert_movement:
        return alert_movement
    if "RISK_REWARD" in decision:
        return "Esperar mejor riesgo/beneficio: stop mas cerca o target minimo 2% viable."
    if "PULLBACK" in {trigger, trend}:
        return "Esperar rebote en SMA20/SMA40 con cierre verde y volumen."
    if "TREND_CONTINUATION" in {trigger, trend}:
        return "Esperar continuacion: cierre sobre SMA20 y ruptura del maximo reciente."
    if "EARLY_UPTREND" in {trigger, trend}:
        return "Esperar cruce confirmado: SMA20 sobre SMA40 y 1h sosteniendo tendencia."
    if "DOWNTREND" in {trigger, trend}:
        return "AVOID porque la estructura sigue bajista; esperar recuperacion sobre SMA200."
    if signal == "AVOID" or decision.startswith("NO_TRADE"):
        return "AVOID porque no hay confluencia BUY; esperar que vuelva a WATCH/BUY."
    if signal == "WATCH" or decision == "WAIT":
        return "Esperar 15m en BUY, 1h confirmando y volumen acompanando."
    return "Esperar setup mas claro antes de operar."


def opportunity_reason_label(row: dict) -> str:
    signal = str(row.get("signal") or "").upper()
    decision = str(row.get("trade_decision") or row.get("decision") or "").upper()
    trigger = str(row.get("trigger_setup") or row.get("trigger") or "").upper()
    trend = str(row.get("trend_setup") or row.get("trend") or "").upper()
    risk_pct = safe_float(row.get("risk_pct"))
    target_pct = safe_float(row.get("recommended_target_pct") or row.get("target_pct"))

    if opportunity_is_trade_ready(row):
        parts = ["BUY: confluencia activa"]
        if trigger:
            parts.append(trigger.replace("_", " ").title())
        if risk_pct is not None:
            parts.append(f"riesgo {risk_pct * 100:.2f}%")
        if target_pct is not None:
            parts.append(f"target {target_pct * 100:.0f}% viable")
        return " | ".join(parts[:4])

    if "RISK_REWARD" in decision:
        return "NO: el riesgo/beneficio no compensa el stop actual."
    if "DOWNTREND" in {trigger, trend}:
        return "AVOID: estructura bajista; primero debe recuperar medias largas."
    if signal == "AVOID" or decision.startswith("NO_TRADE"):
        return "AVOID: falta confluencia BUY entre tendencia, entrada y riesgo."
    if signal == "WATCH" or decision == "WAIT":
        return f"WATCH: {watch_movement_label(row)}"
    return "WAIT: falta un setup mas limpio."


def opportunity_change_label(row: dict) -> str:
    signal = str(row.get("signal") or "").upper()
    decision = str(row.get("trade_decision") or row.get("decision") or "").upper()
    trigger = str(row.get("trigger_setup") or row.get("trigger") or "").upper()
    trend = str(row.get("trend_setup") or row.get("trend") or "").upper()
    risk_pct = safe_float(row.get("risk_pct"))
    target_pct = safe_float(row.get("recommended_target_pct") or row.get("target_pct"))

    if opportunity_is_trade_ready(row):
        return "Mantener solo si respeta stop, 15m sigue BUY y volumen no se apaga."
    if "RISK_REWARD" in decision:
        return "Cambia si el stop queda mas cerca o el target minimo 2% vuelve a ser viable."
    if "DOWNTREND" in {trigger, trend}:
        return "Cambia si recupera SMA200 y 1h deja de marcar tendencia bajista."

    needed = []
    if signal != "BUY":
        needed.append("15m en BUY")
    if decision in {"", "WAIT"} or signal == "WATCH":
        needed.append("1h confirmando")
    if risk_pct is None or risk_pct > 0.035:
        needed.append("riesgo <= 3.5%")
    if target_pct is None or target_pct < 0.02:
        needed.append("target 2% viable")
    if not needed:
        needed.append("cierre fuerte con volumen")
    return "Necesita " + " + ".join(needed[:3]) + "."


def opportunity_confidence_label(row: dict) -> str:
    readiness = safe_float(row.get("alert_readiness_score") or row.get("readiness"))
    bias = str(row.get("learning_bias") or "").lower()
    memory_note = str(row.get("memory_note") or "")

    if bias == "positive" and readiness is not None and readiness >= 80:
        return "Alta: memoria positiva y checklist fuerte."
    if bias == "negative":
        return "Baja: memoria historica exige filtro extra."
    if bias == "shadow_positive":
        return "Media+: laboratorio WATCH mejora, falta muestra real."
    if bias == "shadow_negative":
        return "Baja: laboratorio WATCH exige filtro extra."
    if bias == "learning" or "no hay suficientes" in memory_note.lower():
        return "Aprendiendo: falta muestra cerrada."
    if readiness is not None and readiness >= 70:
        return "Media: checklist parcial, confirmar entrada."
    if readiness is not None:
        return "Baja: faltan condiciones del checklist."
    return "Sin memoria suficiente."


def focused_opportunity_table(brief: dict) -> pd.DataFrame:
    rows = []
    for row in brief.get("opportunities", []):
        option = row.get("option") or {}
        signal = str(row.get("signal") or "").upper()
        decision = str(row.get("trade_decision") or "").upper()
        action = str(row.get("ai_action") or "").upper()
        is_trade = action == "ALERT" or (signal == "BUY" and decision.startswith("TRADE_FOR"))
        is_no_trade = signal == "AVOID" or decision.startswith("NO_TRADE")
        is_watch = not is_trade and not is_no_trade and (signal == "WATCH" or action == "WATCH" or decision == "WAIT")
        focus_priority = 2 if is_trade else 1 if is_watch else 0
        rows.append(
            {
                "action": row.get("ai_action"),
                "symbol": row.get("symbol"),
                "market": row.get("market"),
                "ai_score": row.get("ai_score"),
                "signal": row.get("signal"),
                "decision": row.get("trade_decision"),
                "entry": row.get("entry"),
                "stop": row.get("stop"),
                "risk_pct": row.get("risk_pct"),
                "target_pct": row.get("recommended_target_pct"),
                "target_price": row.get("recommended_target_price"),
                "rel_volume": row.get("relative_volume_15m") or row.get("relative_volume"),
                "strategy_family": dashboard_strategy_label(row),
                "trigger": row.get("trigger_setup"),
                "trend": row.get("trend_setup"),
                "option": option.get("contract"),
                "option_score": option.get("score"),
                "gate": alert_gate_label(row.get("alert_gate")),
                "readiness": row.get("alert_readiness_score"),
                "confidence": opportunity_confidence_label(row),
                "learning_bias": row.get("learning_bias"),
                "raw_reason": row.get("reason"),
                "por_que": human_alert_reason(row) or opportunity_reason_label(row),
                "waiting_for": watch_movement_label(row),
                "cambia_si": opportunity_change_label(row),
                "focus_priority": focus_priority,
            }
        )
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    if "ai_score" in table.columns:
        table["ai_score"] = pd.to_numeric(table["ai_score"], errors="coerce").fillna(0)
    return table.sort_values(["focus_priority", "ai_score"], ascending=[False, False]).reset_index(drop=True)


def market_pulse_rows(table: pd.DataFrame) -> pd.DataFrame:
    columns = ["bucket", "tone", "market", "symbol", "gate", "readiness", "risk_pct", "ai_score"]
    if table.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for _, item in table.iterrows():
        row = item.to_dict()
        action = str(row.get("action") or row.get("ai_action") or "").upper()
        signal = str(row.get("signal") or "").upper()
        decision = str(row.get("decision") or row.get("trade_decision") or "").upper()
        if action == "ALERT" or opportunity_is_trade_ready(row):
            bucket = "Operar"
            tone = "buy"
        elif signal == "AVOID" or decision.startswith("NO_TRADE"):
            bucket = "Evitar"
            tone = "avoid"
        else:
            bucket = "Vigilar"
            tone = "watch"
        rows.append(
            {
                "bucket": bucket,
                "tone": tone,
                "market": text_display(row.get("market")),
                "symbol": text_display(row.get("symbol")).upper(),
                "gate": text_display(row.get("gate")),
                "readiness": safe_float(row.get("readiness")),
                "risk_pct": safe_float(row.get("risk_pct")),
                "ai_score": safe_float(row.get("ai_score")),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def market_pulse_summary(table: pd.DataFrame) -> dict[str, Any]:
    rows = market_pulse_rows(table)
    if rows.empty:
        return {
            "total": 0,
            "ready": 0,
            "watch": 0,
            "avoid": 0,
            "avg_readiness": None,
            "top_gate": "-",
            "top_market": "-",
            "risk_alerts": 0,
        }
    counts = rows["bucket"].value_counts()
    gate_counts = rows[rows["gate"].ne("-")]["gate"].value_counts()
    market_counts = rows[rows["market"].ne("-")]["market"].value_counts()
    risk_values = pd.to_numeric(rows["risk_pct"], errors="coerce")
    return {
        "total": int(len(rows)),
        "ready": int(counts.get("Operar", 0)),
        "watch": int(counts.get("Vigilar", 0)),
        "avoid": int(counts.get("Evitar", 0)),
        "avg_readiness": safe_float(pd.to_numeric(rows["readiness"], errors="coerce").mean()),
        "top_gate": str(gate_counts.index[0]) if not gate_counts.empty else "-",
        "top_market": str(market_counts.index[0]) if not market_counts.empty else "-",
        "risk_alerts": int(risk_values.gt(0.035).sum()),
    }


def filter_focused_opportunities(
    table: pd.DataFrame,
    *,
    bucket: str = "Todos",
    market: str = "Todos",
    min_readiness: float = 0,
) -> pd.DataFrame:
    if table.empty:
        return table
    pulse = market_pulse_rows(table)
    mask = pd.Series(True, index=table.index)
    if bucket != "Todos":
        mask &= pulse["bucket"].eq(bucket).to_numpy()
    if market != "Todos":
        mask &= pulse["market"].astype(str).str.lower().eq(str(market).lower()).to_numpy()
    readiness = pd.to_numeric(pulse["readiness"], errors="coerce").fillna(0)
    mask &= readiness.ge(float(min_readiness)).to_numpy()
    return table.loc[mask].reset_index(drop=True)


def market_pulse_risk_map(table: pd.DataFrame) -> pd.DataFrame:
    rows = market_pulse_rows(table)
    if rows.empty:
        return pd.DataFrame()
    risk_map = rows.copy()
    risk_map["readiness"] = pd.to_numeric(risk_map["readiness"], errors="coerce")
    risk_map["risk_pct"] = pd.to_numeric(risk_map["risk_pct"], errors="coerce")
    risk_map = risk_map.dropna(subset=["readiness", "risk_pct"])
    if risk_map.empty:
        return risk_map
    risk_map["risk_pct_display"] = risk_map["risk_pct"] * 100.0
    return risk_map



def dashboard_now_reason(row: dict[str, Any], brief: dict[str, Any] | None = None) -> str:
    brief = brief or {}
    if not row:
        return text_display(brief.get("summary") or "Esperar el próximo scan con datos frescos.")
    for key in ("waiting_for", "next", "por_que", "reason", "raw_reason"):
        value = text_display(row.get(key))
        if value != "-":
            return value
    movement = watch_movement_label(row)
    if movement and movement != "-":
        return movement
    reason = opportunity_reason_label(row)
    if reason and reason != "-":
        return reason
    return text_display(brief.get("summary") or "Esperar confirmación de 15m, 1h, volumen y riesgo.")

def scanner_overview_summary(
    table: pd.DataFrame,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    brief: dict,
) -> dict[str, Any]:
    pulse = market_pulse_summary(table)
    top = table.iloc[0].to_dict() if not table.empty else {}
    score_values = pd.to_numeric(table.get("ai_score", pd.Series(dtype=float)), errors="coerce") if not table.empty else pd.Series(dtype=float)
    readiness_values = pd.to_numeric(table.get("readiness", pd.Series(dtype=float)), errors="coerce") if not table.empty else pd.Series(dtype=float)
    option_candidates = 0
    if not options_df.empty:
        if "option_decision" in options_df.columns:
            option_candidates = int(options_df["option_decision"].astype(str).str.upper().eq("OPTION_CANDIDATE").sum())
        else:
            option_candidates = int(len(options_df))
    session = brief.get("market_session") if isinstance(brief.get("market_session"), dict) else {}
    freshness = brief.get("source_freshness") if isinstance(brief.get("source_freshness"), dict) else {}
    return {
        "total": pulse["total"],
        "ready": pulse["ready"],
        "watch": pulse["watch"],
        "avoid": pulse["avoid"],
        "top_symbol": text_display(top.get("symbol")).upper(),
        "top_action": human_trade_action(top) if top else "Esperar",
        "top_strategy": dashboard_strategy_label(top) if top else "-",
        "top_gate": pulse["top_gate"],
        "avg_score": safe_float(score_values.mean()),
        "avg_readiness": safe_float(readiness_values.mean()),
        "confluence_rows": int(len(confluence_df)),
        "option_candidates": option_candidates,
        "session": text_display(session.get("stock_session") or session.get("crypto_session")),
        "freshness": text_display(freshness.get("label")),
    }


def scanner_heatmap_rows(table: pd.DataFrame) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame(columns=["strategy", "bucket", "tone", "count", "avg_score", "avg_readiness"])
    pulse = market_pulse_rows(table)
    rows: list[dict[str, Any]] = []
    for idx, item in table.iterrows():
        row = item.to_dict()
        status = pulse.iloc[idx].to_dict() if idx < len(pulse) else {}
        rows.append(
            {
                "strategy": dashboard_strategy_label(row),
                "bucket": status.get("bucket", "Vigilar"),
                "tone": status.get("tone", "watch"),
                "ai_score": safe_float(row.get("ai_score")),
                "readiness": safe_float(row.get("readiness")),
            }
        )
    data = pd.DataFrame(rows)
    grouped = (
        data.groupby(["strategy", "bucket", "tone"], as_index=False)
        .agg(count=("strategy", "size"), avg_score=("ai_score", "mean"), avg_readiness=("readiness", "mean"))
        .sort_values(["count", "avg_score"], ascending=[False, False])
    )
    return grouped.reset_index(drop=True)


def scanner_leaderboard_rows(table: pd.DataFrame, *, bucket: str = "Todos", limit: int = 12) -> pd.DataFrame:
    filtered = filter_focused_opportunities(table, bucket=bucket)
    if filtered.empty:
        return pd.DataFrame(columns=["symbol", "status", "market", "strategy", "score", "readiness", "risk", "gate", "next"])
    pulse = market_pulse_rows(filtered)
    rows: list[dict[str, Any]] = []
    for idx, item in filtered.iterrows():
        row = item.to_dict()
        status = pulse.iloc[idx].to_dict() if idx < len(pulse) else {}
        rows.append(
            {
                "symbol": text_display(row.get("symbol")).upper(),
                "status": status.get("bucket", "-"),
                "market": text_display(row.get("market")),
                "strategy": dashboard_strategy_label(row),
                "score": safe_float(row.get("ai_score")),
                "readiness": safe_float(row.get("readiness")),
                "risk": safe_float(row.get("risk_pct")),
                "gate": text_display(row.get("gate")),
                "next": text_display(row.get("waiting_for")),
            }
        )
    display = pd.DataFrame(rows)
    display["score_sort"] = pd.to_numeric(display["score"], errors="coerce").fillna(0)
    display["readiness_sort"] = pd.to_numeric(display["readiness"], errors="coerce").fillna(0)
    display = display.sort_values(["score_sort", "readiness_sort"], ascending=[False, False]).head(limit)
    return display.drop(columns=["score_sort", "readiness_sort"]).reset_index(drop=True)


def scanner_action_lane_rows(table: pd.DataFrame, *, limit_per_lane: int = 4) -> pd.DataFrame:
    columns = ["lane", "tone", "symbol", "action", "strategy", "score", "readiness", "risk", "target", "trigger"]
    if table.empty:
        return pd.DataFrame(columns=columns)
    pulse = market_pulse_rows(table)
    rows: list[dict[str, Any]] = []
    lane_map = {
        "Operar": ("Ahora", "buy", 0),
        "Vigilar": ("Esperar gatillo", "watch", 1),
        "Evitar": ("No tocar", "avoid", 2),
    }
    for idx, item in table.iterrows():
        row = item.to_dict()
        status = pulse.iloc[idx].to_dict() if idx < len(pulse) else {}
        lane, tone, lane_order = lane_map.get(str(status.get("bucket")), ("Esperar gatillo", "watch", 1))
        rows.append(
            {
                "lane": lane,
                "tone": tone,
                "symbol": text_display(row.get("symbol")).upper(),
                "action": human_trade_action(row),
                "strategy": dashboard_strategy_label(row),
                "score": safe_float(row.get("ai_score")),
                "readiness": safe_float(row.get("readiness")),
                "risk": safe_float(row.get("risk_pct")),
                "target": safe_float(row.get("target_pct")),
                "trigger": text_display(row.get("waiting_for") or row.get("gate")),
                "lane_order": lane_order,
            }
        )
    display = pd.DataFrame(rows)
    display["score_sort"] = pd.to_numeric(display["score"], errors="coerce").fillna(0)
    display["readiness_sort"] = pd.to_numeric(display["readiness"], errors="coerce").fillna(0)
    display = display.sort_values(["lane_order", "score_sort", "readiness_sort"], ascending=[True, False, False])
    display = display.groupby("lane", sort=False).head(max(1, int(limit_per_lane)))
    return display.drop(columns=["lane_order", "score_sort", "readiness_sort"]).reset_index(drop=True)


def scanner_strategy_options(table: pd.DataFrame) -> list[str]:
    if table.empty:
        return ["Todos"]
    strategies = sorted(
        {
            dashboard_strategy_label(row)
            for row in table.to_dict("records")
            if dashboard_strategy_label(row) and dashboard_strategy_label(row) != "-"
        }
    )
    return ["Todos", *strategies]


def filter_scanner_explorer_rows(
    table: pd.DataFrame,
    *,
    bucket: str = "Todos",
    market: str = "Todos",
    strategy: str = "Todos",
    min_readiness: float = 0,
) -> pd.DataFrame:
    filtered = filter_focused_opportunities(table, bucket=bucket, market=market, min_readiness=min_readiness)
    if filtered.empty or strategy == "Todos":
        return filtered
    mask = [dashboard_strategy_label(row) == strategy for row in filtered.to_dict("records")]
    return filtered.loc[mask].reset_index(drop=True)


def scanner_wallboard_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit: int = 30) -> pd.DataFrame:
    columns = ["symbol", "status", "tone", "market", "strategy", "score", "readiness", "risk", "target", "rel_volume", "tf", "next"]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pulse = market_pulse_rows(table)
    for idx, item in table.iterrows():
        row = item.to_dict()
        status = pulse.iloc[idx].to_dict() if idx < len(pulse) else {}
        symbol = text_display(row.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        seen.add(symbol)
        rows.append(
            {
                "symbol": symbol,
                "status": status.get("bucket", "Vigilar"),
                "tone": status.get("tone", "watch"),
                "market": text_display(row.get("market")),
                "strategy": dashboard_strategy_label(row),
                "score": safe_float(row.get("ai_score")),
                "readiness": safe_float(row.get("readiness")),
                "risk": safe_float(row.get("risk_pct")),
                "target": safe_float(row.get("target_pct")),
                "rel_volume": safe_float(row.get("relative_volume_15m") or row.get("relative_volume") or row.get("rel_volume")),
                "tf": text_display(row.get("entry_tf") or row.get("tf") or row.get("timeframe")),
                "next": text_display(row.get("waiting_for") or row.get("gate")),
            }
        )
    if not confluence_df.empty:
        data = confluence_df.copy()
        if "confluence_score" in data.columns:
            data["sort_score"] = pd.to_numeric(data["confluence_score"], errors="coerce").fillna(0)
            data = data.sort_values("sort_score", ascending=False)
        for _, item in data.head(max(limit * 2, limit)).iterrows():
            row = item.to_dict()
            symbol = text_display(row.get("symbol")).upper()
            if not symbol or symbol == "-" or symbol in seen:
                continue
            signal = str(row.get("signal") or "").upper()
            decision = str(row.get("trade_decision") or "").upper()
            if signal == "BUY" and decision.startswith("TRADE_FOR"):
                status, tone = "Operar", "buy"
            elif signal == "AVOID" or decision.startswith("NO_TRADE"):
                status, tone = "Evitar", "avoid"
            else:
                status, tone = "Vigilar", "watch"
            rows.append(
                {
                    "symbol": symbol,
                    "status": status,
                    "tone": tone,
                    "market": text_display(row.get("market")),
                    "strategy": dashboard_strategy_label(row),
                    "score": safe_float(row.get("confluence_score") or row.get("ai_score")),
                    "readiness": None,
                    "risk": safe_float(row.get("risk_pct")),
                    "target": safe_float(row.get("recommended_target_pct")),
                    "rel_volume": safe_float(row.get("relative_volume_15m") or row.get("relative_volume") or row.get("rel_volume")),
                    "tf": text_display(row.get("entry_tf") or row.get("tf")),
                    "next": text_display(row.get("trade_decision") or row.get("action")),
                }
            )
            seen.add(symbol)
            if len(rows) >= limit:
                break
    result = pd.DataFrame(rows, columns=columns)
    if result.empty:
        return result
    result["score_sort"] = pd.to_numeric(result["score"], errors="coerce").fillna(0)
    result["risk_sort"] = pd.to_numeric(result["risk"], errors="coerce").fillna(99)
    result["volume_sort"] = pd.to_numeric(result["rel_volume"], errors="coerce").fillna(0)
    result["status_order"] = result["status"].map({"Operar": 0, "Vigilar": 1, "Evitar": 2}).fillna(1)
    result = result.sort_values(["status_order", "score_sort"], ascending=[True, False]).head(limit)
    return result.drop(columns=["score_sort", "risk_sort", "volume_sort", "status_order"]).reset_index(drop=True)


def scanner_wallboard_summary(rows: pd.DataFrame) -> dict[str, Any]:
    if rows.empty:
        return {"total": 0, "ready": 0, "watch": 0, "avoid": 0, "avg_score": None, "avg_risk": None, "top_strategy": "-", "top_symbol": "-"}
    counts = rows["status"].value_counts()
    strategies = rows[rows["strategy"].ne("-")]["strategy"].value_counts()
    return {
        "total": int(len(rows)),
        "ready": int(counts.get("Operar", 0)),
        "watch": int(counts.get("Vigilar", 0)),
        "avoid": int(counts.get("Evitar", 0)),
        "avg_score": safe_float(pd.to_numeric(rows["score"], errors="coerce").mean()),
        "avg_risk": safe_float(pd.to_numeric(rows["risk"], errors="coerce").mean()),
        "top_strategy": str(strategies.index[0]) if not strategies.empty else "-",
        "top_symbol": text_display(rows.iloc[0].get("symbol")).upper(),
    }


def scanner_opportunity_matrix_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit: int = 12) -> pd.DataFrame:
    columns = ["rank", "symbol", "status", "tone", "edge", "score", "risk", "rel_volume", "strategy", "next"]
    rows = scanner_wallboard_rows(table, confluence_df, limit=max(limit * 3, limit))
    if rows.empty:
        return pd.DataFrame(columns=columns)
    display = rows.copy()
    score = pd.to_numeric(display["score"], errors="coerce").fillna(0.0)
    risk = pd.to_numeric(display["risk"], errors="coerce").fillna(0.99)
    rel_volume = pd.to_numeric(display["rel_volume"], errors="coerce").fillna(0.0)
    target = pd.to_numeric(display["target"], errors="coerce").fillna(0.0)
    status_bonus = display["status"].map({"Operar": 18.0, "Vigilar": 8.0, "Evitar": -28.0}).fillna(0.0)
    display["edge"] = (score + (rel_volume.clip(0, 5) * 4.0) + (target.clip(0, 0.15) * 150.0) + status_bonus - (risk.clip(0, 0.20) * 180.0)).round(1)
    display = display.sort_values(["edge", "score"], ascending=[False, False]).head(limit).reset_index(drop=True)
    display["rank"] = display.index + 1
    return display[columns]


def scanner_matrix_summary(rows: pd.DataFrame) -> dict[str, Any]:
    if rows.empty:
        return {"top_symbol": "-", "top_status": "-", "top_edge": None, "watch_count": 0, "low_risk": 0, "volume_count": 0}
    risk = pd.to_numeric(rows["risk"], errors="coerce")
    rel_volume = pd.to_numeric(rows["rel_volume"], errors="coerce")
    top = rows.iloc[0].to_dict()
    return {
        "top_symbol": text_display(top.get("symbol")).upper(),
        "top_status": text_display(top.get("status")),
        "top_edge": safe_float(top.get("edge")),
        "watch_count": int(rows["status"].astype(str).eq("Vigilar").sum()),
        "low_risk": int(risk.le(0.035).sum()),
        "volume_count": int(rel_volume.ge(1.0).sum()),
    }


def opportunity_compare_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit: int = 4) -> pd.DataFrame:
    columns = ["rank", "symbol", "status", "tone", "edge", "score", "risk", "target", "rel_volume", "strategy", "next", "verdict"]
    matrix = scanner_opportunity_matrix_rows(table, confluence_df, limit=max(limit * 2, limit))
    if matrix.empty:
        return pd.DataFrame(columns=columns)
    wall = scanner_wallboard_rows(table, confluence_df, limit=max(limit * 3, limit))
    target_lookup = {text_display(row.get("symbol")).upper(): safe_float(row.get("target")) for row in wall.to_dict("records")}
    rows: list[dict[str, Any]] = []
    for _, item in matrix.head(limit).iterrows():
        row = item.to_dict()
        symbol = text_display(row.get("symbol")).upper()
        status = text_display(row.get("status"))
        risk = safe_float(row.get("risk"))
        target = target_lookup.get(symbol)
        volume = safe_float(row.get("rel_volume"))
        if status == "Operar":
            verdict = "Mejor candidata si respeta stop y timing."
        elif risk is not None and risk > 0.035:
            verdict = "Riesgo alto: esperar mejor entrada."
        elif volume is not None and volume < 0.8:
            verdict = "Falta volumen real para confiar."
        else:
            verdict = text_display(row.get("next"))
        rows.append(
            {
                "rank": int(row.get("rank") or len(rows) + 1),
                "symbol": symbol,
                "status": status,
                "tone": text_display(row.get("tone")),
                "edge": safe_float(row.get("edge")),
                "score": safe_float(row.get("score")),
                "risk": risk,
                "target": target,
                "rel_volume": volume,
                "strategy": text_display(row.get("strategy")),
                "next": text_display(row.get("next")),
                "verdict": verdict,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def render_opportunity_compare_board(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = opportunity_compare_rows(table, confluence_df, limit=4)
    if rows.empty:
        return
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        symbol = text_display(row.get("symbol"))
        cards.append(
            f'<section class="compare-card compare-card-{html.escape(tone)}">'
            f'<header><span>#{int(row.get("rank") or 0)}</span><strong>{html.escape(symbol)}</strong><em>{html.escape(text_display(row.get("status")))}</em></header>'
            f'<div class="compare-score"><b>{html.escape(num_display(row.get("edge"), 0))}</b><span>Edge</span></div>'
            f'<div class="compare-grid">'
            f'<div><span>Score</span><strong>{html.escape(num_display(row.get("score"), 0))}</strong></div>'
            f'<div><span>Riesgo</span><strong>{html.escape(pct_display(row.get("risk")))}</strong></div>'
            f'<div><span>Target</span><strong>{html.escape(pct_display(row.get("target")))}</strong></div>'
            f'<div><span>RVol</span><strong>{html.escape(num_display(row.get("rel_volume"), 1))}x</strong></div>'
            f'</div>'
            f'<p>{html.escape(text_display(row.get("strategy")))}</p>'
            f'<small>{html.escape(text_display(row.get("verdict")))}</small>'
            "</section>"
        )
    st.markdown(
        '<section class="compare-board"><header><strong>Compare Board</strong><span>Comparación rápida para decidir cuál merece atención ahora.</span></header><div class="compare-grid-cards">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )



def ticker_intel_snapshot(table: pd.DataFrame, confluence_df: pd.DataFrame, symbol: str | None = None) -> dict[str, Any]:
    columns = ["symbol", "status", "tone", "edge", "score", "risk", "target", "rel_volume", "strategy", "next"]
    matrix = scanner_opportunity_matrix_rows(table, confluence_df, limit=12)
    if matrix.empty:
        return {
            "symbol": text_display(symbol).upper() if symbol else "-",
            "status": "Sin datos",
            "tone": "watch",
            "edge": None,
            "score": None,
            "risk": None,
            "target": None,
            "entry": None,
            "stop": None,
            "rel_volume": None,
            "strategy": "-",
            "next": "No hay lectura suficiente para priorizar.",
            "why": "Roxy necesita datos frescos del scanner o confluencia para construir una ficha operativa.",
            "blockers": ["Actualizar datos", "Esperar lectura 15m/1h"],
        }
    target_symbol = text_display(symbol).upper()
    rows = matrix.copy()
    if target_symbol and target_symbol != "-":
        selected = rows[rows["symbol"].astype(str).str.upper().eq(target_symbol)]
        if selected.empty:
            selected = rows.head(1)
    else:
        selected = rows.head(1)
    item = selected.iloc[0].to_dict()
    item = {key: item.get(key) for key in columns}
    selected_symbol = text_display(item.get("symbol")).upper()
    source_row: dict[str, Any] = {}
    if not table.empty and selected_symbol:
        matches = table[table.get("symbol", pd.Series(dtype=str)).astype(str).str.upper().eq(selected_symbol)]
        if not matches.empty:
            source_row = matches.iloc[0].to_dict()
    wall = scanner_wallboard_rows(table, confluence_df, limit=30)
    if not wall.empty:
        wall_matches = wall[wall["symbol"].astype(str).str.upper().eq(selected_symbol)]
        if not wall_matches.empty:
            wall_row = wall_matches.iloc[0].to_dict()
            item["target"] = wall_row.get("target")
            item["rel_volume"] = wall_row.get("rel_volume")
    risk = safe_float(item.get("risk"))
    target = safe_float(item.get("target"))
    rel_volume = safe_float(item.get("rel_volume"))
    blockers: list[str] = []
    if risk is not None and risk > 0.035:
        blockers.append(f"Riesgo {pct_display(risk)} > 3.5%")
    if target is None or target < 0.02:
        blockers.append("Target minimo 2% sin confirmar")
    if rel_volume is None or rel_volume < 0.8:
        blockers.append(f"Volumen relativo {num_display(rel_volume, 1)}x")
    status = text_display(item.get("status"))
    next_step = text_display(item.get("next") or source_row.get("waiting_for") or source_row.get("gate"))
    if status == "Operar" and not blockers:
        blockers.append("Listo para validacion manual final")
    elif next_step and next_step != "-":
        blockers.append(next_step[:90])
    why = text_display(source_row.get("raw_reason") or source_row.get("por_que") or opportunity_reason_label(source_row) if source_row else "")
    if why == "-":
        why = "Ficha priorizada por edge, score IA, riesgo, volumen relativo y estado multi-timeframe."
    return {
        "symbol": selected_symbol,
        "status": status,
        "tone": text_display(item.get("tone")),
        "edge": safe_float(item.get("edge")),
        "score": safe_float(item.get("score")),
        "risk": risk,
        "target": target,
        "entry": safe_float(source_row.get("entry")),
        "stop": safe_float(source_row.get("stop")),
        "rel_volume": rel_volume,
        "strategy": text_display(item.get("strategy")),
        "next": next_step,
        "why": why,
        "blockers": blockers[:4],
    }


def render_ticker_intel_strip(table: pd.DataFrame, confluence_df: pd.DataFrame, symbol: str | None = None) -> None:
    intel = ticker_intel_snapshot(table, confluence_df, symbol)
    tone = text_display(intel.get("tone"))
    blockers = intel.get("blockers") if isinstance(intel.get("blockers"), list) else []
    blocker_html = "".join(f"<li>{html.escape(text_display(item))}</li>" for item in blockers[:4])
    st.markdown(
        f"""
        <section class="ticker-intel ticker-intel-{html.escape(tone)}">
            <div class="ticker-intel-main">
                <span>Ticker Intel</span>
                <h3>{html.escape(text_display(intel.get("symbol")))}</h3>
                <strong>{html.escape(text_display(intel.get("status")))} · {html.escape(text_display(intel.get("strategy")))}</strong>
                <p>{html.escape(text_display(intel.get("why")))}</p>
            </div>
            <div class="ticker-intel-kpis">
                <div><span>Edge</span><strong>{html.escape(num_display(intel.get("edge"), 0))}</strong></div>
                <div><span>Score</span><strong>{html.escape(num_display(intel.get("score"), 0))}</strong></div>
                <div><span>Riesgo</span><strong>{html.escape(pct_display(intel.get("risk")))}</strong></div>
                <div><span>Target</span><strong>{html.escape(pct_display(intel.get("target")))}</strong></div>
                <div><span>Entrada</span><strong>{html.escape(num_display(intel.get("entry"), 2))}</strong></div>
                <div><span>Stop</span><strong>{html.escape(num_display(intel.get("stop"), 2))}</strong></div>
            </div>
            <div class="ticker-intel-next">
                <span>Que falta / siguiente accion</span>
                <ul>{blocker_html}</ul>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )



def company_research_hub_rows(symbol: str | None, market: str = "stock") -> pd.DataFrame:
    columns = ["label", "kind", "url", "why"]
    raw_symbol = text_display(symbol).upper()
    safe_symbol = "".join(char for char in raw_symbol if char.isalnum() or char in {".", "-", "/"})
    if not safe_symbol or safe_symbol == "-":
        return pd.DataFrame(columns=columns)
    stock_symbol = safe_symbol.split("/")[0]
    encoded_symbol = quote(stock_symbol, safe="")
    encoded_pair = quote(safe_symbol.replace("/", ""), safe="")
    is_crypto = str(market).lower() == "crypto" or "/" in safe_symbol
    if is_crypto:
        rows = [
            {
                "label": "TradingView",
                "kind": "Chart live",
                "url": f"https://www.tradingview.com/chart/?symbol={encoded_pair}",
                "why": "Velas, indicadores y replay visual para el par seleccionado.",
            },
            {
                "label": "Yahoo",
                "kind": "Quote",
                "url": f"https://finance.yahoo.com/quote/{encoded_pair}",
                "why": "Precio, variacion y noticias rapidas del activo.",
            },
            {
                "label": "CoinMarketCap",
                "kind": "Crypto intel",
                "url": f"https://coinmarketcap.com/search/?q={encoded_pair}",
                "why": "Capitalizacion, volumen y mercado cripto.",
            },
            {
                "label": "Alpaca",
                "kind": "Broker/data",
                "url": "https://alpaca.markets/docs/",
                "why": "Paper/live feed cuando existan key y secret en entorno seguro.",
            },
        ]
    else:
        rows = [
            {
                "label": "Finviz",
                "kind": "Company + screener",
                "url": f"https://finviz.com/quote.ashx?t={encoded_symbol}",
                "why": "Snapshot de compania, mapa sectorial, noticias y metricas.",
            },
            {
                "label": "TradingView",
                "kind": "Chart live",
                "url": f"https://www.tradingview.com/chart/?symbol={encoded_symbol}",
                "why": "Grafica interactiva externa para validar niveles historicos.",
            },
            {
                "label": "Yahoo",
                "kind": "Quote + news",
                "url": f"https://finance.yahoo.com/quote/{encoded_symbol}",
                "why": "Precio, perfil, calendario, noticias y fundamentales.",
            },
            {
                "label": "SEC",
                "kind": "Filings",
                "url": f"https://www.sec.gov/edgar/search/#/q={encoded_symbol}",
                "why": "Reportes oficiales, 10-K, 10-Q y eventos corporativos.",
            },
            {
                "label": "Nasdaq",
                "kind": "Market activity",
                "url": f"https://www.nasdaq.com/market-activity/stocks/{encoded_symbol.lower()}",
                "why": "Actividad de mercado, pre/after-market y eventos.",
            },
        ]
    return pd.DataFrame(rows, columns=columns)


def render_company_research_hub(symbol: str | None, market: str = "stock") -> None:
    rows = company_research_hub_rows(symbol, market)
    if rows.empty:
        return
    clean_symbol = text_display(symbol).upper()
    cards = []
    for row in rows.to_dict("records"):
        cards.append(
            f'<a class="research-card" href="{html.escape(text_display(row.get("url")))}" target="_blank" rel="noopener noreferrer">'
            f'<span>{html.escape(text_display(row.get("kind")))}</span>'
            f'<strong>{html.escape(text_display(row.get("label")))}</strong>'
            f'<small>{html.escape(text_display(row.get("why")))}</small>'
            "</a>"
        )
    st.markdown(
        f'<section class="company-research"><header><strong>Company Research Hub · {html.escape(clean_symbol)}</strong><span>Accesos rapidos para validar compania, noticias, filings, chart y broker sin perder el foco del scanner.</span></header><div class="research-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )



def screener_preset_rows(table: pd.DataFrame, confluence_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["preset", "tone", "count", "avg_edge", "top_symbols", "rule"]
    rows = scanner_opportunity_matrix_rows(table, confluence_df, limit=40)
    if rows.empty:
        return pd.DataFrame(columns=columns)
    data = rows.copy()
    strategy = data["strategy"].astype(str).str.lower()
    status = data["status"].astype(str)
    risk = pd.to_numeric(data["risk"], errors="coerce")
    rel_volume = pd.to_numeric(data["rel_volume"], errors="coerce")
    presets = [
        ("Breakouts", "buy", strategy.str.contains("break|salto|canal", regex=True, na=False), "ruptura/canal con edge alto"),
        ("Pullbacks", "watch", strategy.str.contains("pullback|retroceso|retest", regex=True, na=False), "retroceso cerca de soporte"),
        ("Bajo riesgo", "buy", risk.le(0.025), "riesgo <= 2.5%"),
        ("Volumen", "watch", rel_volume.ge(1.2), "volumen relativo >= 1.2x"),
        ("Evitar", "avoid", status.eq("Evitar"), "bloqueadas por checklist"),
    ]
    output: list[dict[str, Any]] = []
    for label, tone, mask, rule in presets:
        subset = data[mask.fillna(False)].copy()
        if subset.empty:
            top_symbols = "-"
            avg_edge = None
        else:
            subset = subset.sort_values(["edge", "score"], ascending=[False, False])
            top_symbols = " · ".join(subset["symbol"].astype(str).head(4).tolist())
            avg_edge = safe_float(pd.to_numeric(subset["edge"], errors="coerce").mean())
        output.append(
            {
                "preset": label,
                "tone": tone,
                "count": int(len(subset)),
                "avg_edge": avg_edge,
                "top_symbols": top_symbols,
                "rule": rule,
            }
        )
    return pd.DataFrame(output, columns=columns)


def render_screener_preset_deck(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = screener_preset_rows(table, confluence_df)
    if rows.empty:
        return
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<section class="preset-card preset-card-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("preset")))}</strong><span>{int(row.get("count") or 0)}</span></header>'
            f'<div><span>Edge avg</span><b>{html.escape(num_display(row.get("avg_edge"), 0))}</b></div>'
            f'<p>{html.escape(text_display(row.get("top_symbols")))}</p>'
            f'<small>{html.escape(text_display(row.get("rule")))}</small>'
            "</section>"
        )
    st.markdown(
        '<section class="screener-presets"><header><strong>Screener Presets</strong><span>Vistas rápidas tipo Finviz para separar trabajo real de ruido.</span></header><div class="preset-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )



def exit_plan_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit: int = 5) -> pd.DataFrame:
    columns = ["symbol", "tone", "status", "entry", "stop", "target_1", "target_2", "protect", "exit_rule"]
    if table.empty:
        return pd.DataFrame(columns=columns)
    wall = scanner_wallboard_rows(table, confluence_df, limit=max(limit * 3, limit))
    status_lookup = {
        text_display(row.get("symbol")).upper(): row
        for row in wall.to_dict("records")
        if text_display(row.get("symbol")).upper() and text_display(row.get("symbol")) != "-"
    }
    rows: list[dict[str, Any]] = []
    for item in table.to_dict("records"):
        symbol = text_display(item.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        status_row = status_lookup.get(symbol, {})
        entry = safe_float(item.get("entry"))
        stop = safe_float(item.get("stop"))
        target_pct = safe_float(item.get("target_pct") or item.get("recommended_target_pct"))
        target_price = safe_float(item.get("target_price") or item.get("recommended_target_price"))
        target_1 = target_price
        if target_1 is None and entry is not None and target_pct is not None:
            target_1 = round(entry * (1.0 + target_pct), 4)
        target_2 = round(entry * 1.05, 4) if entry is not None else None
        target_1 = round(target_1, 2) if target_1 is not None else None
        target_2 = round(target_2, 2) if target_2 is not None else None
        risk_pct = safe_float(item.get("risk_pct"))
        status = text_display(status_row.get("status") or item.get("decision") or item.get("signal"))
        tone = text_display(status_row.get("tone") or ("buy" if status == "Operar" else "avoid" if status == "Evitar" else "watch"))
        if entry is None or stop is None:
            protect = "No operar sin entrada/stop"
            exit_rule = "Esperar plan completo antes de enviar ticket."
            tone = "avoid"
        elif status == "Operar":
            protect = "Tomar parcial en T1; mover stop a break-even."
            exit_rule = "Salir si pierde entrada/EMA9 con volumen o toca stop."
        elif risk_pct is not None and risk_pct > 0.035:
            protect = "No perseguir: stop muy amplio."
            exit_rule = "Esperar entrada mas cerca del stop tecnico."
            tone = "watch"
        else:
            protect = "Mantener en vigilancia; no anticipar."
            exit_rule = text_display(item.get("waiting_for") or status_row.get("next"))
        rows.append(
            {
                "symbol": symbol,
                "tone": tone,
                "status": status,
                "entry": entry,
                "stop": stop,
                "target_1": target_1,
                "target_2": target_2,
                "protect": protect,
                "exit_rule": exit_rule,
                "sort_score": safe_float(item.get("ai_score")) or 0,
            }
        )
        if len(rows) >= limit:
            break
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=columns)
    result = result.sort_values("sort_score", ascending=False).head(limit)
    return result[columns].reset_index(drop=True)


def render_exit_plan_board(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = exit_plan_rows(table, confluence_df, limit=5)
    if rows.empty:
        return
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<section class="exit-card exit-card-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("symbol")))}</strong><span>{html.escape(text_display(row.get("status")))}</span></header>'
            f'<div class="exit-levels">'
            f'<div><span>Entry</span><b>{html.escape(num_display(row.get("entry"), 2))}</b></div>'
            f'<div><span>Stop</span><b>{html.escape(num_display(row.get("stop"), 2))}</b></div>'
            f'<div><span>T1</span><b>{html.escape(num_display(row.get("target_1"), 2))}</b></div>'
            f'<div><span>T2</span><b>{html.escape(num_display(row.get("target_2"), 2))}</b></div>'
            f'</div>'
            f'<p>{html.escape(text_display(row.get("protect")))}</p>'
            f'<small>{html.escape(text_display(row.get("exit_rule")))}</small>'
            "</section>"
        )
    st.markdown(
        '<section class="exit-board"><header><strong>Exit Plan Board</strong><span>Gestion de salida: proteger capital, capturar parcial y no devolver ganancias.</span></header><div class="exit-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )



def opportunity_edge_heatmap_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit: int = 40) -> pd.DataFrame:
    columns = ["strategy", "status", "tone", "count", "avg_edge", "avg_score", "avg_risk", "avg_volume", "symbols"]
    rows = scanner_wallboard_rows(table, confluence_df, limit=max(limit, 12))
    if rows.empty:
        return pd.DataFrame(columns=columns)
    data = rows.copy()
    score = pd.to_numeric(data["score"], errors="coerce").fillna(0.0)
    risk = pd.to_numeric(data["risk"], errors="coerce").fillna(0.99)
    rel_volume = pd.to_numeric(data["rel_volume"], errors="coerce").fillna(0.0)
    target = pd.to_numeric(data["target"], errors="coerce").fillna(0.0)
    status_bonus = data["status"].map({"Operar": 18.0, "Vigilar": 8.0, "Evitar": -28.0}).fillna(0.0)
    data["edge"] = (score + (rel_volume.clip(0, 5) * 4.0) + (target.clip(0, 0.15) * 150.0) + status_bonus - (risk.clip(0, 0.20) * 180.0)).round(1)
    data["strategy"] = data["strategy"].replace("", "-").fillna("-")
    grouped_rows: list[dict[str, Any]] = []
    for (strategy, status), group in data.groupby(["strategy", "status"], sort=False):
        ranked = group.sort_values(["edge", "score"], ascending=[False, False])
        grouped_rows.append(
            {
                "strategy": text_display(strategy),
                "status": text_display(status),
                "tone": text_display(ranked.iloc[0].get("tone")),
                "count": int(len(group)),
                "avg_edge": safe_float(pd.to_numeric(group["edge"], errors="coerce").mean()),
                "avg_score": safe_float(pd.to_numeric(group["score"], errors="coerce").mean()),
                "avg_risk": safe_float(pd.to_numeric(group["risk"], errors="coerce").mean()),
                "avg_volume": safe_float(pd.to_numeric(group["rel_volume"], errors="coerce").mean()),
                "symbols": ", ".join(ranked["symbol"].astype(str).head(4).tolist()),
            }
        )
    result = pd.DataFrame(grouped_rows, columns=columns)
    if result.empty:
        return result
    result["edge_sort"] = pd.to_numeric(result["avg_edge"], errors="coerce").fillna(-999)
    result["count_sort"] = pd.to_numeric(result["count"], errors="coerce").fillna(0)
    return result.sort_values(["edge_sort", "count_sort"], ascending=[False, False]).drop(columns=["edge_sort", "count_sort"]).reset_index(drop=True)


def render_opportunity_edge_heatmap(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = opportunity_edge_heatmap_rows(table, confluence_df, limit=40)
    if rows.empty:
        return
    chart_df = rows.copy()
    chart_df["avg_edge"] = pd.to_numeric(chart_df["avg_edge"], errors="coerce").fillna(0)
    chart_df["count"] = pd.to_numeric(chart_df["count"], errors="coerce").fillna(0).astype(int)
    chart_df["label"] = chart_df["count"].astype(str) + " · " + chart_df["symbols"].astype(str)
    heatmap = (
        alt.Chart(chart_df)
        .mark_rect(cornerRadius=4)
        .encode(
            x=alt.X("status:N", title=None, sort=["Operar", "Vigilar", "Evitar"]),
            y=alt.Y("strategy:N", title=None, sort="-x"),
            color=alt.Color(
                "avg_edge:Q",
                title="Edge",
                scale=alt.Scale(scheme="redyellowgreen"),
            ),
            tooltip=[
                alt.Tooltip("strategy:N", title="Estrategia"),
                alt.Tooltip("status:N", title="Estado"),
                alt.Tooltip("count:Q", title="Setups"),
                alt.Tooltip("avg_edge:Q", title="Edge avg", format=".1f"),
                alt.Tooltip("avg_score:Q", title="Score avg", format=".1f"),
                alt.Tooltip("avg_risk:Q", title="Riesgo avg", format=".2%"),
                alt.Tooltip("avg_volume:Q", title="RVol avg", format=".1f"),
                alt.Tooltip("symbols:N", title="Símbolos"),
            ],
        )
    )
    labels = (
        alt.Chart(chart_df)
        .mark_text(color="#f8fafc", fontSize=11, fontWeight="bold", lineBreak=", ")
        .encode(
            x=alt.X("status:N", title=None, sort=["Operar", "Vigilar", "Evitar"]),
            y=alt.Y("strategy:N", title=None, sort="-x"),
            text=alt.Text("label:N"),
        )
    )
    st.markdown("**Edge Heatmap**")
    st.caption("Mapa compacto por estrategia y estado: más verde = mejor mezcla de score, volumen, target y riesgo.")
    st.altair_chart(style_trading_chart((heatmap + labels).properties(height=max(220, min(520, 54 + len(rows) * 26)))), use_container_width=True)



def executive_cockpit_summary(table: pd.DataFrame, confluence_df: pd.DataFrame, scan_df: pd.DataFrame, brief: dict) -> dict[str, Any]:
    matrix_rows = scanner_opportunity_matrix_rows(table, confluence_df, limit=6)
    wall_rows = scanner_wallboard_rows(table, confluence_df, limit=32)
    wall_summary = scanner_wallboard_summary(wall_rows) if not wall_rows.empty else {
        "total": 0,
        "ready": 0,
        "watch": 0,
        "avoid": 0,
        "avg_score": None,
        "avg_risk": None,
        "top_strategy": "-",
        "top_symbol": "-",
    }
    top = matrix_rows.iloc[0].to_dict() if not matrix_rows.empty else {}
    freshness = brief.get("source_freshness") if isinstance(brief.get("source_freshness"), dict) else {}
    session = brief.get("market_session") if isinstance(brief.get("market_session"), dict) else {}
    index_regime = market_regime_summary(market_index_strip_rows(scan_df, confluence_df))
    validation_rows = confluence_validation_rows(confluence_df, limit=12)
    validated = int(validation_rows["decision"].eq("Validado").sum()) if not validation_rows.empty else 0
    blocked = int(validation_rows["decision"].eq("Bloqueado").sum()) if not validation_rows.empty else 0
    top_status = text_display(top.get("status") or wall_summary.get("top_symbol"))
    top_symbol = text_display(top.get("symbol") or wall_summary.get("top_symbol")).upper()
    if not top_symbol or top_symbol == "-":
        headline = "Sin oportunidad priorizada"
    else:
        headline = f"{top_symbol} · {top_status}"
    return {
        "headline": headline,
        "top_symbol": top_symbol,
        "top_status": top_status,
        "top_edge": safe_float(top.get("edge")),
        "top_strategy": text_display(top.get("strategy") or wall_summary.get("top_strategy")),
        "top_next": text_display(top.get("next")),
        "total": wall_summary["total"],
        "ready": wall_summary["ready"],
        "watch": wall_summary["watch"],
        "avoid": wall_summary["avoid"],
        "avg_score": wall_summary["avg_score"],
        "avg_risk": wall_summary["avg_risk"],
        "validated": validated,
        "blocked": blocked,
        "regime_label": index_regime["label"],
        "regime_tone": index_regime["tone"],
        "regime_detail": index_regime["detail"],
        "session": text_display(session.get("stock_session") or session.get("crypto_session")),
        "freshness": text_display(freshness.get("label")),
        "tape": matrix_rows.to_dict("records"),
    }


def render_executive_cockpit(table: pd.DataFrame, confluence_df: pd.DataFrame, scan_df: pd.DataFrame, brief: dict) -> None:
    summary = executive_cockpit_summary(table, confluence_df, scan_df, brief)
    if not summary["total"] and not summary["tape"]:
        return
    if summary["ready"]:
        action_tone = "buy"
        action_label = "Prioridad: operar confirmado"
        action_detail = f"{summary['ready']} listas · validar stop/target antes de paper"
    elif summary["watch"]:
        action_tone = "watch"
        action_label = "Prioridad: esperar gatillo"
        action_detail = f"{summary['watch']} en watch · no anticipar entrada"
    else:
        action_tone = "avoid"
        action_label = "Prioridad: proteger capital"
        action_detail = "Sin setups limpios · esperar nuevo scan"
    tape_items = []
    for row in summary["tape"][:5]:
        tone = text_display(row.get("tone"))
        tape_items.append(
            f'<div class="exec-tape-item exec-tape-{html.escape(tone)}">'
            f'<strong>{html.escape(text_display(row.get("symbol")))}</strong>'
            f'<span>{html.escape(text_display(row.get("status")))} · {html.escape(num_display(row.get("edge"), 0))}</span>'
            f'<small>R {html.escape(pct_display(row.get("risk")))} · {html.escape(text_display(row.get("strategy")))}</small>'
            "</div>"
        )
    st.markdown(
        f"""
        <section class="executive-cockpit executive-cockpit-{html.escape(summary['regime_tone'])}">
            <div class="exec-main">
                <span>Roxy live cockpit</span>
                <h2>{html.escape(summary['headline'])}</h2>
                <p>{html.escape(summary['top_strategy'])} · Edge {html.escape(num_display(summary['top_edge'], 0))} · {html.escape(summary['top_next'])}</p>
                <div class="exec-action-line exec-action-{html.escape(action_tone)}">
                    <strong>{html.escape(action_label)}</strong>
                    <small>{html.escape(action_detail)}</small>
                </div>
            </div>
            <div class="exec-kpis">
                <div><span>Operar</span><strong>{summary['ready']}</strong><small>{summary['validated']} validadas</small></div>
                <div><span>Vigilar</span><strong>{summary['watch']}</strong><small>gatillo pendiente</small></div>
                <div><span>Bloqueos</span><strong>{summary['avoid']}</strong><small>{summary['blocked']} MTF</small></div>
                <div><span>Régimen</span><strong>{html.escape(summary['regime_label'])}</strong><small>{html.escape(summary['session'])} · {html.escape(summary['freshness'])}</small></div>
            </div>
            <div class="exec-tape">{''.join(tape_items)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_opportunity_matrix(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = scanner_opportunity_matrix_rows(table, confluence_df, limit=12)
    if rows.empty:
        return
    summary = scanner_matrix_summary(rows)
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<div class="matrix-row matrix-row-{html.escape(tone)}">'
            f'<span>#{int(row.get("rank") or 0)}</span>'
            f'<strong>{html.escape(text_display(row.get("symbol")))}</strong>'
            f'<em>{html.escape(text_display(row.get("status")))}</em>'
            f'<b>{html.escape(num_display(row.get("edge"), 0))}</b>'
            f'<small>{html.escape(text_display(row.get("strategy")))} · R {html.escape(pct_display(row.get("risk")))} · V {html.escape(num_display(row.get("rel_volume"), 1))}x</small>'
            f'<i>{html.escape(text_display(row.get("next")))}</i>'
            "</div>"
        )
    st.markdown(
        f"""
        <section class="opportunity-matrix">
            <header>
                <div>
                    <strong>Opportunity Matrix</strong>
                    <span>Ranking compacto por score, volumen, riesgo, target y estado operativo.</span>
                </div>
                <aside>
                    <b>{html.escape(summary['top_symbol'])}</b>
                    <small>{html.escape(summary['top_status'])} · Edge {html.escape(num_display(summary['top_edge'], 0))}</small>
                </aside>
            </header>
            <div class="matrix-summary">
                <div><span>Watch</span><strong>{summary['watch_count']}</strong></div>
                <div><span>Riesgo limpio</span><strong>{summary['low_risk']}</strong></div>
                <div><span>Volumen vivo</span><strong>{summary['volume_count']}</strong></div>
            </div>
            <div class="matrix-grid">{''.join(cards)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def confluence_validation_rows(confluence_df: pd.DataFrame, *, limit: int = 10) -> pd.DataFrame:
    columns = ["symbol", "tone", "decision", "trigger", "trend", "htf", "risk", "target_2pct", "backtest", "reason"]
    if confluence_df.empty:
        return pd.DataFrame(columns=columns)
    data = confluence_df.copy()
    if "confluence_score" in data.columns:
        data["sort_score"] = pd.to_numeric(data["confluence_score"], errors="coerce").fillna(0)
        data = data.sort_values("sort_score", ascending=False)
    rows: list[dict[str, Any]] = []
    for _, item in data.head(max(limit * 2, limit)).iterrows():
        row = item.to_dict()
        symbol = text_display(row.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        signal = text_display(row.get("signal")).upper()
        trade_decision = text_display(row.get("trade_decision")).upper()
        if signal == "BUY" and trade_decision.startswith("TRADE_FOR"):
            tone, decision = "buy", "Validado"
        elif signal == "AVOID" or trade_decision.startswith("NO_TRADE"):
            tone, decision = "avoid", "Bloqueado"
        else:
            tone, decision = "watch", "Esperar"
        confirmations = safe_float(row.get("higher_tf_confirmations"))
        blocks = safe_float(row.get("higher_tf_blocks"))
        if confirmations is not None or blocks is not None:
            htf = f"{int(confirmations or 0)}/{int((confirmations or 0) + (blocks or 0))}"
        else:
            htf = text_display(row.get("higher_tf_bias"))
        target_ok = row.get("target_2pct_ok")
        if isinstance(target_ok, str):
            target_ok = target_ok.strip().lower() in {"true", "1", "yes"}
        target_label = "2% OK" if bool(target_ok) else "2% falta"
        backtest_eligible = row.get("backtest_eligible")
        if isinstance(backtest_eligible, str):
            backtest_eligible = backtest_eligible.strip().lower() in {"true", "1", "yes"}
        profit_factor = safe_float(row.get("backtest_profit_factor"))
        backtest_label = f"PF {profit_factor:.1f}" if profit_factor is not None and bool(backtest_eligible) else "No hist"
        rows.append(
            {
                "symbol": symbol,
                "tone": tone,
                "decision": decision,
                "trigger": text_display(row.get("trigger_setup")),
                "trend": text_display(row.get("trend_setup")),
                "htf": htf,
                "risk": safe_float(row.get("risk_pct")),
                "target_2pct": target_label,
                "backtest": backtest_label,
                "reason": text_display(row.get("reasons")),
            }
        )
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows, columns=columns)


def render_confluence_validation_board(confluence_df: pd.DataFrame) -> None:
    rows = confluence_validation_rows(confluence_df, limit=10)
    if rows.empty:
        return
    items = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        items.append(
            f'<div class="validation-row validation-row-{html.escape(tone)}">'
            f'<strong>{html.escape(text_display(row.get("symbol")))}</strong>'
            f'<span>{html.escape(text_display(row.get("decision")))}</span>'
            f'<small>{html.escape(text_display(row.get("trigger")))} / {html.escape(text_display(row.get("trend")))}</small>'
            f'<em>HTF {html.escape(text_display(row.get("htf")))} · R {html.escape(pct_display(row.get("risk")))} · {html.escape(text_display(row.get("target_2pct")))} · {html.escape(text_display(row.get("backtest")))}</em>'
            f'<i>{html.escape(text_display(row.get("reason")))}</i>'
            "</div>"
        )
    st.markdown(
        '<section class="validation-board"><header><strong>Validación multi-timeframe</strong><span>15m gatillo · 1h tendencia · 2h/4h bloqueo · backtest · target 2%</span></header><div class="validation-grid">'
        + "".join(items)
        + "</div></section>",
        unsafe_allow_html=True,
    )


def render_finviz_style_wallboard(table: pd.DataFrame, confluence_df: pd.DataFrame, brief: dict) -> None:
    rows = scanner_wallboard_rows(table, confluence_df, limit=32)
    if rows.empty:
        return
    summary = scanner_wallboard_summary(rows)
    status = read_summary_json("alerts/roxy_status.json")
    daily_line = (
        f"Plan diario: {status.get('daily_plan_top_symbol', summary['top_symbol'])} · "
        f"{status.get('daily_plan_proxima_entrada', summary['watch'])} próximas entradas · "
        f"{status.get('daily_plan_operar_ahora', summary['ready'])} operar ahora"
        if status
        else f"{summary['total']} candidatos · top {summary['top_symbol']}"
    )
    freshness = brief.get("source_freshness") if isinstance(brief.get("source_freshness"), dict) else {}
    session = brief.get("market_session") if isinstance(brief.get("market_session"), dict) else {}
    top_tiles = rows.head(24).to_dict("records")
    tile_html = []
    for row in top_tiles:
        score = safe_float(row.get("score")) or 0
        score_alpha = min(0.92, max(0.24, score / 125.0))
        tone = text_display(row.get("tone"))
        tile_html.append(
            f'<div class="wall-tile wall-tile-{html.escape(tone)}" style="--tile-alpha:{score_alpha:.2f}">'
            f'<strong>{html.escape(text_display(row.get("symbol")))}</strong>'
            f'<span>{html.escape(num_display(row.get("score"), 0))}</span>'
            f'<small>{html.escape(text_display(row.get("strategy")))}</small>'
            f'<em>R {html.escape(pct_display(row.get("risk")))} · V {html.escape(num_display(row.get("rel_volume"), 1))}x</em>'
            "</div>"
        )
    def _mini_table(title: str, data: pd.DataFrame) -> str:
        body = []
        for row in data.head(7).to_dict("records"):
            body.append(
                "<tr>"
                f"<td>{html.escape(text_display(row.get('symbol')))}</td>"
                f"<td>{html.escape(text_display(row.get('status')))}</td>"
                f"<td>{html.escape(num_display(row.get('score'), 0))}</td>"
                f"<td>{html.escape(pct_display(row.get('risk')))}</td>"
                "</tr>"
            )
        return (
            f'<section class="wall-table"><header>{html.escape(title)}</header>'
            "<table><thead><tr><th>Ticker</th><th>Estado</th><th>Score</th><th>Riesgo</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table></section>"
        )
    score_table = rows.assign(_score=pd.to_numeric(rows["score"], errors="coerce").fillna(0)).sort_values("_score", ascending=False)
    volume_table = rows.assign(_volume=pd.to_numeric(rows["rel_volume"], errors="coerce").fillna(0)).sort_values("_volume", ascending=False)
    risk_table = rows.assign(_risk=pd.to_numeric(rows["risk"], errors="coerce").fillna(99)).sort_values(["_risk", "symbol"], ascending=[True, True])
    st.markdown(
        f"""
        <section class="finviz-wallboard">
            <div class="wall-ticker">
                <strong>ROXY MARKET WALL</strong>
                <span>{html.escape(daily_line)}</span>
                <span>{html.escape(text_display(session.get('stock_session') or session.get('crypto_session')))} · {html.escape(text_display(freshness.get('label')))}</span>
            </div>
            <div class="wall-stats">
                <div><span>Total</span><strong>{summary['total']}</strong><small>{html.escape(summary['top_strategy'])}</small></div>
                <div class="wall-stat-buy"><span>Operar</span><strong>{summary['ready']}</strong><small>confirmadas</small></div>
                <div class="wall-stat-watch"><span>Vigilar</span><strong>{summary['watch']}</strong><small>gatillo pendiente</small></div>
                <div class="wall-stat-avoid"><span>Evitar</span><strong>{summary['avoid']}</strong><small>bloqueadas</small></div>
                <div><span>Score avg</span><strong>{html.escape(num_display(summary['avg_score'], 0))}</strong><small>riesgo {html.escape(pct_display(summary['avg_risk']))}</small></div>
            </div>
            <div class="wall-main">
                <div class="wall-heatmap">{''.join(tile_html)}</div>
                <div class="wall-tables">
                    {_mini_table("Top Score", score_table)}
                    {_mini_table("Volumen Relativo", volume_table)}
                    {_mini_table("Riesgo Bajo", risk_table)}
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def mini_opportunity_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit: int = 4) -> pd.DataFrame:
    columns = ["symbol", "status", "tone", "market", "edge", "score", "risk", "target", "strategy", "next"]
    rows = scanner_wallboard_rows(table, confluence_df, limit=max(limit * 2, limit))
    if rows.empty:
        return pd.DataFrame(columns=columns)
    display = rows.copy()
    display["edge_sort"] = pd.to_numeric(
        display.get("edge", pd.Series(0, index=display.index)), errors="coerce"
    ).fillna(0)
    display["score_sort"] = pd.to_numeric(display["score"], errors="coerce").fillna(0)
    display["status_order"] = display["status"].map({"Operar": 0, "Vigilar": 1, "Evitar": 2}).fillna(1)
    display = display.sort_values(["status_order", "edge_sort", "score_sort"], ascending=[True, False, False]).head(limit)
    return display[[col for col in columns if col in display.columns]].reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_symbol_mini_chart(symbol: str, *, limit: int = 90) -> pd.DataFrame:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        return pd.DataFrame()
    try:
        history = get_ohlcv(clean_symbol)
    except Exception:
        return pd.DataFrame()
    if history.empty:
        return pd.DataFrame()
    data = history.reset_index().tail(max(12, int(limit))).copy()
    if "ts" not in data.columns:
        data = data.rename(columns={data.columns[0]: "ts"})
    return prepare_chart_window(data, limit=limit)


def mini_chart_status_label(chart_df: pd.DataFrame) -> str:
    window = prepare_chart_window(chart_df, limit=90)
    if window.empty:
        return "Sin mini historial · revisar proveedor"
    latest = "-"
    if "ts" in window.columns:
        try:
            ts_values = pd.to_datetime(window["ts"], errors="coerce").dropna()
            if not ts_values.empty:
                latest = pd.Timestamp(ts_values.max()).strftime("%m/%d %H:%M")
        except Exception:
            latest = "-"
    return f"{len(window)} velas · última {latest}"


def build_mini_opportunity_chart(chart_df: pd.DataFrame, tone: str = "watch") -> alt.Chart | alt.LayerChart:
    window = prepare_chart_window(chart_df, limit=90)
    if window.empty:
        fallback = pd.DataFrame(
            {
                "x": [0],
                "y": [0],
                "message": ["Sin historial local"],
                "action": ["Validar proveedor / recargar scanner"],
            }
        )
        base = alt.Chart(fallback).encode(
            x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[-1, 1])),
            y=alt.Y("y:Q", axis=None, scale=alt.Scale(domain=[-1, 1])),
        )
        panel = (
            alt.Chart(pd.DataFrame({"x": [0], "y": [0]}))
            .mark_rect(color="#0f172a", opacity=0.92)
            .encode(x=alt.value(0), x2=alt.value(520), y=alt.value(0), y2=alt.value(92))
        )
        title = base.mark_text(color="#f8fafc", fontSize=12, fontWeight="bold", dy=-8).encode(text="message:N")
        action = base.mark_text(color="#94a3b8", fontSize=10, dy=12).encode(text="action:N")
        return (panel + title + action).properties(height=92)
    color = {"buy": "#22c55e", "avoid": "#ef4444", "watch": "#f59e0b"}.get(str(tone), "#38bdf8")
    hover = alt.selection_point(name="mini_hover", fields=["ts"], nearest=True, on="pointerover", empty=False)
    area = (
        alt.Chart(window)
        .mark_area(line=False, opacity=0.16, color=color)
        .encode(
            x=alt.X("ts:T", title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)),
            y=alt.Y(
                "close:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(labels=False, ticks=False, grid=False)
            ),
        )
    )
    line = (
        alt.Chart(window)
        .mark_line(color=color, strokeWidth=2)
        .encode(
            x=alt.X("ts:T", title=None),
            y=alt.Y("close:Q", title=None, scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("ts:T", title="Tiempo"),
                alt.Tooltip("open:Q", title="Open", format=".2f"),
                alt.Tooltip("high:Q", title="High", format=".2f"),
                alt.Tooltip("low:Q", title="Low", format=".2f"),
                alt.Tooltip("close:Q", title="Close", format=".2f"),
                alt.Tooltip("volume:Q", title="Volumen", format=",.0f"),
            ],
        )
    )
    selectors = (
        alt.Chart(window)
        .mark_point(opacity=0)
        .encode(x="ts:T", y=alt.Y("close:Q", scale=alt.Scale(zero=False)))
        .add_params(hover)
    )
    hover_rule = (
        alt.Chart(window)
        .mark_rule(color="#94a3b8", strokeDash=[3, 3])
        .encode(
            x="ts:T",
            opacity=alt.condition(hover, alt.value(0.65), alt.value(0)),
            tooltip=[
                alt.Tooltip("ts:T", title="Tiempo"),
                alt.Tooltip("open:Q", title="Open", format=".2f"),
                alt.Tooltip("high:Q", title="High", format=".2f"),
                alt.Tooltip("low:Q", title="Low", format=".2f"),
                alt.Tooltip("close:Q", title="Close", format=".2f"),
                alt.Tooltip("volume:Q", title="Volumen", format=",.0f"),
            ],
        )
    )
    hover_point = (
        alt.Chart(window)
        .mark_point(filled=True, size=70, color=color, stroke="#f8fafc", strokeWidth=1.3)
        .encode(
            x="ts:T",
            y=alt.Y("close:Q", scale=alt.Scale(zero=False)),
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        )
    )
    last_point = (
        alt.Chart(window.tail(1))
        .mark_point(filled=True, size=55, color=color, stroke="#0b1220", strokeWidth=1.2)
        .encode(
            x="ts:T",
            y=alt.Y("close:Q", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("close:Q", title="Ultimo", format=".2f")],
        )
    )
    return (area + line + selectors + hover_rule + hover_point + last_point).interactive(bind_y=False).properties(height=92)


def top_opportunity_card_details(row: dict[str, Any]) -> dict[str, str]:
    next_action = text_display(row.get("next"))
    if next_action == "-":
        status = text_display(row.get("status"))
        if status == "Operar":
            next_action = "Confirmar ticket manual, stop y tamaño."
        elif status == "Evitar":
            next_action = "No tocar hasta que desbloquee riesgo/estructura."
        else:
            next_action = "Esperar gatillo 15m/confirmación 1h."
    edge_value = safe_float(row.get("edge"))
    edge_width = max(6.0, min(100.0, edge_value or 0.0))
    return {
        "edge": num_display(edge_value, 0),
        "edge_width": f"{edge_width:.0f}",
        "metrics": (
            f"Score {num_display(row.get('score'), 0)} · "
            f"Riesgo {pct_display(row.get('risk'))} · "
            f"Target {pct_display(row.get('target'))}"
        ),
        "route": f"{text_display(row.get('market')).upper()} · {text_display(row.get('status'))}",
        "next": next_action,
    }


def render_top_opportunity_cards(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = mini_opportunity_rows(table, confluence_df, limit=4)
    if rows.empty:
        return
    st.markdown(
        '<section class="top-opps-header"><strong>Top oportunidades</strong><span>Sparklines locales · hover para precios previos · click para cargar plan</span></section>',
        unsafe_allow_html=True,
    )
    cols = st.columns(len(rows))
    for idx, row in enumerate(rows.to_dict("records")):
        symbol = text_display(row.get("symbol")).upper()
        tone = text_display(row.get("tone"))
        market = text_display(row.get("market"))
        with cols[idx]:
            details = top_opportunity_card_details(row)
            mini_df = load_symbol_mini_chart(symbol)
            mini_status = mini_chart_status_label(mini_df)
            st.markdown(
                f"""
                <div class="top-opp-card top-opp-{html.escape(tone)}">
                    <div><span>{html.escape(text_display(row.get("status")))}</span><strong>{html.escape(symbol)}</strong></div>
                    <em class="top-opp-route">{html.escape(details["route"])}</em>
                    <div class="top-opp-meter"><span style="width:{html.escape(details["edge_width"])}%"></span><em>Edge {html.escape(details["edge"])}</em></div>
                    <p>{html.escape(text_display(row.get("strategy")))}</p>
                    <small>{html.escape(details["metrics"])}</small>
                    <small class="top-opp-next">Siguiente: {html.escape(details["next"])}</small>
                    <small class="top-opp-mini-status">{html.escape(mini_status)}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.altair_chart(
                build_mini_opportunity_chart(mini_df, tone=tone), use_container_width=True
            )
            if st.button("Cargar plan", key=f"top_opp_load_{idx}_{safe_key(symbol)}", use_container_width=True):
                st.session_state["command_symbol_pending"] = symbol
                st.session_state["command_market_pending"] = (
                    "crypto" if "/" in symbol or market.lower().startswith("crypto") else "stock"
                )
                st.rerun()


def market_movers_tape_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit_per_group: int = 5) -> pd.DataFrame:
    columns = ["group", "tone", "symbol", "status", "score", "risk", "rel_volume", "strategy", "next"]
    rows = scanner_wallboard_rows(table, confluence_df, limit=max(limit_per_group * 8, 32))
    if rows.empty:
        return pd.DataFrame(columns=columns)
    data = rows.copy()
    data["score_sort"] = pd.to_numeric(data["score"], errors="coerce").fillna(0)
    data["risk_sort"] = pd.to_numeric(data["risk"], errors="coerce")
    data["volume_sort"] = pd.to_numeric(data["rel_volume"], errors="coerce").fillna(0)
    groups: list[tuple[str, str, pd.DataFrame]] = [
        ("Top Score", "buy", data.sort_values(["score_sort", "volume_sort"], ascending=[False, False])),
        ("Volumen", "watch", data.sort_values(["volume_sort", "score_sort"], ascending=[False, False])),
        ("Riesgo Bajo", "buy", data.dropna(subset=["risk_sort"]).sort_values(["risk_sort", "score_sort"], ascending=[True, False])),
        ("Gatillo Cerca", "watch", data[data["status"].eq("Vigilar")].sort_values(["score_sort", "volume_sort"], ascending=[False, False])),
        ("No Tocar", "avoid", data[data["status"].eq("Evitar")].sort_values(["risk_sort", "score_sort"], ascending=[False, False])),
    ]
    output: list[dict[str, Any]] = []
    for group, tone, group_rows in groups:
        for _, item in group_rows.head(max(1, int(limit_per_group))).iterrows():
            row = item.to_dict()
            output.append(
                {
                    "group": group,
                    "tone": tone,
                    "symbol": text_display(row.get("symbol")).upper(),
                    "status": text_display(row.get("status")),
                    "score": safe_float(row.get("score")),
                    "risk": safe_float(row.get("risk")),
                    "rel_volume": safe_float(row.get("rel_volume")),
                    "strategy": text_display(row.get("strategy")),
                    "next": text_display(row.get("next")),
                }
            )
    return pd.DataFrame(output, columns=columns)


def render_market_movers_tape(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = market_movers_tape_rows(table, confluence_df, limit_per_group=5)
    if rows.empty:
        return
    sections = []
    for group in ["Top Score", "Volumen", "Riesgo Bajo", "Gatillo Cerca", "No Tocar"]:
        group_rows = rows[rows["group"].eq(group)].to_dict("records")
        if not group_rows:
            continue
        tone = text_display(group_rows[0].get("tone"))
        body = []
        for row in group_rows:
            body.append(
                "<tr>"
                f"<td>{html.escape(text_display(row.get('symbol')))}</td>"
                f"<td>{html.escape(num_display(row.get('score'), 0))}</td>"
                f"<td>{html.escape(num_display(row.get('rel_volume'), 1))}x</td>"
                f"<td>{html.escape(pct_display(row.get('risk')))}</td>"
                f"<td>{html.escape(text_display(row.get('next')))}</td>"
                "</tr>"
            )
        sections.append(
            f'<section class="market-mover-table market-mover-{html.escape(tone)}">'
            f"<header>{html.escape(group)}</header>"
            "<table><thead><tr><th>Ticker</th><th>Score</th><th>RVol</th><th>Riesgo</th><th>Next</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table></section>"
        )
    st.markdown(
        '<section class="market-movers-tape"><header><strong>Market Movers Tape</strong><span>Listas rápidas tipo Finviz para decidir dónde mirar primero.</span></header><div class="market-mover-grid">'
        + "".join(sections)
        + "</div></section>",
        unsafe_allow_html=True,
    )



def scanner_breadth_summary(scan_df: pd.DataFrame, confluence_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def ratio_row(label: str, positive: int, total: int, detail: str, tone: str = "neutral") -> None:
        pct = (positive / total * 100.0) if total else None
        rows.append(
            {
                "label": label,
                "positive": int(positive),
                "total": int(total),
                "pct": pct,
                "detail": detail,
                "tone": tone,
            }
        )

    if not scan_df.empty:
        scan = scan_df.copy()
        total = int(len(scan))
        signal_series = scan["signal"].astype(str).str.upper() if "signal" in scan.columns else pd.Series(dtype=str)
        raw_series = scan["raw_signal"].astype(str).str.upper() if "raw_signal" in scan.columns else signal_series
        score_values = pd.to_numeric(scan.get("score", pd.Series(dtype=float)), errors="coerce")
        sma200_values = pd.to_numeric(scan.get("dist_sma200_pct", pd.Series(dtype=float)), errors="coerce")
        rel_volume_values = pd.to_numeric(scan.get("relative_volume", pd.Series(dtype=float)), errors="coerce")
        ratio_row("BUY crudo", int(raw_series.eq("BUY").sum()), total, "gatillos tecnicos vivos", "buy")
        ratio_row("Sobre SMA200", int(sma200_values.gt(0).sum()), int(sma200_values.notna().sum()), "estructura mayor", "buy")
        ratio_row("Score >=80", int(score_values.ge(80).sum()), int(score_values.notna().sum()), "calidad tecnica", "watch")
        ratio_row("Volumen >1.2x", int(rel_volume_values.ge(1.2).sum()), int(rel_volume_values.notna().sum()), "participacion real", "watch")
        if "tf" in scan.columns:
            tf_counts = scan["tf"].dropna().astype(str).value_counts()
            if not tf_counts.empty:
                rows.append(
                    {
                        "label": "Marco dominante",
                        "positive": int(tf_counts.iloc[0]),
                        "total": total,
                        "pct": tf_counts.iloc[0] / total * 100.0 if total else None,
                        "detail": str(tf_counts.index[0]),
                        "tone": "neutral",
                    }
                )
    if not confluence_df.empty:
        confluence = confluence_df.copy()
        total = int(len(confluence))
        signal_series = confluence["signal"].astype(str).str.upper() if "signal" in confluence.columns else pd.Series(dtype=str)
        score_values = pd.to_numeric(confluence.get("confluence_score", pd.Series(dtype=float)), errors="coerce")
        risk_values = pd.to_numeric(confluence.get("risk_pct", pd.Series(dtype=float)), errors="coerce")
        ratio_row("Confluencia BUY", int(signal_series.eq("BUY").sum()), total, "multi-timeframe", "buy")
        ratio_row("Riesgo <=3.5%", int(risk_values.le(0.035).sum()), int(risk_values.notna().sum()), "stop trabajable", "buy")
        ratio_row("Conf score >=75", int(score_values.ge(75).sum()), int(score_values.notna().sum()), "mejores candidatos", "watch")
    return rows


def render_market_breadth_strip(scan_df: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = scanner_breadth_summary(scan_df, confluence_df)
    if not rows:
        return
    cards = []
    for row in rows[:8]:
        pct = safe_float(row.get("pct"))
        fill = min(100.0, max(0.0, pct or 0.0))
        tone = text_display(row.get("tone"))
        value = f"{num_display(pct, 0)}%" if pct is not None else "-"
        count = f"{row.get('positive', 0)}/{row.get('total', 0)}"
        cards.append(
            f'<div class="breadth-card breadth-card-{html.escape(tone)}">'
            f'<div><strong>{html.escape(text_display(row.get("label")))}</strong><span>{html.escape(value)}</span></div>'
            f'<div class="breadth-bar"><i style="width:{fill:.1f}%"></i></div>'
            f'<small>{html.escape(count)} · {html.escape(text_display(row.get("detail")))}</small>'
            "</div>"
        )
    st.markdown(
        '<section class="breadth-strip"><header>Market Breadth</header><div class="breadth-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )


def market_index_strip_rows(scan_df: pd.DataFrame, confluence_df: pd.DataFrame) -> list[dict[str, Any]]:
    targets = [
        ("SPY", "S&P 500"),
        ("QQQ", "Nasdaq"),
        ("DIA", "Dow"),
        ("IWM", "Russell"),
        ("BTC/USD", "Bitcoin"),
        ("ETH/USD", "Ethereum"),
        ("SOL/USD", "Solana"),
    ]
    scan_lookup: dict[str, dict[str, Any]] = {}
    if not scan_df.empty and "symbol" in scan_df.columns:
        scan_data = scan_df.copy()
        if "score" in scan_data.columns:
            scan_data["sort_score"] = pd.to_numeric(scan_data["score"], errors="coerce").fillna(0)
            scan_data = scan_data.sort_values("sort_score", ascending=False)
        for _, item in scan_data.iterrows():
            row = item.to_dict()
            symbol = text_display(row.get("symbol")).upper()
            scan_lookup.setdefault(symbol, row)

    confluence_lookup: dict[str, dict[str, Any]] = {}
    if not confluence_df.empty and "symbol" in confluence_df.columns:
        confluence_data = confluence_df.copy()
        if "confluence_score" in confluence_data.columns:
            confluence_data["sort_score"] = pd.to_numeric(confluence_data["confluence_score"], errors="coerce").fillna(0)
            confluence_data = confluence_data.sort_values("sort_score", ascending=False)
        for _, item in confluence_data.iterrows():
            row = item.to_dict()
            symbol = text_display(row.get("symbol")).upper()
            confluence_lookup.setdefault(symbol, row)

    rows: list[dict[str, Any]] = []
    for symbol, label in targets:
        row = {**scan_lookup.get(symbol, {}), **confluence_lookup.get(symbol, {})}
        if not row:
            continue
        signal = text_display(row.get("signal")).upper()
        decision = text_display(row.get("trade_decision")).upper()
        if signal == "BUY" and decision.startswith("TRADE_FOR"):
            tone = "buy"
            status = "Operar"
        elif signal == "AVOID" or decision.startswith("NO_TRADE"):
            tone = "avoid"
            status = "Evitar"
        else:
            tone = "watch"
            status = "Vigilar"
        rows.append(
            {
                "symbol": symbol,
                "label": label,
                "status": status,
                "tone": tone,
                "score": safe_float(row.get("confluence_score") or row.get("score")),
                "risk": safe_float(row.get("risk_pct")),
                "relative_volume": safe_float(row.get("relative_volume_15m") or row.get("relative_volume")),
                "setup": dashboard_strategy_label(row),
                "tf": text_display(row.get("entry_tf") or row.get("tf")),
            }
        )
    return rows


def market_regime_summary(index_rows: list[dict[str, Any]]) -> dict[str, str]:
    if not index_rows:
        return {"label": "Sin contexto", "tone": "watch", "detail": "No hay datos de indices principales."}
    core_rows = [row for row in index_rows if row.get("symbol") in {"SPY", "QQQ", "DIA", "IWM"}] or index_rows
    tones = [str(row.get("tone") or "watch") for row in core_rows]
    avoid_count = tones.count("avoid")
    buy_count = tones.count("buy")
    watch_count = tones.count("watch")
    leaders = ", ".join(text_display(row.get("symbol")) for row in core_rows[:4])
    if avoid_count >= max(2, buy_count + watch_count):
        return {"label": "Risk-off", "tone": "avoid", "detail": f"Indices bloquean: {leaders}. Prioridad a esperar confirmacion."}
    if buy_count >= max(2, avoid_count + watch_count):
        return {"label": "Risk-on", "tone": "buy", "detail": f"Indices apoyan: {leaders}. Buscar setups con riesgo medido."}
    return {"label": "Mixto", "tone": "watch", "detail": f"Mercado dividido: {leaders}. Operar solo gatillos limpios."}


def render_market_index_strip(scan_df: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    rows = market_index_strip_rows(scan_df, confluence_df)
    if not rows:
        return
    regime = market_regime_summary(rows)
    cards = []
    for row in rows:
        tone = text_display(row.get("tone"))
        cards.append(
            f'<div class="index-card index-card-{html.escape(tone)}">'
            f'<div><span>{html.escape(text_display(row.get("label")))}</span><strong>{html.escape(text_display(row.get("symbol")))}</strong></div>'
            f'<em>{html.escape(text_display(row.get("status")))} · {html.escape(num_display(row.get("score"), 0))}</em>'
            f'<small>{html.escape(text_display(row.get("setup")))} · R {html.escape(pct_display(row.get("risk")))} · V {html.escape(num_display(row.get("relative_volume"), 1))}x</small>'
            "</div>"
        )
    st.markdown(
        f'<section class="index-strip"><header>Índices y crypto mayor</header>'
        f'<div class="regime-banner regime-banner-{html.escape(regime["tone"])}"><strong>{html.escape(regime["label"])}</strong><span>{html.escape(regime["detail"])}</span></div>'
        '<div class="index-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )


def technical_mover_rows(scan_df: pd.DataFrame, *, limit_per_lane: int = 5) -> pd.DataFrame:
    columns = ["lane", "tone", "symbol", "score", "setup", "move", "sma200", "rel_volume"]
    if scan_df.empty or "symbol" not in scan_df.columns:
        return pd.DataFrame(columns=columns)
    data = scan_df.copy()
    for col in ["score", "dist_sma20_pct", "dist_sma200_pct", "relative_volume"]:
        data[col] = pd.to_numeric(data.get(col, pd.Series(dtype=float)), errors="coerce")
    setup = data.get("setup", pd.Series("", index=data.index)).astype(str)
    signal = data.get("raw_signal", data.get("signal", pd.Series("", index=data.index))).astype(str).str.upper()
    data["setup_text"] = setup
    data["signal_text"] = signal
    lanes = [
        ("Ruptura", "buy", data[data["dist_sma20_pct"].ge(0) & data["dist_sma200_pct"].ge(0) & signal.isin(["BUY", "WATCH"])]),
        ("Pullback", "watch", data[data["dist_sma20_pct"].lt(0) & data["dist_sma200_pct"].ge(0)]),
        ("Debilidad", "avoid", data[data["dist_sma200_pct"].lt(0)]),
    ]
    rows: list[dict[str, Any]] = []
    for lane, tone, lane_df in lanes:
        if lane_df.empty:
            continue
        ranked = lane_df.assign(
            volume_sort=lane_df["relative_volume"].fillna(0),
            score_sort=lane_df["score"].fillna(0),
            move_abs=lane_df["dist_sma20_pct"].abs().fillna(0),
        )
        if lane == "Pullback":
            ranked = ranked.sort_values(["score_sort", "move_abs"], ascending=[False, True])
        elif lane == "Debilidad":
            ranked = ranked.sort_values(["dist_sma200_pct", "score_sort"], ascending=[True, False])
        else:
            ranked = ranked.sort_values(["score_sort", "volume_sort"], ascending=[False, False])
        for _, item in ranked.head(max(1, int(limit_per_lane))).iterrows():
            row = item.to_dict()
            rows.append(
                {
                    "lane": lane,
                    "tone": tone,
                    "symbol": text_display(row.get("symbol")).upper(),
                    "score": safe_float(row.get("score")),
                    "setup": dashboard_strategy_label(row),
                    "move": safe_float(row.get("dist_sma20_pct")),
                    "sma200": safe_float(row.get("dist_sma200_pct")),
                    "rel_volume": safe_float(row.get("relative_volume")),
                }
            )
    return pd.DataFrame(rows, columns=columns)


def render_technical_movers_strip(scan_df: pd.DataFrame) -> None:
    rows = technical_mover_rows(scan_df, limit_per_lane=5)
    if rows.empty:
        return
    sections = []
    for lane in ["Ruptura", "Pullback", "Debilidad"]:
        lane_rows = rows[rows["lane"].eq(lane)].to_dict("records")
        tone = text_display(lane_rows[0].get("tone") if lane_rows else "watch")
        body = []
        for row in lane_rows:
            body.append(
                "<tr>"
                f"<td>{html.escape(text_display(row.get('symbol')))}</td>"
                f"<td>{html.escape(num_display(row.get('score'), 0))}</td>"
                f"<td>{html.escape(num_display(row.get('move'), 1))}%</td>"
                f"<td>{html.escape(num_display(row.get('rel_volume'), 1))}x</td>"
                "</tr>"
            )
        empty = '<tr><td colspan="4">Sin candidatos</td></tr>' if not body else ""
        sections.append(
            f'<section class="mover-table mover-table-{html.escape(tone)}">'
            f"<header>{html.escape(lane)}</header>"
            "<table><thead><tr><th>Ticker</th><th>Score</th><th>SMA20</th><th>RVol</th></tr></thead>"
            f"<tbody>{''.join(body) or empty}</tbody></table></section>"
        )
    st.markdown(
        '<section class="technical-movers"><header>Movers técnicos del scanner</header><div class="mover-grid">'
        + "".join(sections)
        + "</div></section>",
        unsafe_allow_html=True,
    )


def trading_desk_rows(
    table: pd.DataFrame, confluence_df: pd.DataFrame, scan_df: pd.DataFrame, *, limit: int = 18
) -> pd.DataFrame:
    columns = [
        "#",
        "Prioridad",
        "Ticker",
        "Estado",
        "Paper",
        "Falta",
        "Edge",
        "Score",
        "Riesgo",
        "Target",
        "RVol",
        "HTF",
        "Mover",
        "Setup",
        "Siguiente",
        "Razón",
    ]
    matrix = scanner_opportunity_matrix_rows(table, confluence_df, limit=max(limit, 18))
    wall = scanner_wallboard_rows(table, confluence_df, limit=max(limit * 2, limit))
    if wall.empty and matrix.empty:
        return pd.DataFrame(columns=columns)
    edge_lookup = {text_display(row.get("symbol")).upper(): row for row in matrix.to_dict("records")}
    validation_lookup = {
        text_display(row.get("symbol")).upper(): row
        for row in confluence_validation_rows(confluence_df, limit=max(limit * 2, limit)).to_dict("records")
    }
    mover_lookup = {
        text_display(row.get("symbol")).upper(): row
        for row in technical_mover_rows(scan_df, limit_per_lane=max(6, limit // 2)).to_dict("records")
    }
    confluence_lookup: dict[str, dict[str, Any]] = {}
    if not confluence_df.empty and "symbol" in confluence_df.columns:
        confluence_data = confluence_df.copy()
        if "confluence_score" in confluence_data.columns:
            confluence_data["sort_score"] = pd.to_numeric(confluence_data["confluence_score"], errors="coerce").fillna(
                0
            )
            confluence_data = confluence_data.sort_values("sort_score", ascending=False)
        for _, row in confluence_data.iterrows():
            item = row.to_dict()
            confluence_lookup.setdefault(text_display(item.get("symbol")).upper(), item)
    rows: list[dict[str, Any]] = []
    for item in wall.to_dict("records"):
        symbol = text_display(item.get("symbol")).upper()
        edge_row = edge_lookup.get(symbol, {})
        validation = validation_lookup.get(symbol, {})
        mover = mover_lookup.get(symbol, {})
        confluence = confluence_lookup.get(symbol, {})
        paper_state = trading_desk_paper_state(
            status=text_display(item.get("status")),
            risk=safe_float(item.get("risk")) or safe_float(confluence.get("risk_pct")),
            target=safe_float(item.get("target")) or safe_float(confluence.get("recommended_target_pct")),
            rel_volume=safe_float(item.get("rel_volume"))
            or safe_float(confluence.get("relative_volume_15m") or confluence.get("relative_volume")),
            htf=text_display(validation.get("htf")),
        )
        score_value = safe_float(item.get("score"))
        risk_value = safe_float(item.get("risk")) or safe_float(confluence.get("risk_pct"))
        rel_volume_value = safe_float(item.get("rel_volume")) or safe_float(
            confluence.get("relative_volume_15m") or confluence.get("relative_volume")
        )
        next_step = text_display(item.get("next"))
        reason_text = text_display(validation.get("reason") or item.get("next"))
        rows.append(
            {
                "Ticker": symbol,
                "Estado": text_display(item.get("status")),
                "Paper": paper_state,
                "Falta": trading_desk_blocker_summary(text_display(item.get("status")), paper_state, next_step, reason_text),
                "Edge": safe_float(edge_row.get("edge")),
                "Score": score_value,
                "Riesgo": risk_value,
                "Target": safe_float(item.get("target")) or safe_float(confluence.get("recommended_target_pct")),
                "RVol": rel_volume_value,
                "HTF": text_display(validation.get("htf")),
                "Mover": text_display(mover.get("lane")),
                "Setup": text_display(item.get("strategy")),
                "Siguiente": next_step,
                "Razón": reason_text,
                "Prioridad": trading_desk_priority_label(
                    text_display(item.get("status")), paper_state, score_value, risk_value, rel_volume_value
                ),
            }
        )
    display = pd.DataFrame(rows)
    display["edge_sort"] = pd.to_numeric(display["Edge"], errors="coerce").fillna(-999)
    display["score_sort"] = pd.to_numeric(display["Score"], errors="coerce").fillna(0)
    display["status_order"] = display["Estado"].map({"Operar": 0, "Vigilar": 1, "Evitar": 2}).fillna(1)
    display = (
        display.sort_values(["status_order", "edge_sort", "score_sort"], ascending=[True, False, False])
        .head(limit)
        .reset_index(drop=True)
    )
    display["#"] = display.index + 1
    display["Edge"] = pd.to_numeric(display["Edge"], errors="coerce").map(
        lambda value: num_display(value, 0) if pd.notna(value) else "-"
    )
    display["Score"] = pd.to_numeric(display["Score"], errors="coerce").map(
        lambda value: num_display(value, 0) if pd.notna(value) else "-"
    )
    display["Riesgo"] = pd.to_numeric(display["Riesgo"], errors="coerce").map(
        lambda value: pct_display(value) if pd.notna(value) else "-"
    )
    display["Target"] = pd.to_numeric(display["Target"], errors="coerce").map(
        lambda value: pct_display(value) if pd.notna(value) else "-"
    )
    display["RVol"] = pd.to_numeric(display["RVol"], errors="coerce").map(
        lambda value: f"{value:.1f}x" if pd.notna(value) else "-"
    )
    display["HTF"] = display["HTF"].replace("", "-")
    display["Mover"] = display["Mover"].replace("", "-")
    return display[columns]


def trading_desk_paper_state(
    *,
    status: str,
    risk: float | None,
    target: float | None,
    rel_volume: float | None,
    htf: str,
) -> str:
    status_value = text_display(status)
    if status_value == "Evitar":
        return "No tocar"
    if status_value != "Operar":
        return "Setup"
    missing = []
    if risk is None or risk > 0.035:
        missing.append("riesgo")
    if target is None or target < 0.02:
        missing.append("target")
    if rel_volume is None or rel_volume < 0.8:
        missing.append("volumen")
    if text_display(htf).startswith("0/") or text_display(htf) == "-":
        missing.append("HTF")
    if missing:
        return "Bloq " + "/".join(missing[:2])
    return "Paper listo"

def trading_desk_blocker_summary(status: str, paper: str, next_step: str, reason: str) -> str:
    status_value = text_display(status)
    paper_value = text_display(paper)
    next_value = text_display(next_step)
    reason_value = text_display(reason)
    combined = f"{paper_value} {next_value} {reason_value}".lower()
    if status_value == "Evitar" or paper_value == "No tocar":
        return "No tocar"
    if paper_value == "Paper listo":
        return "Completo"
    if paper_value.startswith("Bloq"):
        raw_parts = [part.strip().lower() for part in paper_value.replace("Bloq", "", 1).split("/") if part.strip()]
        labels = {"riesgo": "Riesgo", "target": "Target 2%", "volumen": "Volumen", "tf": "TF mayor"}
        missing = [labels.get(part, part.title()) for part in raw_parts]
        return "Falta " + " + ".join(missing[:2]) if missing else "Falta validar"
    checks = [
        ("15m", "Falta 15m"),
        ("1h", "Falta 1h"),
        ("2h", "Falta 2h"),
        ("4h", "Falta 4h"),
        ("volumen", "Falta volumen"),
        ("target", "Falta target"),
        ("riesgo", "Falta riesgo"),
    ]
    for token, label in checks:
        if token in combined:
            return label
    return next_value if next_value != "-" else "Revisar setup"


def trading_desk_priority_label(
    status: str, paper: str, score: float | None, risk: float | None, rel_volume: float | None
) -> str:
    status_value = text_display(status)
    paper_value = text_display(paper)
    score_value = safe_float(score) or 0
    if status_value == "Evitar" or paper_value == "No tocar":
        return "⛔ No tocar"
    if status_value == "Operar" and paper_value == "Paper listo":
        return "🔥 Paper listo"
    if status_value == "Operar" and paper_value.startswith("Bloq"):
        return "⚠ Bloqueada"
    if status_value == "Operar":
        return "✅ Operar"
    if status_value == "Vigilar" and (score_value >= 85 or (safe_float(rel_volume) or 0) >= 1.2):
        return "👀 Alta vigilancia"
    if status_value == "Vigilar":
        return "👀 Vigilar"
    return "Radar"


def filter_trading_desk_display(
    rows: pd.DataFrame,
    *,
    status: str = "Todos",
    query: str = "",
    min_score: float = 0,
    preset: str = "Todos",
    blocker: str = "Todos",
) -> pd.DataFrame:
    if rows.empty:
        return rows
    filtered = rows.copy()
    preset = str(preset or "Todos")
    if preset == "Operar ahora" and "Estado" in filtered.columns:
        filtered = filtered[filtered["Estado"].astype(str).eq("Operar")]
    elif preset == "Paper listo" and "Paper" in filtered.columns:
        filtered = filtered[filtered["Paper"].astype(str).eq("Paper listo")]
    elif preset == "Alto score" and "Score" in filtered.columns:
        scores = pd.to_numeric(filtered["Score"], errors="coerce").fillna(0)
        filtered = filtered[scores.ge(85)]
    elif preset == "Bajo riesgo" and "Riesgo" in filtered.columns:
        risk = (
            pd.to_numeric(filtered["Riesgo"].astype(str).str.replace("%", "", regex=False), errors="coerce").fillna(999)
            / 100.0
        )
        filtered = filtered[risk.le(0.025)]
    elif preset == "Volumen vivo" and "RVol" in filtered.columns:
        volume = pd.to_numeric(filtered["RVol"].astype(str).str.replace("x", "", regex=False), errors="coerce").fillna(
            0
        )
        filtered = filtered[volume.ge(1.2)]
    elif preset == "No tocar" and "Estado" in filtered.columns:
        filtered = filtered[filtered["Estado"].astype(str).eq("Evitar")]
    if status != "Todos" and "Estado" in filtered.columns:
        filtered = filtered[filtered["Estado"].astype(str).eq(status)]
    if blocker != "Todos" and "Falta" in filtered.columns:
        filtered = filtered[filtered["Falta"].astype(str).eq(blocker)]
    if min_score and "Score" in filtered.columns:
        scores = pd.to_numeric(filtered["Score"], errors="coerce").fillna(0)
        filtered = filtered[scores.ge(float(min_score))]
    search = str(query or "").strip().lower()
    if search:
        searchable_columns = [
            col
            for col in ["Ticker", "Prioridad", "Paper", "Falta", "Setup", "Siguiente", "Razón", "Mover"]
            if col in filtered.columns
        ]
        if searchable_columns:
            mask = pd.Series(False, index=filtered.index)
            for column in searchable_columns:
                mask |= filtered[column].astype(str).str.lower().str.contains(search, regex=False, na=False)
            filtered = filtered[mask]
    filtered = filtered.reset_index(drop=True)
    if "#" in filtered.columns:
        filtered["#"] = filtered.index + 1
    return filtered


TRADING_DESK_PRESETS = ["Todos", "Operar ahora", "Paper listo", "Alto score", "Bajo riesgo", "Volumen vivo", "No tocar"]


def trading_desk_preset_counts(rows: pd.DataFrame) -> dict[str, int]:
    if rows.empty:
        return {preset: 0 for preset in TRADING_DESK_PRESETS}
    return {
        preset: len(rows) if preset == "Todos" else len(filter_trading_desk_display(rows, preset=preset))
        for preset in TRADING_DESK_PRESETS
    }


def trading_desk_summary(rows: pd.DataFrame) -> dict[str, Any]:
    if rows.empty:
        return {
            "visible": 0,
            "operar": 0,
            "vigilar": 0,
            "evitar": 0,
            "best_symbol": "-",
            "best_score": 0,
            "avg_risk": None,
            "volume_live": 0,
        }
    data = rows.copy()
    status = data.get("Estado", pd.Series("", index=data.index)).astype(str)
    score = pd.to_numeric(data.get("Score", pd.Series(0, index=data.index)), errors="coerce").fillna(0)
    risk = pd.to_numeric(data.get("Riesgo", pd.Series("", index=data.index)).astype(str).str.replace("%", "", regex=False), errors="coerce")
    volume = pd.to_numeric(data.get("RVol", pd.Series("", index=data.index)).astype(str).str.replace("x", "", regex=False), errors="coerce").fillna(0)
    data["_status_order"] = status.map({"Operar": 0, "Vigilar": 1, "Evitar": 2}).fillna(3)
    data["_score"] = score
    best = data.sort_values(["_status_order", "_score"], ascending=[True, False]).head(1)
    best_symbol = text_display(best.iloc[0].get("Ticker")) if not best.empty else "-"
    best_score = float(best.iloc[0].get("_score")) if not best.empty else 0
    return {
        "visible": len(data),
        "operar": int(status.eq("Operar").sum()),
        "vigilar": int(status.eq("Vigilar").sum()),
        "evitar": int(status.eq("Evitar").sum()),
        "best_symbol": best_symbol,
        "best_score": round(best_score, 0),
        "avg_risk": round(float(risk.dropna().mean()), 2) if not risk.dropna().empty else None,
        "volume_live": int(volume.ge(1.2).sum()),
    }

def trading_desk_blocker_counts(rows: pd.DataFrame, *, limit: int = 4) -> pd.DataFrame:
    columns = ["blocker", "count", "tone"]
    if rows.empty or "Falta" not in rows.columns:
        return pd.DataFrame(columns=columns)
    blockers = rows["Falta"].fillna("-").astype(str).str.strip()
    blockers = blockers[(blockers != "") & (blockers != "-")]
    if blockers.empty:
        return pd.DataFrame(columns=columns)
    data = []
    for blocker, count in blockers.value_counts().head(limit).items():
        if blocker == "Completo":
            tone = "buy"
        elif blocker == "No tocar":
            tone = "avoid"
        else:
            tone = "watch"
        data.append({"blocker": blocker, "count": int(count), "tone": tone})
    return pd.DataFrame(data, columns=columns)


def trading_desk_action_queue(rows: pd.DataFrame, *, limit: int = 3) -> pd.DataFrame:
    columns = ["rank", "ticker", "tone", "status", "paper", "score", "risk", "rvol", "setup", "action", "reason"]
    if rows.empty:
        return pd.DataFrame(columns=columns)
    data = rows.copy()
    status = data.get("Estado", pd.Series("", index=data.index)).astype(str)
    paper = data.get("Paper", pd.Series("", index=data.index)).astype(str)
    score = pd.to_numeric(data.get("Score", pd.Series(0, index=data.index)), errors="coerce").fillna(0)
    risk = pd.to_numeric(
        data.get("Riesgo", pd.Series("", index=data.index)).astype(str).str.replace("%", "", regex=False),
        errors="coerce",
    )
    rvol = pd.to_numeric(
        data.get("RVol", pd.Series("", index=data.index)).astype(str).str.replace("x", "", regex=False), errors="coerce"
    )
    data["_status_order"] = status.map({"Operar": 0, "Vigilar": 1, "Evitar": 2}).fillna(3)
    data["_paper_order"] = paper.map({"Paper listo": 0, "Setup": 1, "No tocar": 3}).fillna(2)
    data["_score"] = score
    data["_risk"] = risk
    data["_rvol"] = rvol
    ranked = data.sort_values(["_status_order", "_paper_order", "_score"], ascending=[True, True, False]).head(limit)
    queue: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked.to_dict("records"), start=1):
        row_status = text_display(row.get("Estado"))
        row_paper = text_display(row.get("Paper"))
        if row_status == "Operar" and row_paper == "Paper listo":
            tone = "buy"
            action = "Preparar paper: confirmar stop, target y tamaño."
        elif row_status == "Evitar" or row_paper == "No tocar":
            tone = "avoid"
            action = "No tocar hasta que cambie estructura."
        elif row_paper.startswith("Bloq"):
            tone = "watch"
            action = f"Resolver {row_paper.replace('Bloq ', '')} antes de paper."
        else:
            tone = "watch"
            action = text_display(row.get("Siguiente")) if text_display(row.get("Siguiente")) != "-" else "Esperar gatillo."
        queue.append(
            {
                "rank": idx,
                "ticker": text_display(row.get("Ticker")).upper(),
                "tone": tone,
                "status": row_status,
                "paper": row_paper,
                "score": safe_float(row.get("_score")),
                "risk": safe_float(row.get("_risk")),
                "rvol": safe_float(row.get("_rvol")),
                "setup": text_display(row.get("Setup")),
                "action": action,
                "reason": text_display(row.get("Razón")),
            }
        )
    return pd.DataFrame(queue, columns=columns)


def render_trading_desk_action_queue(rows: pd.DataFrame) -> None:
    queue = trading_desk_action_queue(rows, limit=3)
    if queue.empty:
        return
    cards = []
    for row in queue.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<article class="desk-queue-card desk-queue-{html.escape(tone)}">'
            f'<header><span>#{int(row.get("rank") or 0)}</span><strong>{html.escape(text_display(row.get("ticker")))}</strong><em>{html.escape(num_display(row.get("score"), 0))}</em></header>'
            f'<p>{html.escape(text_display(row.get("action")))}</p>'
            f'<small>{html.escape(text_display(row.get("status")))} · {html.escape(text_display(row.get("paper")))} · R {html.escape(num_display(row.get("risk"), 2))}% · RVOL {html.escape(num_display(row.get("rvol"), 1))}x</small>'
            f'<i>{html.escape(text_display(row.get("setup")))} · {html.escape(text_display(row.get("reason")))}</i>'
            "</article>"
        )
    st.markdown(
        '<section class="trading-desk-queue"><header><strong>Fila de ejecución</strong><span>Top 3 ordenados por estado, paper-readiness y score.</span></header><div>'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )


def render_trading_desk_focus_banner(rows: pd.DataFrame) -> None:
    queue = trading_desk_action_queue(rows, limit=1)
    if queue.empty:
        return
    row = queue.iloc[0].to_dict()
    tone = text_display(row.get("tone"))
    ticker = html.escape(text_display(row.get("ticker")))
    action = html.escape(text_display(row.get("action")))
    status = html.escape(text_display(row.get("status")))
    paper = html.escape(text_display(row.get("paper")))
    setup = html.escape(text_display(row.get("setup")))
    score = html.escape(num_display(row.get("score"), 0))
    reason = html.escape(text_display(row.get("reason")))
    st.markdown(
        f"""
        <section class="trading-desk-focus desk-focus-{html.escape(tone)}">
            <div>
                <span>Decisión inmediata</span>
                <strong>{ticker}</strong>
                <em>{status} · {paper} · Score {score}</em>
            </div>
            <p>{action}</p>
            <small>{setup} · {reason}</small>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_trading_desk_card_grid(rows: pd.DataFrame, *, limit: int = 6) -> None:
    if rows.empty:
        return
    cards = []
    for row in rows.head(limit).to_dict("records"):
        status = text_display(row.get("Estado"))
        paper = text_display(row.get("Paper"))
        blocker = text_display(row.get("Falta"))
        tone = "avoid" if status == "Evitar" or paper == "No tocar" else "buy" if paper == "Paper listo" else "watch"
        chip_tone = "buy" if blocker == "Completo" else "avoid" if blocker == "No tocar" else "watch"
        blocker_chips = "".join(
            f'<span class="desk-missing-chip desk-missing-{html.escape(chip_tone)}">{html.escape(part.strip())}</span>'
            for part in blocker.replace("Falta", "").replace("+", ",").split(",")
            if part.strip()
        ) or f'<span class="desk-missing-chip desk-missing-{html.escape(chip_tone)}">{html.escape(blocker)}</span>'
        cards.append(
            f'<article class="desk-opportunity-card desk-opportunity-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("Ticker")))}</strong><span>{html.escape(text_display(row.get("Prioridad")))}</span></header>'
            f'<div class="desk-card-metrics">'
            f'<b>{html.escape(text_display(row.get("Score")))}</b><em>Score</em>'
            f'<b>{html.escape(text_display(row.get("Riesgo")))}</b><em>Riesgo</em>'
            f'<b>{html.escape(text_display(row.get("RVol")))}</b><em>RVol</em>'
            f'</div>'
            f'<p>{html.escape(text_display(row.get("Falta")))}</p>'
            f'<div class="desk-missing-row">{blocker_chips}</div>'
            f'<small>{html.escape(text_display(row.get("Siguiente")))} · {html.escape(text_display(row.get("Setup")))}</small>'
            "</article>"
        )
    st.markdown(
        '<section class="desk-opportunity-grid">' + "".join(cards) + "</section>",
        unsafe_allow_html=True,
    )



def render_trading_desk_summary(rows: pd.DataFrame) -> None:
    summary = trading_desk_summary(rows)
    blocker_counts = trading_desk_blocker_counts(rows, limit=4)
    blocker_html = ""
    if not blocker_counts.empty:
        blocker_cards = []
        for row in blocker_counts.to_dict("records"):
            tone = text_display(row.get("tone"))
            blocker_cards.append(
                f'<div class="desk-chip desk-{html.escape(tone)}"><span>{html.escape(text_display(row.get("blocker")))}</span><strong>{int(row.get("count") or 0)}</strong><small>bloqueo visible</small></div>'
            )
        blocker_html = '<section class="trading-desk-strip trading-desk-blockers">' + "".join(blocker_cards) + "</section>"
    render_trading_desk_focus_banner(rows)
    st.markdown(
        '<section class="trading-desk-strip">'
        f'<div class="desk-chip desk-buy"><span>Operar</span><strong>{int(summary.get("operar") or 0)}</strong><small>listas visibles</small></div>'
        f'<div class="desk-chip desk-watch"><span>Vigilar</span><strong>{int(summary.get("vigilar") or 0)}</strong><small>esperando gatillo</small></div>'
        f'<div class="desk-chip desk-avoid"><span>Evitar</span><strong>{int(summary.get("evitar") or 0)}</strong><small>bloqueadas</small></div>'
        f'<div class="desk-chip"><span>Top</span><strong>{html.escape(text_display(summary.get("best_symbol")))}</strong><small>score {html.escape(num_display(summary.get("best_score"), 0))}</small></div>'
        f'<div class="desk-chip"><span>Riesgo prom</span><strong>{html.escape(num_display(summary.get("avg_risk"), 2))}%</strong><small>{int(summary.get("visible") or 0)} visibles</small></div>'
        f'<div class="desk-chip"><span>Volumen vivo</span><strong>{int(summary.get("volume_live") or 0)}</strong><small>RVol ≥ 1.2x</small></div>'
        "</section>",
        unsafe_allow_html=True,
    )
    if blocker_html:
        st.markdown(blocker_html, unsafe_allow_html=True)
    render_trading_desk_action_queue(rows)
    render_trading_desk_card_grid(rows)





def reset_trading_desk_filters() -> None:
    st.session_state["trading_desk_preset_filter"] = "Todos"
    st.session_state["trading_desk_status_filter"] = "Todos"
    st.session_state["trading_desk_blocker_filter"] = "Todos"
    st.session_state["trading_desk_score_filter"] = 0
    st.session_state["trading_desk_query_filter"] = ""


def render_trading_desk_filter_scope(
    visible_rows: int,
    total_rows: int,
    *,
    preset: str,
    status: str,
    blocker: str,
    min_score: int,
    query: str,
) -> None:
    active_filters: list[str] = []
    if text_display(preset) != "Todos":
        active_filters.append(f"Preset {text_display(preset)}")
    if text_display(status) != "Todos":
        active_filters.append(f"Estado {text_display(status)}")
    if text_display(blocker) != "Todos":
        active_filters.append(f"Falta {text_display(blocker)}")
    if int(min_score or 0) > 0:
        active_filters.append(f"Score ≥ {int(min_score)}")
    query_text = text_display(query)
    if query_text != "-":
        active_filters.append(f"Busca {query_text}")
    if not active_filters:
        return
    st.markdown(
        f"""
        <section class="trading-desk-filter-scope">
          <span>Vista filtrada</span>
          <strong>{int(visible_rows)} de {int(total_rows)}</strong>
          <p>{html.escape(" · ".join(active_filters[:5]))}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

def render_trading_desk_empty_filter_state(
    total_rows: int,
    *,
    preset: str,
    status: str,
    blocker: str,
    min_score: int,
    query: str,
) -> None:
    query_label = text_display(query) if text_display(query) != "-" else "sin búsqueda"
    st.markdown(
        f"""
        <section class="trading-desk-empty">
          <div>
            <span>Trading Desk sin resultados</span>
            <strong>0 visibles de {int(total_rows)}</strong>
            <p>El filtro actual es demasiado estrecho para las oportunidades cargadas.</p>
          </div>
          <ul>
            <li>Preset: {html.escape(text_display(preset))}</li>
            <li>Estado: {html.escape(text_display(status))} · Falta: {html.escape(text_display(blocker))}</li>
            <li>Score ≥ {int(min_score)} · Buscar: {html.escape(query_label)}</li>
          </ul>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Para recuperar la vista rápida: Preset Todos, Estado Todos, Falta Todos, Score min 0 y búsqueda vacía.")
    st.button(
        "Limpiar filtros y volver a todo",
        key="trading_desk_empty_reset",
        on_click=reset_trading_desk_filters,
        use_container_width=True,
    )

def render_trading_desk_table(table: pd.DataFrame, confluence_df: pd.DataFrame, scan_df: pd.DataFrame) -> None:
    rows = trading_desk_rows(table, confluence_df, scan_df, limit=18)
    if rows.empty:
        return
    st.markdown("**Trading Desk**")
    preset_counts = trading_desk_preset_counts(rows)
    preset_labels = {preset: f"{preset} ({preset_counts.get(preset, 0)})" for preset in TRADING_DESK_PRESETS}
    with st.expander("Filtros del Trading Desk", expanded=False):
        reset_col, hint_col = st.columns([0.28, 1.72])
        with reset_col:
            st.button(
                "Limpiar filtros",
                key="trading_desk_reset_filters",
                on_click=reset_trading_desk_filters,
                use_container_width=True,
            )
        with hint_col:
            st.caption("Usa filtros para aislar oportunidades; limpia para volver al ranking completo.")
        filter_cols = st.columns([0.72, 0.72, 0.8, 0.72, 1.2])
        with filter_cols[0]:
            preset_filter = st.selectbox(
                "Preset",
                TRADING_DESK_PRESETS,
                format_func=lambda preset: preset_labels.get(str(preset), str(preset)),
                key="trading_desk_preset_filter",
            )
        with filter_cols[1]:
            status_options = ["Todos"] + sorted(
                [status for status in rows["Estado"].dropna().astype(str).unique() if status and status != "-"]
            )
            status_filter = st.selectbox("Estado desk", status_options, key="trading_desk_status_filter")
        with filter_cols[2]:
            blocker_options = ["Todos"] + sorted(
                [value for value in rows["Falta"].dropna().astype(str).unique() if value and value != "-"]
            )
            blocker_filter = st.selectbox("Falta", blocker_options, key="trading_desk_blocker_filter")
        with filter_cols[3]:
            min_score = st.slider(
                "Score min", min_value=0, max_value=100, value=0, step=5, key="trading_desk_score_filter"
            )
        with filter_cols[4]:
            query = st.text_input("Buscar ticker/setup/falta", value="", key="trading_desk_query_filter")
    display_rows = filter_trading_desk_display(
        rows, status=status_filter, query=query, min_score=min_score, preset=preset_filter, blocker=blocker_filter
    )
    if display_rows.empty:
        render_trading_desk_empty_filter_state(
            len(rows),
            preset=preset_filter,
            status=status_filter,
            blocker=blocker_filter,
            min_score=min_score,
            query=query,
        )
        return
    render_trading_desk_filter_scope(
        len(display_rows),
        len(rows),
        preset=preset_filter,
        status=status_filter,
        blocker=blocker_filter,
        min_score=min_score,
        query=query,
    )
    render_trading_desk_summary(display_rows)
    with st.expander("Tabla completa del Trading Desk", expanded=False):
        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
            height=min(560, 58 + len(display_rows) * 28),
        )


def buy_gap_next_step(missing: list[str], ready: bool) -> str:
    if ready:
        return "Listo: revisar ticket manual, stop y tamaño antes de operar."
    if not missing:
        return "Esperar confirmación final antes de actuar."
    guidance = {
        "15m gatillo BUY": "Esperar vela 15m en BUY; no anticipar entrada.",
        "1h confirma": "Esperar que 1h confirme tendencia y estructura.",
        "2h/4h no bloquean": "Esperar desbloqueo multi-timeframe; no luchar contra HTF.",
        "riesgo <=3.5%": "Mejorar entrada/stop o descartar si el riesgo sigue alto.",
        "volumen acompaña": "Esperar volumen relativo >=0.8x antes de confiar.",
        "target 2% viable": "No operar hasta que el target mínimo 2% sea viable.",
        "backtest elegible": "Mantener en vigilancia; falta validación histórica.",
    }
    return guidance.get(missing[0], f"Resolver: {missing[0]}.")


def buy_readiness_gap_rows(confluence_df: pd.DataFrame, *, limit: int = 8) -> pd.DataFrame:
    columns = ["symbol", "tone", "ready", "readiness_pct", "missing_count", "passed_count", "next_step", "missing", "passed", "risk", "score", "decision"]
    if confluence_df.empty or "symbol" not in confluence_df.columns:
        return pd.DataFrame(columns=columns)
    data = confluence_df.copy()
    if "confluence_score" in data.columns:
        data["sort_score"] = pd.to_numeric(data["confluence_score"], errors="coerce").fillna(0)
        data = data.sort_values("sort_score", ascending=False)
    rows: list[dict[str, Any]] = []
    for _, item in data.head(max(limit * 3, limit)).iterrows():
        row = item.to_dict()
        symbol = text_display(row.get("symbol")).upper()
        if not symbol or symbol == "-":
            continue
        signal = text_display(row.get("signal")).upper()
        decision = text_display(row.get("trade_decision")).upper()
        risk = safe_float(row.get("risk_pct"))
        rel_volume = safe_float(row.get("relative_volume_15m") or row.get("relative_volume"))
        target_ok = row.get("target_2pct_ok")
        if isinstance(target_ok, str):
            target_ok = target_ok.strip().lower() in {"true", "1", "yes"}
        backtest_eligible = row.get("backtest_eligible")
        if isinstance(backtest_eligible, str):
            backtest_eligible = backtest_eligible.strip().lower() in {"true", "1", "yes"}
        confirmations = int(safe_float(row.get("higher_tf_confirmations")) or 0)
        blocks = int(safe_float(row.get("higher_tf_blocks")) or 0)
        checks = [
            ("15m gatillo BUY", signal == "BUY" or text_display(row.get("trigger_raw_signal")).upper() == "BUY"),
            ("1h confirma", text_display(row.get("trend_signal")).upper() in {"BUY", "WATCH"} and text_display(row.get("trend_setup")) != "-"),
            ("2h/4h no bloquean", blocks == 0 and confirmations >= 1),
            ("riesgo <=3.5%", risk is not None and risk <= 0.035),
            ("volumen acompaña", rel_volume is not None and rel_volume >= 0.8),
            ("target 2% viable", bool(target_ok)),
            ("backtest elegible", bool(backtest_eligible)),
        ]
        missing = [label for label, ok in checks if not ok]
        passed = [label for label, ok in checks if ok]
        ready = signal == "BUY" and decision.startswith("TRADE_FOR") and not missing
        readiness_pct = round((len(passed) / len(checks)) * 100) if checks else 0
        if ready:
            tone = "buy"
        elif decision.startswith("NO_TRADE") or signal == "AVOID":
            tone = "avoid"
        else:
            tone = "watch"
        rows.append(
            {
                "symbol": symbol,
                "tone": tone,
                "ready": ready,
                "readiness_pct": readiness_pct,
                "missing_count": len(missing),
                "passed_count": len(passed),
                "next_step": buy_gap_next_step(missing, ready),
                "missing": " · ".join(missing[:4]) if missing else "Listo para operar",
                "passed": " · ".join(passed[:4]) if passed else "-",
                "risk": risk,
                "score": safe_float(row.get("confluence_score")),
                "decision": text_display(row.get("trade_decision") or row.get("action")),
            }
        )
        if len(rows) >= limit:
            break
    result = pd.DataFrame(rows, columns=columns)
    if result.empty:
        return result
    result["tone_order"] = result["tone"].map({"buy": 0, "watch": 1, "avoid": 2}).fillna(1)
    result["score_sort"] = pd.to_numeric(result["score"], errors="coerce").fillna(0)
    result = result.sort_values(["tone_order", "missing_count", "score_sort"], ascending=[True, True, False]).head(limit)
    return result.drop(columns=["tone_order", "score_sort"]).reset_index(drop=True)

def buy_readiness_blocker_summary(confluence_df: pd.DataFrame) -> dict[str, Any]:
    gap_rows = buy_readiness_gap_rows(confluence_df, limit=50)
    if gap_rows.empty:
        return {
            "dominant": "-",
            "count": 0,
            "tone": "neutral",
            "ready": 0,
            "watch": 0,
            "avoid": 0,
            "avg_readiness": None,
            "next_step": "Sin datos suficientes para priorizar.",
            "symbols": "-",
        }
    blocker_counts: dict[str, int] = {}
    blocker_symbols: dict[str, list[str]] = {}
    for row in gap_rows.to_dict("records"):
        symbol = text_display(row.get("symbol")).upper()
        missing_text = text_display(row.get("missing"))
        if missing_text in {"-", "Listo para operar"}:
            continue
        for blocker in [part.strip() for part in missing_text.split("·") if part.strip()]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
            symbols = blocker_symbols.setdefault(blocker, [])
            if symbol and symbol not in symbols and len(symbols) < 5:
                symbols.append(symbol)
    if blocker_counts:
        dominant = sorted(blocker_counts, key=lambda item: (-blocker_counts[item], item))[0]
        count = blocker_counts[dominant]
        next_step = buy_gap_next_step([dominant], False)
        symbols_text = " · ".join(blocker_symbols.get(dominant, [])) or "-"
    else:
        dominant = "Listos para operar"
        count = int(gap_rows["ready"].fillna(False).astype(bool).sum())
        next_step = "Revisar ticket manual, stop, target y tamaño antes de operar."
        symbols_text = " · ".join(gap_rows["symbol"].astype(str).head(5).tolist())
    tones = gap_rows["tone"].astype(str).str.lower()
    avg_readiness = safe_float(pd.to_numeric(gap_rows["readiness_pct"], errors="coerce").mean())
    if dominant in {"riesgo <=3.5%", "2h/4h no bloquean"}:
        tone = "avoid"
    elif dominant == "Listos para operar":
        tone = "buy"
    elif count >= 3:
        tone = "watch"
    else:
        tone = "neutral"
    return {
        "dominant": dominant,
        "count": count,
        "tone": tone,
        "ready": int((tones == "buy").sum()),
        "watch": int((tones == "watch").sum()),
        "avoid": int((tones == "avoid").sum()),
        "avg_readiness": avg_readiness,
        "next_step": next_step,
        "symbols": symbols_text,
    }



def confirmation_radar_action(requirement: str) -> str:
    actions = {
        "15m gatillo BUY": "Esperar vela 15m con BUY real antes de entrar.",
        "1h confirma": "Validar que 1h sostenga tendencia/canal.",
        "2h/4h no bloquean": "No operar contra timeframes altos bloqueando.",
        "riesgo <=3.5%": "Mejorar entrada o descartar si stop queda amplio.",
        "volumen acompaña": "Esperar volumen relativo >= 0.8x.",
        "target 2% viable": "No entrar si el primer objetivo no paga el riesgo.",
        "backtest elegible": "Mantener en paper/watch hasta validar historial.",
    }
    return actions.get(text_display(requirement), f"Resolver {text_display(requirement)} antes de operar.")


def confirmation_radar_rows(confluence_df: pd.DataFrame, *, limit: int = 6) -> pd.DataFrame:
    columns = ["requirement", "tone", "missing_count", "top_symbols", "action"]
    gap_rows = buy_readiness_gap_rows(confluence_df, limit=50)
    if gap_rows.empty:
        return pd.DataFrame(columns=columns)
    grouped: dict[str, dict[str, Any]] = {}
    for row in gap_rows.to_dict("records"):
        symbol = text_display(row.get("symbol")).upper()
        missing_text = text_display(row.get("missing"))
        if missing_text in {"-", "Listo para operar"}:
            continue
        for requirement in [part.strip() for part in missing_text.split("·") if part.strip()]:
            item = grouped.setdefault(requirement, {"symbols": [], "count": 0})
            item["count"] += 1
            if symbol and symbol not in item["symbols"] and len(item["symbols"]) < 5:
                item["symbols"].append(symbol)
    rows: list[dict[str, Any]] = []
    for requirement, item in grouped.items():
        count = int(item["count"])
        if requirement in {"riesgo <=3.5%", "2h/4h no bloquean"}:
            tone = "avoid"
        elif count >= 3:
            tone = "watch"
        else:
            tone = "neutral"
        rows.append(
            {
                "requirement": requirement,
                "tone": tone,
                "missing_count": count,
                "top_symbols": " · ".join(item["symbols"]) if item["symbols"] else "-",
                "action": confirmation_radar_action(requirement),
            }
        )
    result = pd.DataFrame(rows, columns=columns)
    if result.empty:
        return result
    tone_order = result["tone"].map({"avoid": 0, "watch": 1, "neutral": 2}).fillna(2)
    result = result.assign(tone_order=tone_order).sort_values(["missing_count", "tone_order"], ascending=[False, True])
    return result.drop(columns=["tone_order"]).head(limit).reset_index(drop=True)


def render_confirmation_radar(confluence_df: pd.DataFrame) -> None:
    rows = confirmation_radar_rows(confluence_df, limit=6)
    if rows.empty:
        return
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<section class="confirm-radar-card confirm-radar-{html.escape(tone)}">'
            f'<header><strong>{html.escape(text_display(row.get("requirement")))}</strong><span>{int(row.get("missing_count") or 0)}</span></header>'
            f'<p>{html.escape(text_display(row.get("action")))}</p>'
            f'<small>{html.escape(text_display(row.get("top_symbols")))}</small>'
            "</section>"
        )
    st.markdown(
        '<section class="confirmation-radar"><header><strong>Confirmation Radar</strong><span>Bloqueos repetidos en el scanner: resuelve estos primero antes de perseguir oportunidades.</span></header><div class="confirm-radar-grid">'
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )



def render_buy_readiness_gap_panel(confluence_df: pd.DataFrame) -> None:
    rows = buy_readiness_gap_rows(confluence_df, limit=8)
    if rows.empty:
        return
    summary = buy_readiness_blocker_summary(confluence_df)
    summary_tone = text_display(summary.get("tone"))
    avg_readiness = summary.get("avg_readiness")
    readiness_label = "-" if avg_readiness is None else f"{avg_readiness:.0f}%"
    strip = (
        f'<div class="buy-gap-strip buy-gap-strip-{html.escape(summary_tone)}">'
        '<section><span>Bloqueo dominante</span>'
        f'<strong>{html.escape(text_display(summary.get("dominant")))}</strong>'
        f'<em>{int(summary.get("count") or 0)} tickers · readiness avg {html.escape(readiness_label)} · {html.escape(text_display(summary.get("symbols")))}</em></section>'
        '<section><span>Estado scanner</span>'
        f'<strong>{int(summary.get("ready") or 0)} operar · {int(summary.get("watch") or 0)} vigilar · {int(summary.get("avoid") or 0)} evitar</strong>'
        f'<em>{html.escape(text_display(summary.get("next_step")))}</em></section>'
        "</div>"
    )
    cards = []
    for row in rows.to_dict("records"):
        tone = text_display(row.get("tone"))
        cards.append(
            f'<div class="buy-gap-card buy-gap-{html.escape(tone)}">'
            f'<div><strong>{html.escape(text_display(row.get("symbol")))}</strong><span>{html.escape(text_display(row.get("decision")))}</span></div>'
            f'<em>{html.escape(num_display(row.get("readiness_pct"), 0))}% listo · {html.escape(str(row.get("missing_count")))} faltan · R {html.escape(pct_display(row.get("risk")))} · Score {html.escape(num_display(row.get("score"), 0))}</em>'
            f'<b class="buy-gap-progress"><u style="width:{max(0, min(100, safe_float(row.get("readiness_pct")) or 0)):.0f}%"></u></b>'
            f'<i>Siguiente: {html.escape(text_display(row.get("next_step")))}</i>'
            f'<small>Falta: {html.escape(text_display(row.get("missing")))}</small>'
            f'<i>OK: {html.escape(text_display(row.get("passed")))}</i>'
            "</div>"
        )
    st.markdown(
        '<section class="buy-gap-panel"><header><strong>Qué falta para BUY</strong><span>Diagnóstico directo antes de operar: gatillo, HTF, riesgo, volumen, target y backtest.</span></header><div class="buy-gap-grid">'
        + strip
        + "".join(cards)
        + "</div></section>",
        unsafe_allow_html=True,
    )



def scanner_blotter_rows(table: pd.DataFrame, confluence_df: pd.DataFrame, *, limit: int = 24) -> pd.DataFrame:
    wall_rows = scanner_wallboard_rows(table, confluence_df, limit=limit)
    columns = [
        "#",
        "Semáforo",
        "Acción",
        "Ticker",
        "Estado",
        "Edge",
        "Score",
        "Calidad",
        "Setup",
        "Riesgo",
        "Target",
        "RVol",
        "TF",
        "Qué falta",
    ]
    if wall_rows.empty:
        return pd.DataFrame(columns=columns)
    display = wall_rows.copy().head(limit).reset_index(drop=True)
    score = pd.to_numeric(display["score"], errors="coerce").fillna(0.0)
    risk = pd.to_numeric(display["risk"], errors="coerce").fillna(0.99)
    target = pd.to_numeric(display["target"], errors="coerce").fillna(0.0)
    rel_volume = pd.to_numeric(display["rel_volume"], errors="coerce").fillna(0.0)
    status_bonus = display["status"].map({"Operar": 18.0, "Vigilar": 8.0, "Evitar": -28.0}).fillna(0.0)
    edge = (
        score
        + (rel_volume.clip(0, 5) * 4.0)
        + (target.clip(0, 0.15) * 150.0)
        + status_bonus
        - (risk.clip(0, 0.20) * 180.0)
    ).round(1)
    display["#"] = display.index + 1
    display["Semáforo"] = [
        "🟢" if status == "Operar" else "🔴" if status == "Evitar" else "🟡"
        for status in display["status"].astype(str)
    ]
    display["Acción"] = [
        (
            "🔥 OPERAR"
            if status == "Operar"
            else (
                "👀 ESPERAR"
                if status == "Vigilar" and (score_value >= 85 or volume_value >= 1.2)
                else "⛔ NO TOCAR" if status == "Evitar" else "ESPERAR"
            )
        )
        for status, score_value, volume_value in zip(display["status"].astype(str), score, rel_volume)
    ]
    display["Ticker"] = display["symbol"].astype(str)
    display["Estado"] = display["status"].astype(str)
    display["Edge"] = edge
    display["Score"] = score.round(0).astype(int)
    display["Calidad"] = [
        "A+" if value >= 95 else "A" if value >= 80 else "B" if value >= 65 else "C" for value in edge
    ]
    display["Setup"] = display["strategy"].astype(str)
    display["Riesgo"] = pd.to_numeric(display["risk"], errors="coerce").map(
        lambda value: pct_display(value) if pd.notna(value) else "-"
    )
    display["Target"] = pd.to_numeric(display["target"], errors="coerce").map(
        lambda value: pct_display(value) if pd.notna(value) else "-"
    )
    display["RVol"] = pd.to_numeric(display["rel_volume"], errors="coerce").map(
        lambda value: f"{value:.1f}x" if pd.notna(value) else "-"
    )
    display["TF"] = display["tf"].astype(str)
    display["Qué falta"] = display["next"].astype(str)
    return display[columns]


def render_scanner_blotter(table: pd.DataFrame, confluence_df: pd.DataFrame) -> None:
    blotter = scanner_blotter_rows(table, confluence_df, limit=28)
    if blotter.empty:
        return
    ready_count = int(blotter["Estado"].eq("Operar").sum())
    watch_count = int(blotter["Estado"].eq("Vigilar").sum())
    avoid_count = int(blotter["Estado"].eq("Evitar").sum())
    top_symbol = text_display(blotter.iloc[0].get("Ticker")).upper()
    top_action = text_display(blotter.iloc[0].get("Acción"))
    st.markdown(
        f"""
        <section class="roxy-radar-head">
            <div><strong>Roxy Radar</strong><span>Tabla principal para decidir qué trabajar ahora.</span></div>
            <aside><b>{html.escape(top_symbol)}</b><small>{html.escape(top_action)} · {ready_count} operar · {watch_count} esperar · {avoid_count} no tocar</small></aside>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <section class="roxy-radar-guide">
            <div class="radar-guide-buy"><strong>OPERAR</strong><span>Confirmar ticket, stop, target y tamaño.</span></div>
            <div class="radar-guide-watch"><strong>ESPERAR</strong><span>No anticipar; esperar gatillo 15m/1h.</span></div>
            <div class="radar-guide-avoid"><strong>NO TOCAR</strong><span>Bloqueo activo: proteger capital.</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    filter_cols = st.columns([1.15, 1, 0.7])
    with filter_cols[0]:
        radar_filter = st.radio(
            "Filtro Roxy Radar",
            ["Todos", "Operar", "Esperar", "No tocar"],
            horizontal=True,
            label_visibility="collapsed",
            key="roxy_radar_action_filter",
        )
    with filter_cols[1]:
        quality_filter = st.radio(
            "Calidad Roxy Radar",
            ["Todas calidades", "A+ solamente", "A o mejor", "B o mejor"],
            horizontal=True,
            label_visibility="collapsed",
            key="roxy_radar_quality_filter",
        )
    with filter_cols[2]:
        depth_filter = st.radio(
            "Profundidad Roxy Radar",
            ["Top 8", "Top 16", "Todos"],
            horizontal=True,
            label_visibility="collapsed",
            key="roxy_radar_depth_filter",
        )
    visible_blotter = blotter
    if radar_filter != "Todos":
        action_key = {"Operar": "OPERAR", "Esperar": "ESPERAR", "No tocar": "NO TOCAR"}[radar_filter]
        visible_blotter = blotter[blotter["Acción"].astype(str).str.contains(action_key, regex=False)].reset_index(
            drop=True
        )
    if quality_filter != "Todas calidades":
        minimum_quality = {"A+ solamente": 3, "A o mejor": 2, "B o mejor": 1}[quality_filter]
        quality_rank = visible_blotter["Calidad"].map({"A+": 3, "A": 2, "B": 1, "C": 0}).fillna(0)
        visible_blotter = visible_blotter[quality_rank.ge(minimum_quality)].reset_index(drop=True)
    if visible_blotter.empty:
        st.caption("Sin oportunidades para estos filtros del Radar.")
        return
    total_after_filters = len(visible_blotter)
    if depth_filter != "Todos":
        visible_limit = int(depth_filter.split()[1])
        visible_blotter = visible_blotter.head(visible_limit).reset_index(drop=True)
    st.caption(
        f"Mostrando {len(visible_blotter)} de {total_after_filters} oportunidades filtradas. Cambia a Todos para investigacion."
    )
    quick_cols = st.columns(min(6, max(1, len(visible_blotter))))
    for idx, row in enumerate(visible_blotter.head(6).to_dict("records")):
        with quick_cols[idx]:
            symbol = text_display(row.get("Ticker")).upper()
            if st.button(
                f"{symbol} · {text_display(row.get('Acción'))}",
                key=f"blotter_load_{idx}_{safe_key(symbol)}",
                use_container_width=True,
            ):
                st.session_state["command_symbol_pending"] = symbol
                st.session_state["command_market_pending"] = "crypto" if "/" in symbol else "stock"
                st.rerun()
    radar_columns = [
        "Semáforo",
        "Ticker",
        "Acción",
        "Calidad",
        "Edge",
        "Score",
        "Riesgo",
        "Target",
        "RVol",
        "TF",
        "Setup",
        "Qué falta",
    ]
    radar_table = visible_blotter[radar_columns]
    st.dataframe(
        radar_table,
        use_container_width=True,
        hide_index=True,
        height=min(360, 58 + len(radar_table) * 27),
        column_config={
            "Semáforo": st.column_config.TextColumn("Semáforo", width="small"),
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "Edge": st.column_config.NumberColumn("Edge", format="%.0f"),
            "Acción": st.column_config.TextColumn("Acción", width="small"),
            "Calidad": st.column_config.TextColumn("Calidad", width="small"),
            "Qué falta": st.column_config.TextColumn("Qué falta", width="large"),
        },
    )


def render_scanner_cockpit(
    table: pd.DataFrame,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    brief: dict,
) -> None:
    summary = scanner_overview_summary(table, confluence_df, options_df, brief)
    if summary["ready"]:
        compass_tone = "buy"
        compass_label = "Trabajar ahora"
        compass_detail = f"{summary['ready']} setup(s) operables. Prioridad: {summary['top_symbol']}."
    elif summary["watch"]:
        compass_tone = "watch"
        compass_label = "Esperar gatillo"
        compass_detail = f"{summary['watch']} en vigilancia. Bloqueo dominante: {summary['top_gate']}."
    else:
        compass_tone = "avoid"
        compass_label = "No operar"
        compass_detail = "Sin setups limpios. Mantener capital y esperar nuevo scan."
    st.markdown(
        f"""
        <section class="scanner-tape">
            <div><strong>Roxy Scanner</strong><span>{summary['total']} setups · {summary['ready']} operables · {summary['watch']} en vigilancia · {summary['avoid']} evitados</span></div>
            <div><strong>Top</strong><span>{html.escape(summary['top_symbol'])} · {html.escape(summary['top_action'])} · {html.escape(summary['top_strategy'])}</span></div>
            <div><strong>Contexto</strong><span>{html.escape(summary['session'])} · {html.escape(summary['freshness'])}</span></div>
        </section>
        <section class="scanner-compass scanner-compass-{html.escape(compass_tone)}">
            <strong>{html.escape(compass_label)}</strong>
            <span>{html.escape(compass_detail)}</span>
            <em>Foco: operar solo lo limpio; lo demás queda en watchlist.</em>
        </section>
        """,
        unsafe_allow_html=True,
    )
    card_html = []
    for label, value, detail, tone in [
        ("Operables", summary["ready"], "Listas o casi listas para trabajar", "buy" if summary["ready"] else "neutral"),
        ("Watchlist", summary["watch"], f"Filtro dominante: {summary['top_gate']}", "watch" if summary["watch"] else "neutral"),
        ("Confluencia", summary["confluence_rows"], f"Score avg {num_display(summary['avg_score'], 0)}", "neutral"),
        ("Opciones", summary["option_candidates"], f"Readiness avg {num_display(summary['avg_readiness'], 0)}", "buy" if summary["option_candidates"] else "watch"),
    ]:
        tone = tone if tone in {"buy", "watch", "avoid", "neutral"} else "neutral"
        card_html.append(
            f'<div class="scanner-card scanner-card-{tone}">'
            f'<span>{html.escape(str(label))}</span>'
            f'<strong>{html.escape(text_display(value))}</strong>'
            f'<small>{html.escape(text_display(detail))}</small>'
            "</div>"
        )
    st.markdown('<div class="scanner-card-grid">' + "".join(card_html) + "</div>", unsafe_allow_html=True)

    lanes = scanner_action_lane_rows(table, limit_per_lane=3)
    if not lanes.empty:
        lane_html = []
        for lane_name in ["Ahora", "Esperar gatillo", "No tocar"]:
            lane_rows = lanes[lanes["lane"].eq(lane_name)].to_dict("records")
            tone = str(lane_rows[0].get("tone") if lane_rows else "neutral")
            items = []
            for row in lane_rows:
                risk = safe_float(row.get("risk"))
                target = safe_float(row.get("target"))
                detail = f"R {pct_display(risk)} · T {pct_display(target)} · {text_display(row.get('strategy'))}"
                items.append(
                    '<div class="scanner-lane-row">'
                    f'<strong>{html.escape(text_display(row.get("symbol")))}</strong>'
                    f'<span>{html.escape(text_display(row.get("action")))} · {html.escape(num_display(row.get("score"), 0))}</span>'
                    f'<small>{html.escape(detail)}</small>'
                    f'<em>{html.escape(text_display(row.get("trigger")))}</em>'
                    "</div>"
                )
            empty = '<div class="scanner-lane-empty">Sin setups en este carril</div>' if not items else ""
            lane_html.append(
                f'<section class="scanner-lane scanner-lane-{html.escape(tone)}">'
                f'<header>{html.escape(lane_name)}</header>'
                + "".join(items)
                + empty
                + "</section>"
            )
        st.markdown('<div class="scanner-lane-grid">' + "".join(lane_html) + "</div>", unsafe_allow_html=True)

    with st.expander("Explorar scanner con filtros", expanded=False):
        markets = ["Todos"]
        if not table.empty and "market" in table.columns:
            markets.extend(sorted({text_display(value) for value in table["market"].dropna().tolist() if text_display(value) != "-"}))
        filter_cols = st.columns([0.8, 0.8, 1.0, 1.0])
        with filter_cols[0]:
            bucket_filter = st.selectbox("Estado", ["Todos", "Operar", "Vigilar", "Evitar"], key="scanner_explorer_bucket")
        with filter_cols[1]:
            market_filter = st.selectbox("Mercado", markets, key="scanner_explorer_market")
        with filter_cols[2]:
            strategy_filter = st.selectbox("Estrategia", scanner_strategy_options(table), key="scanner_explorer_strategy")
        with filter_cols[3]:
            readiness_filter = st.slider("Readiness minimo", 0, 100, 0, step=5, key="scanner_explorer_readiness")
        explorer_rows = filter_scanner_explorer_rows(
            table,
            bucket=bucket_filter,
            market=market_filter,
            strategy=strategy_filter,
            min_readiness=float(readiness_filter),
        )
        explorer_display = scanner_leaderboard_rows(explorer_rows, bucket="Todos", limit=25)
        if explorer_display.empty:
            st.info("No hay setups con esos filtros.")
        else:
            st.dataframe(explorer_display, use_container_width=True, hide_index=True, height=260)

    heatmap = scanner_heatmap_rows(table)
    top_rows = scanner_leaderboard_rows(table, bucket="Todos", limit=10)
    chart_cols = st.columns([1.15, 0.85])
    with chart_cols[0]:
        st.markdown("**Mapa de estrategias**")
        if heatmap.empty:
            st.info("Aun no hay setups para mapa de estrategias.")
        else:
            heatmap_chart = (
                alt.Chart(heatmap)
                .mark_square(opacity=0.88)
                .encode(
                    x=alt.X("bucket:N", title="", sort=["Operar", "Vigilar", "Evitar"]),
                    y=alt.Y("strategy:N", title="", sort="-x"),
                    color=alt.Color("tone:N", title="", scale=alt.Scale(domain=["buy", "watch", "avoid"], range=["#16a34a", "#d97706", "#dc2626"])),
                    size=alt.Size("count:Q", title="Setups", scale=alt.Scale(range=[80, 600])),
                    tooltip=[
                        "strategy:N",
                        "bucket:N",
                        alt.Tooltip("count:Q", format=",.0f"),
                        alt.Tooltip("avg_score:Q", title="Score avg", format=".0f"),
                        alt.Tooltip("avg_readiness:Q", title="Readiness avg", format=".0f"),
                    ],
                )
            )
            st.altair_chart(heatmap_chart.properties(height=260), use_container_width=True)
    with chart_cols[1]:
        st.markdown("**Ranking por IA**")
        if top_rows.empty:
            st.info("Sin ranking disponible.")
        else:
            score_chart = (
                alt.Chart(top_rows)
                .mark_bar(cornerRadius=4)
                .encode(
                    x=alt.X("score:Q", title="Score IA", scale=alt.Scale(domain=[0, 100])),
                    y=alt.Y("symbol:N", title="", sort="-x"),
                    color=alt.Color("status:N", title="", scale=alt.Scale(domain=["Operar", "Vigilar", "Evitar"], range=["#16a34a", "#d97706", "#dc2626"])),
                    tooltip=["symbol:N", "status:N", "strategy:N", alt.Tooltip("score:Q", format=".0f"), alt.Tooltip("readiness:Q", format=".0f")],
                )
            )
            st.altair_chart(score_chart.properties(height=260), use_container_width=True)

    table_cols = st.columns([1, 1])
    with table_cols[0]:
        st.markdown("**Mejores oportunidades**")
        top_display = scanner_leaderboard_rows(table, bucket="Todos", limit=12)
        if top_display.empty:
            st.info("Sin oportunidades priorizadas.")
        else:
            st.dataframe(top_display, use_container_width=True, hide_index=True, height=300)
    with table_cols[1]:
        st.markdown("**Falta confirmacion / bloqueadas**")
        watch_display = scanner_leaderboard_rows(table, bucket="Vigilar", limit=8)
        avoid_display = scanner_leaderboard_rows(table, bucket="Evitar", limit=4)
        blocked_display = pd.concat([watch_display, avoid_display], ignore_index=True).head(12)
        if blocked_display.empty:
            st.info("Sin setups bloqueados.")
        else:
            st.dataframe(blocked_display, use_container_width=True, hide_index=True, height=300)
    render_scanner_blotter(table, confluence_df)


def render_market_pulse_dashboard(table: pd.DataFrame) -> None:
    summary = market_pulse_summary(table)
    st.markdown("**Pulso del mercado**")
    cols = st.columns([0.75, 0.75, 0.75, 1.05, 1.1])
    with cols[0]:
        render_kpi_card("Operables", summary["ready"], tone="buy" if summary["ready"] else "neutral")
    with cols[1]:
        render_kpi_card("Vigilar", summary["watch"], tone="watch" if summary["watch"] else "neutral")
    with cols[2]:
        render_kpi_card("Evitar", summary["avoid"], tone="avoid" if summary["avoid"] else "neutral")
    with cols[3]:
        render_kpi_card("Readiness avg", num_display(summary["avg_readiness"], 0), tone="buy" if (summary["avg_readiness"] or 0) >= 70 else "watch")
    with cols[4]:
        render_kpi_card("Filtro dominante", summary["top_gate"], detail=f"Mercado: {summary['top_market']}")

    rows = market_pulse_rows(table)
    if rows.empty:
        st.info("Aun no hay oportunidades para dibujar el pulso.")
        return

    chart_cols = st.columns([1, 1, 1])
    with chart_cols[0]:
        bucket_df = rows.groupby(["bucket", "tone"], as_index=False).size().rename(columns={"size": "count"})
        bucket_chart = (
            alt.Chart(bucket_df)
            .mark_bar(cornerRadius=4)
            .encode(
                x=alt.X("count:Q", title="Setups"),
                y=alt.Y("bucket:N", title="", sort=["Operar", "Vigilar", "Evitar"]),
                color=alt.Color("tone:N", title="", scale=alt.Scale(domain=["buy", "watch", "avoid"], range=["#22c55e", "#f59e0b", "#ef4444"])),
                tooltip=["bucket:N", alt.Tooltip("count:Q", format=",.0f")],
            )
        )
        st.altair_chart(bucket_chart.properties(height=185), use_container_width=True)
    with chart_cols[1]:
        gate_df = rows[rows["gate"].ne("-")].groupby("gate", as_index=False).size().rename(columns={"size": "count"})
        if gate_df.empty:
            st.info("Sin filtros de alerta registrados.")
        else:
            gate_chart = (
                alt.Chart(gate_df.sort_values("count", ascending=False).head(8))
                .mark_bar(cornerRadius=4, color="#38bdf8")
                .encode(
                    x=alt.X("count:Q", title="Setups"),
                    y=alt.Y("gate:N", title="", sort="-x"),
                    tooltip=["gate:N", alt.Tooltip("count:Q", format=",.0f")],
                )
            )
            st.altair_chart(gate_chart.properties(height=185), use_container_width=True)
    with chart_cols[2]:
        risk_map = market_pulse_risk_map(table)
        if risk_map.empty:
            st.info("Sin riesgo/readiness suficiente.")
        else:
            risk_chart = (
                alt.Chart(risk_map)
                .mark_circle(size=130, opacity=0.82)
                .encode(
                    x=alt.X("risk_pct_display:Q", title="Riesgo %"),
                    y=alt.Y("readiness:Q", title="Readiness", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color("tone:N", title="", scale=alt.Scale(domain=["buy", "watch", "avoid"], range=["#22c55e", "#f59e0b", "#ef4444"])),
                    shape=alt.Shape("market:N", title="Mercado"),
                    tooltip=[
                        "symbol:N",
                        "bucket:N",
                        "market:N",
                        "gate:N",
                        alt.Tooltip("risk_pct_display:Q", title="Riesgo %", format=".2f"),
                        alt.Tooltip("readiness:Q", format=".0f"),
                    ],
                )
            )
            st.altair_chart(risk_chart.properties(height=185), use_container_width=True)


def focused_display_table(table: pd.DataFrame) -> pd.DataFrame:
    if table.empty:
        return table
    columns = [
        "action",
        "symbol",
        "signal",
        "decision",
        "ai_score",
        "entry",
        "stop",
        "risk_pct",
        "target_pct",
        "target_price",
        "gate",
        "readiness",
        "confidence",
        "por_que",
        "waiting_for",
        "cambia_si",
        "option",
        "option_score",
    ]
    return table[[col for col in columns if col in table.columns]].copy()


def focused_display_table_es(table: pd.DataFrame) -> pd.DataFrame:
    display = focused_display_table(table)
    if display.empty:
        return display
    formatted = display.copy()
    for column in ["entry", "stop", "target_price"]:
        if column in formatted.columns:
            formatted[column] = formatted[column].map(lambda value: num_display(value) if pd.notna(value) else "-")
    for column in ["risk_pct", "target_pct"]:
        if column in formatted.columns:
            formatted[column] = formatted[column].map(lambda value: pct_display(value) if pd.notna(value) else "-")
    if "readiness" in formatted.columns:
        formatted["readiness"] = formatted["readiness"].map(lambda value: num_display(value, 0) if pd.notna(value) else "-")
    rename = {
        "action": "accion",
        "symbol": "simbolo",
        "signal": "senal",
        "decision": "decision",
        "ai_score": "score_ia",
        "entry": "entrada",
        "stop": "stop",
        "risk_pct": "riesgo",
        "target_pct": "target",
        "target_price": "precio_target",
        "gate": "filtro",
        "readiness": "readiness",
        "confidence": "confianza",
        "por_que": "por_que",
        "waiting_for": "esperamos",
        "cambia_si": "cambia_si",
        "option": "opcion",
        "option_score": "score_opcion",
    }
    return formatted.rename(columns={key: value for key, value in rename.items() if key in formatted.columns})


def alert_preview_table(brief: dict) -> pd.DataFrame:
    rows = []
    for row in brief.get("opportunities", []):
        if str(row.get("ai_action") or "").upper() != "ALERT":
            continue
        entry = safe_float(row.get("entry"))
        target_2 = safe_float(row.get("target_2pct_price"))
        target_5 = safe_float(row.get("target_5pct_price"))
        target_10 = safe_float(row.get("target_10pct_price"))
        if entry is not None:
            target_2 = target_2 if target_2 is not None else entry * 1.02
            target_5 = target_5 if target_5 is not None else entry * 1.05
            target_10 = target_10 if target_10 is not None else entry * 1.10
        rows.append(
            {
                "market": row.get("market"),
                "symbol": row.get("symbol"),
                "accion": row.get("trade_decision"),
                "setup": row.get("strategy_family") or row.get("trigger_setup"),
                "entry": entry,
                "stop": safe_float(row.get("stop")),
                "target_2": target_2,
                "target_5": target_5,
                "target_10": target_10,
                "risk": safe_float(row.get("risk_pct")),
                "readiness": safe_float(row.get("alert_readiness_score")),
                "confianza": opportunity_confidence_label(row),
                "por_que": human_alert_reason(row) or opportunity_reason_label(row),
                "vigilar": watch_movement_label(row),
                "filtro": alert_gate_label(row.get("alert_gate")),
            }
        )
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.sort_values(["readiness", "symbol"], ascending=[False, True], na_position="last").reset_index(drop=True)


def _option_entry_price(option: dict) -> float | None:
    bid = safe_float(option.get("bid"))
    ask = safe_float(option.get("ask"))
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    for field in ("mark", "mid", "lastPrice", "last", "ask"):
        price = safe_float(option.get(field))
        if price is not None and price > 0:
            return price
    return None


def trade_plan_platform_preview(
    trade_brief: dict,
    *,
    account_equity: float,
    risk_per_trade_pct: float,
    preferred_crypto: str = "crypto_com",
    preferred_stock: str = "schwab",
    preferred_option: str = "schwab",
    source_freshness: dict | None = None,
    market_session: dict | None = None,
) -> dict:
    action = str(trade_brief.get("action") or "").upper()
    operation_status = str(trade_brief.get("operation_status") or "").lower()
    option = trade_brief.get("option") or {}
    preferred_product = "option" if action == "WATCH_CALL" else "crypto" if trade_brief.get("market") == "crypto" else "stock"
    ready_signal = operation_status == "operar"
    entry = trade_brief.get("entry")
    stop = trade_brief.get("stop")

    if preferred_product == "option" and option:
        option_entry = _option_entry_price(option)
        if option_entry is not None:
            entry = option_entry
            max_loss = safe_float(option.get("max_loss_per_contract"))
            option_stop = safe_float(option.get("stop") or option.get("option_stop"))
            if option_stop is None and max_loss is not None and max_loss > 0:
                option_stop = max(0.01, option_entry - (max_loss / 100.0))
            stop = option_stop

    row = {
        "market": trade_brief.get("market"),
        "symbol": trade_brief.get("symbol"),
        "contractSymbol": option.get("contractSymbol"),
        "option": option.get("contractSymbol"),
        "signal": "BUY" if ready_signal else trade_brief.get("signal") or "WATCH",
        "decision": trade_brief.get("trade_decision") if ready_signal else "WAIT",
        "trade_decision": trade_brief.get("trade_decision") if ready_signal else "WAIT",
        "entry": entry,
        "stop": stop,
        "target_pct": trade_brief.get("recommended_target_pct"),
        "target_price": trade_brief.get("recommended_target_price"),
        "strategy_family": trade_brief.get("strategy_family"),
    }
    ticket = build_platform_ticket(
        row,
        account_equity=account_equity,
        risk_per_trade_pct=risk_per_trade_pct,
        preferred_product=preferred_product,
        preferred_crypto=preferred_crypto,
        preferred_stock=preferred_stock,
        preferred_option=preferred_option,
        source_freshness=source_freshness,
        market_session=market_session,
    )
    ticket["trade_plan_decision"] = trade_brief.get("decision")
    ticket["manual_only"] = True
    ticket["platform_note"] = (
        "Preview only: Roxy prepara la orden y el tamano; la entrada real se confirma manualmente en la plataforma."
    )
    guardrail = build_account_risk_guardrail(
        account_equity,
        risk_per_trade_pct,
        planned_risk_dollars=ticket.get("risk_dollars"),
    )
    ticket["risk_guardrail"] = guardrail
    ticket["small_account_plan"] = small_account_product_plan(
        account_equity=account_equity,
        risk_per_trade_pct=risk_per_trade_pct,
        market=trade_brief.get("market"),
        entry=entry,
        stop=stop,
        option=option,
    )
    if ticket.get("status") == "READY_TO_PREVIEW" and not guardrail["allowed"]:
        ticket["status"] = "RISK_GUARDRAIL"
        ticket["status_reason"] = guardrail["message"]
        ticket["execution_enabled"] = False
    if preferred_product == "option":
        ticket["option_contract"] = option.get("contractSymbol")
        ticket["option_quality"] = {
            "dte": option.get("dte"),
            "delta": option.get("delta"),
            "spread_pct": option.get("spread_pct"),
            "volume": option.get("volume"),
            "openInterest": option.get("openInterest"),
            "breakeven_price": option.get("breakeven_price"),
            "max_loss_per_contract": option.get("max_loss_per_contract"),
        }
    return ticket


def opportunity_is_trade_ready(row: dict) -> bool:
    action = str(row.get("action") or row.get("ai_action") or "").upper()
    signal = str(row.get("signal") or "").upper()
    decision = str(row.get("decision") or row.get("trade_decision") or "").upper()
    return action == "ALERT" or (signal == "BUY" and decision.startswith("TRADE_FOR"))


def render_center_decision_board(row: dict) -> None:
    summary = center_decision_summary(row)
    st.markdown(
        f"""
        <div class="trade-plan trade-plan-{html.escape(summary['tone'])}">
            <div class="trade-plan-title">{html.escape(summary['status'])} | {html.escape(str(row.get('symbol') or '-'))}</div>
            <div class="trade-plan-line">{html.escape(summary['headline'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns([0.8, 1.4, 1.4, 1.4])
    with cols[0]:
        render_kpi_card("Accion Roxy", summary["action"], tone=summary["tone"])
    with cols[1]:
        render_kpi_card("Por que", summary["why"], tone=summary["tone"])
    with cols[2]:
        render_kpi_card("Esperamos", summary["wait_for"], tone="watch")
    with cols[3]:
        render_kpi_card("Cambia si", summary["changes_when"], tone="neutral")


def render_real_opportunity_panel(row: dict) -> None:
    symbol = str(row.get("symbol") or "-")
    market = str(row.get("market") or "-")
    signal = str(row.get("signal") or "-")
    decision = str(row.get("decision") or row.get("trade_decision") or "-")
    entry = safe_float(row.get("entry"))
    stop = safe_float(row.get("stop"))
    target_pct = safe_float(row.get("target_pct") or row.get("recommended_target_pct"))
    target_price = safe_float(row.get("target_price") or row.get("recommended_target_price"))
    if target_price is None and entry is not None and target_pct is not None:
        target_price = entry * (1.0 + target_pct)
    target_2 = entry * 1.02 if entry is not None else None
    target_5 = entry * 1.05 if entry is not None else None
    target_10 = entry * 1.10 if entry is not None else None
    tone = "buy" if signal == "BUY" else "watch" if signal == "WATCH" else "avoid"
    waiting_for = text_display(row.get("waiting_for"))
    confidence = text_display(row.get("confidence"))
    confidence_tone = "buy" if confidence.startswith("Alta") else "avoid" if confidence.startswith("Baja") else "watch"
    cols = st.columns([1.3, 0.9, 0.85, 0.85, 1.0, 1.35])
    with cols[0]:
        render_kpi_card("Enfoque", f"{market} {symbol}", tone=tone)
    with cols[1]:
        render_kpi_card("Senal", f"{signal} / {decision}", tone=tone, detail=waiting_for if waiting_for != "-" else None)
    with cols[2]:
        render_kpi_card("Entrada", num_display(entry))
    with cols[3]:
        render_kpi_card("Stop", num_display(stop))
    with cols[4]:
        render_kpi_card("Confianza", confidence, tone=confidence_tone)
    with cols[5]:
        render_kpi_card(
            "Objetivos",
            f"{num_display(target_2)} / {num_display(target_5)} / {num_display(target_10)}",
            detail=f"Recomendado {num_display(target_price)}",
        )


def render_focus_opportunity_chart(
    row: dict,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    app_brief: dict | None = None,
) -> None:
    symbol = str(row.get("symbol") or "").strip().upper()
    if not symbol or symbol == "-":
        return

    market_value = str(row.get("market") or "stock").strip().lower()
    market = "crypto" if market_value.startswith("crypto") or "/" in symbol else "stock"
    timeframe = "1h"
    resolved_symbol = resolve_symbol_query(symbol, market)

    with st.spinner(f"Construyendo grafica principal para {resolved_symbol}..."):
        try:
            history = fetch_symbol_history(resolved_symbol, market=market, timeframe=timeframe)
            chart_df = prepare_symbol_chart_data(history)
            setup = analyze_moving_average_setup(history) if not history.empty else {}
        except Exception as exc:
            st.warning(f"Grafica principal no disponible para {resolved_symbol}: {exc}")
            return

    if chart_df.empty or not setup:
        st.info(f"No hay historial de grafica disponible para {resolved_symbol}.")
        return

    confluence = latest_confluence_row(confluence_df, resolved_symbol)
    trade_brief = build_symbol_trade_brief(
        symbol=resolved_symbol,
        market=market,
        timeframe=timeframe,
        setup=setup,
        confluence=confluence,
        options_df=options_df,
        account_equity=float(DEFAULT_ACCOUNT_EQUITY),
        account_risk_pct=0.01,
        memory=load_memory(),
    )

    st.markdown("**Grafica principal**")
    render_chart_readout(setup, confluence, trade_brief, chart_df)
    render_chart_strategy_summary(setup, confluence, trade_brief, chart_df)
    render_operation_gate(trade_brief)
    render_focus_action_brief(trade_brief)
    if str(trade_brief.get("action") or "").upper() not in {"BUY_STOCK", "WATCH_CALL"}:
        render_watch_plan(trade_brief)
    render_chart_level_plan(chart_df, setup, confluence, trade_brief)
    platform_ticket = trade_plan_platform_preview(
        trade_brief,
        account_equity=float(DEFAULT_ACCOUNT_EQUITY),
        risk_per_trade_pct=0.01,
        source_freshness=(app_brief or {}).get("source_freshness"),
        market_session=(app_brief or {}).get("market_session"),
    )
    render_trade_plan_platform_preview(platform_ticket)
    price_chart = build_professional_price_chart(
        chart_df,
        setup,
        confluence,
        trade_brief,
        paper_snapshot=st.session_state.get("alpaca_paper_journal_snapshot"),
        symbol=resolved_symbol,
    ).properties(height=390)
    volume_chart = build_professional_volume_chart(chart_df)
    oscillator_chart = build_professional_oscillator_chart(chart_df)
    chart_panels = [price_chart]
    if volume_chart is not None:
        chart_panels.append(volume_chart.properties(height=105))
    if oscillator_chart is not None:
        chart_panels.append(oscillator_chart.properties(height=100))
    if len(chart_panels) > 1:
        combined_chart = alt.vconcat(*chart_panels).resolve_scale(x="shared")
        st.altair_chart(style_trading_chart(combined_chart), width="stretch")
    else:
        st.altair_chart(style_trading_chart(price_chart), width="stretch")

    with st.expander("Detalles de estrategia", expanded=False):
        render_decision_reason(trade_brief)
        render_decision_transition(trade_brief)
        render_strategy_event_panel(chart_df, setup)
        playbook = classify_strategy_playbook(setup, confluence=confluence, market=market, timeframe=timeframe)
        cols = st.columns(3)
        with cols[0]:
            render_kpi_card("Estrategia", playbook.get("regime", "-"))
        with cols[1]:
            render_kpi_card("Gatillo entrada", playbook.get("entry_rule", "-"))
        with cols[2]:
            render_kpi_card("Plan opciones", playbook.get("options_plan", "-"), tone="watch" if market == "stock" else "neutral")


def default_trade_plan_symbol(confluence_df: pd.DataFrame, brief: dict) -> str:
    table = focused_opportunity_table(brief)
    if not table.empty and table.iloc[0].get("symbol"):
        return str(table.iloc[0].get("symbol")).upper()
    if not confluence_df.empty and "symbol" in confluence_df.columns:
        scored = confluence_df.copy()
        if "confluence_score" in scored.columns:
            scored["confluence_score"] = pd.to_numeric(scored["confluence_score"], errors="coerce").fillna(0)
            scored = scored.sort_values("confluence_score", ascending=False)
        first = scored.iloc[0].get("symbol")
        if first:
            return str(first).upper()
    return "AAPL"


def show_trade_plan_screen(scan_df: pd.DataFrame, confluence_df: pd.DataFrame, options_df: pd.DataFrame, brief: dict) -> None:
    st.subheader("Plan de trade")
    default_symbol = default_trade_plan_symbol(confluence_df, brief)
    query_symbol = first_query_param_value(st.query_params, "symbol") or default_symbol
    query_symbol = str(query_symbol or default_symbol or "AAPL").strip().upper()
    query_market = normalize_command_market(first_query_param_value(st.query_params, "market"), query_symbol)
    query_timeframe = normalize_command_timeframe(first_query_param_value(st.query_params, "tf"))
    query_signature = (query_symbol, query_market, query_timeframe)
    if st.session_state.get("trade_plan_query_signature") != query_signature:
        st.session_state["command_symbol"] = query_symbol
        st.session_state["command_market"] = query_market
        st.session_state["command_timeframe"] = query_timeframe
        st.session_state["trade_plan_query_signature"] = query_signature
    else:
        st.session_state.setdefault("command_symbol", query_symbol)
        st.session_state.setdefault("command_market", query_market)
        st.session_state.setdefault("command_timeframe", query_timeframe)
    apply_pending_command_state()
    current_symbol = str(st.session_state.get("command_symbol", query_symbol) or query_symbol).strip().upper()
    current_market = normalize_command_market(st.session_state.get("command_market"), current_symbol)
    current_timeframe = normalize_command_timeframe(st.session_state.get("command_timeframe", "1h"))

    controls = st.columns([1.2, 0.75, 0.75, 0.8, 0.8])
    with controls[0]:
        symbol_choice = st.text_input(
            "Buscar activo",
            value=current_symbol,
            key="command_symbol",
            on_change=persist_command_symbol_query_params,
            help="Escribe acciones, ETFs o crypto. Ej: AAPL, TSLA, GOLD, BTC/USD, ETH/USD.",
        )
    with controls[1]:
        market = st.selectbox(
            "Mercado",
            ["stock", "crypto"],
            index=1 if current_market == "crypto" else 0,
            key="command_market",
            on_change=persist_command_query_params,
        )
    with controls[2]:
        timeframe = st.selectbox(
            "Marco",
            TIMEFRAME_OPTIONS,
            index=TIMEFRAME_OPTIONS.index(current_timeframe) if current_timeframe in TIMEFRAME_OPTIONS else 1,
            key="command_timeframe",
            on_change=persist_command_query_params,
        )
    with controls[3]:
        account_equity = st.number_input("Cuenta", min_value=100.0, value=float(DEFAULT_ACCOUNT_EQUITY), step=50.0, key="trade_plan_equity")
    with controls[4]:
        risk_per_trade_pct = st.number_input("Riesgo %", min_value=0.1, max_value=5.0, value=1.0, step=0.1, key="trade_plan_risk")

    symbol_choice = str(symbol_choice or current_symbol or default_symbol).strip().upper()
    if "/" in symbol_choice and market != "crypto":
        market = "crypto"
        st.session_state["command_market"] = market
    sync_dashboard_query_params(st.query_params, symbol=symbol_choice, market=market, timeframe=timeframe, page="Activo")
    render_selected_asset_banner(symbol_choice, market, timeframe)
    st.caption("La gráfica, niveles e indicadores se recalculan con este símbolo; no usa el foco global del scanner.")

    symbol = resolve_symbol_query(symbol_choice, market)
    with st.spinner(f"Construyendo plan para {symbol}..."):
        try:
            history = fetch_symbol_history(symbol, market=market, timeframe=timeframe)
            chart_df = prepare_symbol_chart_data(history)
            setup = analyze_moving_average_setup(history) if not history.empty else {}
        except Exception as exc:
            st.error(f"No se pudo construir el plan para {symbol}: {exc}")
            return

    if chart_df.empty or not setup:
        st.warning(f"No hay suficiente historial de precio para {symbol}.")
        return

    confluence = latest_confluence_row(confluence_df, symbol)
    trade_brief = build_symbol_trade_brief(
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        setup=setup,
        confluence=confluence,
        options_df=options_df,
        account_equity=float(account_equity),
        account_risk_pct=float(risk_per_trade_pct) / 100.0,
        memory=load_memory(),
    )
    platform_ticket = trade_plan_platform_preview(
        trade_brief,
        account_equity=float(account_equity),
        risk_per_trade_pct=float(risk_per_trade_pct) / 100.0,
        source_freshness=brief.get("source_freshness"),
        market_session=brief.get("market_session"),
    )

    render_ai_trade_brief(trade_brief)
    render_chart_strategy_summary(setup, confluence, trade_brief, chart_df)
    render_chart_level_plan(chart_df, setup, confluence, trade_brief)
    render_professional_chart_block(chart_df, setup, confluence, trade_brief, price_height=520, volume_height=135)
    render_operation_gate(trade_brief)
    with st.expander("Ruta manual, riesgo y plataforma", expanded=False):
        render_trade_plan_platform_preview(platform_ticket)

    playbook = classify_strategy_playbook(setup, confluence=confluence, market=market, timeframe=timeframe)
    with st.expander("Lectura completa y estudio del setup", expanded=False):
        render_chart_readout(setup, confluence, trade_brief, chart_df)
        render_strategy_event_panel(chart_df, setup)
        plan_cols = st.columns(3)
        with plan_cols[0]:
            render_kpi_card("Regimen", playbook["regime"])
        with plan_cols[1]:
            render_kpi_card("Regla entrada", playbook["entry_rule"])
        with plan_cols[2]:
            render_kpi_card("Opciones", playbook["options_plan"], tone="watch" if market == "stock" else "neutral")

        reference_rows = detect_reference_strategies(chart_df, setup)
        render_strategy_checklist(reference_rows)


def option_side_from_row(row: dict) -> str:
    explicit = str(row.get("option_type") or row.get("side") or row.get("type") or "").upper()
    if explicit in {"CALL", "PUT"}:
        return explicit
    contract = str(row.get("contractSymbol") or "")
    if len(contract) >= 9 and contract[-9] in {"C", "P"}:
        return "CALL" if contract[-9] == "C" else "PUT"
    return "CALL" if "C" in contract[-10:] else "PUT" if "P" in contract[-10:] else "-"


def prepare_options_view(options_df: pd.DataFrame) -> pd.DataFrame:
    if options_df.empty:
        return pd.DataFrame()
    data = options_df.copy()
    for column in [
        "option_score",
        "dte",
        "strike",
        "delta",
        "gamma",
        "theta",
        "vega",
        "bid",
        "ask",
        "spread_pct",
        "volume",
        "openInterest",
        "breakeven_price",
        "breakeven_pct",
        "max_loss_per_contract",
        "risk_reward_at_target",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["side"] = data.apply(lambda row: option_side_from_row(row.to_dict()), axis=1)
    if "option_decision" in data.columns:
        data["candidate_rank"] = data["option_decision"].astype(str).str.upper().eq("OPTION_CANDIDATE").astype(int)
    else:
        data["candidate_rank"] = 0
    if "volume" in data.columns and "openInterest" in data.columns:
        data["liquidity"] = data["volume"].fillna(0) + data["openInterest"].fillna(0)
    else:
        data["liquidity"] = 0
    if "spread_pct" in data.columns:
        data["spread_pct_display"] = data["spread_pct"] * 100.0
    if "breakeven_pct" in data.columns:
        data["breakeven_pct_display"] = data["breakeven_pct"] * 100.0
    data = annotate_option_greek_quality(data)
    sort_cols = [col for col in ["candidate_rank", "option_score", "spread_pct", "liquidity", "dte"] if col in data.columns]
    ascending = [False, False, True, False, True][: len(sort_cols)]
    if sort_cols:
        data = data.sort_values(sort_cols, ascending=ascending)
    return data.reset_index(drop=True)


def annotate_options_risk_budget(
    options_df: pd.DataFrame,
    *,
    account_equity: float = 500.0,
    risk_per_trade_pct: float = 0.01,
) -> pd.DataFrame:
    if options_df.empty:
        return options_df
    data = options_df.copy()
    risk_budget = max(1.0, float(account_equity or 500.0)) * max(0.001, float(risk_per_trade_pct or 0.01))
    if "max_loss_per_contract" in data.columns:
        data["max_loss_per_contract"] = pd.to_numeric(data["max_loss_per_contract"], errors="coerce")
        data["risk_budget"] = risk_budget
        data["risk_multiple"] = data["max_loss_per_contract"] / risk_budget
        data["fits_1r"] = data["max_loss_per_contract"].le(risk_budget)
        data["small_account_label"] = data["fits_1r"].map(
            {True: "Cabe en 1R", False: "Solo paper / reducir riesgo"}
        )
        data.loc[data["max_loss_per_contract"].isna(), "small_account_label"] = "Sin max loss"
    else:
        data["risk_budget"] = risk_budget
        data["risk_multiple"] = pd.NA
        data["fits_1r"] = False
        data["small_account_label"] = "Sin max loss"
    return data


def show_options_screen(confluence_df: pd.DataFrame, options_df: pd.DataFrame, brief: dict) -> None:
    st.subheader("Opciones: calls / puts")
    feed = professional_options_feed_status()
    feed_cols = st.columns(3)
    with feed_cols[0]:
        render_kpi_card("Fuente Greeks", feed["label"], tone=feed["tone"], detail=feed["source"])
    with feed_cols[1]:
        render_kpi_card("Datos requeridos", "Delta / DTE / Spread / OI", tone="watch")
    with feed_cols[2]:
        render_kpi_card("Uso permitido", "Manual / paper", tone="watch", detail=feed["note"])

    data = prepare_options_view(options_df)
    if data.empty:
        st.info("Todavia no hay candidatos de opciones. Roxy solo escanea contratos cuando la accion base tiene setup calificado.")
        empty_cols = st.columns(3)
        with empty_cols[0]:
            render_kpi_card("1R cuenta", num_display(float(DEFAULT_ACCOUNT_EQUITY) * 0.01), tone="watch")
        with empty_cols[1]:
            render_kpi_card("Regla opciones", "Solo paper", tone="avoid")
        with empty_cols[2]:
            render_kpi_card("Esperar", "Setup base BUY", tone="watch")
        st.caption("Con $500 y riesgo 1%, un contrato solo pasa si su max loss cabe cerca de $5. Si no cabe, Roxy debe priorizar accion/fraccionada o paper.")
        table = focused_opportunity_table(brief)
        if not table.empty:
            st.markdown("**Watchlist base esperando escaneo de opciones**")
            st.dataframe(table[["symbol", "signal", "decision", "entry", "stop", "target_pct"]], width="stretch", hide_index=True)
        return

    symbols = ["Todos"] + sorted(data["symbol"].dropna().astype(str).str.upper().unique().tolist()) if "symbol" in data.columns else ["Todos"]
    controls = st.columns([1, 1, 1, 1, 1])
    with controls[0]:
        selected_symbol = st.selectbox("Simbolo", symbols, key="options_symbol_filter")
    with controls[1]:
        selected_side = st.selectbox("Tipo", ["Todos", "CALL", "PUT"], key="options_side_filter")
    with controls[2]:
        min_score = st.slider("Score minimo", 0, 100, 0, key="options_min_score")
    with controls[3]:
        option_equity = st.number_input("Cuenta", min_value=100.0, value=float(DEFAULT_ACCOUNT_EQUITY), step=50.0, key="options_equity")
    with controls[4]:
        option_risk_pct = st.number_input("Riesgo %", min_value=0.1, max_value=5.0, value=1.0, step=0.1, key="options_risk_pct")

    view = data.copy()
    if selected_symbol != "Todos" and "symbol" in view.columns:
        view = view[view["symbol"].astype(str).str.upper().eq(selected_symbol)]
    if selected_side != "Todos":
        view = view[view["side"].eq(selected_side)]
    if "option_score" in view.columns:
        view = view[view["option_score"].fillna(0) >= min_score]
    view = annotate_options_risk_budget(
        view,
        account_equity=float(option_equity),
        risk_per_trade_pct=float(option_risk_pct) / 100.0,
    )
    view = annotate_professional_options_contracts(view)

    if view.empty:
        st.warning("Ningun contrato coincide con esos filtros.")
        return

    best = view.iloc[0].to_dict()
    best_cols = st.columns(8)
    with best_cols[0]:
        render_kpi_card("Mejor contrato", best.get("contractSymbol", "-"), tone="buy")
    with best_cols[1]:
        render_kpi_card("Tipo", best.get("side", "-"))
    with best_cols[2]:
        render_kpi_card("DTE", num_display(best.get("dte"), 0))
    with best_cols[3]:
        render_kpi_card("Delta", num_display(best.get("delta"), 2))
    with best_cols[4]:
        render_kpi_card("Spread", pct_display(best.get("spread_pct")))
    with best_cols[5]:
        render_kpi_card("Volumen", num_display(best.get("volume"), 0))
    with best_cols[6]:
        render_kpi_card("Open interest", num_display(best.get("openInterest"), 0))
    with best_cols[7]:
        render_kpi_card(
            "Riesgo max",
            num_display(best.get("max_loss_per_contract")),
            tone="buy" if bool(best.get("fits_1r")) else "avoid",
        )

    readiness_cols = st.columns([1, 1, 1.2, 1])
    with readiness_cols[0]:
        readiness = text_display(best.get("professional_readiness"))
        readiness_tone = "buy" if readiness == "Listo para revisar" else "avoid" if readiness == "Faltan Greeks" else "watch"
        render_kpi_card("Calidad contrato", readiness, tone=readiness_tone)
    with readiness_cols[1]:
        render_kpi_card("Fuente", text_display(best.get("data_source") or feed["source"]), tone=feed["tone"])
    with readiness_cols[2]:
        render_kpi_card("Bloqueos", text_display(best.get("professional_blockers")), tone=readiness_tone)
    with readiness_cols[3]:
        render_kpi_card("Prima / max loss", f"{num_display(best.get('ask'))} / {num_display(best.get('max_loss_per_contract'))}")

    risk_cols = st.columns(4)
    with risk_cols[0]:
        render_kpi_card("Break-even", num_display(best.get("breakeven_price")))
    with risk_cols[1]:
        render_kpi_card("Break-even %", pct_display(best.get("breakeven_pct")))
    with risk_cols[2]:
        render_kpi_card("Bid / Ask", f"{num_display(best.get('bid'))} / {num_display(best.get('ask'))}")
    with risk_cols[3]:
        render_kpi_card("Score opcion", num_display(best.get("option_score"), 0), tone="buy" if (safe_float(best.get("option_score")) or 0) >= 70 else "watch")

    greek_label, greek_tone, greek_note = greek_quality_label(best)
    greek_cols = st.columns(4)
    with greek_cols[0]:
        render_kpi_card("Greeks", greek_label, tone=greek_tone, detail=greek_note)
    with greek_cols[1]:
        render_kpi_card("Gamma", num_display(best.get("gamma"), 4))
    with greek_cols[2]:
        render_kpi_card("Theta", num_display(best.get("theta"), 4), tone="avoid" if safe_float(best.get("theta")) and safe_float(best.get("theta")) < 0 else "neutral")
    with greek_cols[3]:
        render_kpi_card("Vega", num_display(best.get("vega"), 4))

    account_cols = st.columns(4)
    with account_cols[0]:
        render_kpi_card("1R cuenta", num_display(best.get("risk_budget")), tone="watch")
    with account_cols[1]:
        fits = bool(best.get("fits_1r"))
        render_kpi_card("Cabe en 1R", "SI" if fits else "NO", tone="buy" if fits else "avoid")
    with account_cols[2]:
        render_kpi_card("Veces 1R", num_display(best.get("risk_multiple"), 2), tone="avoid" if (safe_float(best.get("risk_multiple")) or 0) > 1 else "buy")
    with account_cols[3]:
        render_kpi_card("Cuenta pequena", best.get("small_account_label", "-"), tone="buy" if fits else "avoid")

    chart_cols = st.columns([1, 1])
    with chart_cols[0]:
        if {"spread_pct_display", "option_score"}.issubset(view.columns):
            quality_chart = (
                alt.Chart(view)
                .mark_circle(size=120, opacity=0.82)
                .encode(
                    x=alt.X("spread_pct_display:Q", title="Spread %"),
                    y=alt.Y("option_score:Q", title="Score opcion", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color("side:N", title="Tipo", scale=alt.Scale(domain=["CALL", "PUT", "-"], range=["#22c55e", "#ef4444", "#94a3b8"])),
                    size=alt.Size("liquidity:Q", title="Liquidez", scale=alt.Scale(range=[60, 260])),
                    tooltip=[
                        "symbol:N",
                        "contractSymbol:N",
                        "side:N",
                        alt.Tooltip("dte:Q", format=".0f"),
                        alt.Tooltip("delta:Q", format=".2f"),
                        alt.Tooltip("spread_pct_display:Q", title="Spread %", format=".2f"),
                        alt.Tooltip("option_score:Q", format=".0f"),
                    ],
                )
            )
            st.altair_chart(quality_chart.properties(height=280), width="stretch")
    with chart_cols[1]:
        if {"contractSymbol", "volume", "openInterest"}.issubset(view.columns):
            liquidity = view.head(12)[["contractSymbol", "volume", "openInterest"]].melt(
                "contractSymbol", var_name="metric", value_name="value"
            )
            liq_chart = (
                alt.Chart(liquidity)
                .mark_bar()
                .encode(
                    x=alt.X("value:Q", title="Contratos"),
                    y=alt.Y("contractSymbol:N", title="Contrato", sort="-x"),
                    color=alt.Color("metric:N", title="Metrica", scale=alt.Scale(range=["#38bdf8", "#a78bfa"])),
                    tooltip=["contractSymbol:N", "metric:N", alt.Tooltip("value:Q", format=",.0f")],
                )
            )
            st.altair_chart(liq_chart.properties(height=280), width="stretch")

    option_cols = [
        "symbol",
        "side",
        "contractSymbol",
        "option_decision",
        "option_score",
        "expiry",
        "dte",
        "strike",
        "delta",
        "gamma",
        "theta",
        "vega",
        "greek_quality",
        "greek_note",
        "bid",
        "ask",
        "spread_pct_display",
        "spread_dollars",
        "volume",
        "openInterest",
        "breakeven_price",
        "breakeven_pct_display",
        "risk_reward_at_target",
        "max_loss_per_contract",
        "professional_readiness",
        "professional_blockers",
        "risk_budget",
        "risk_multiple",
        "small_account_label",
        "underlying_trade_decision",
        "underlying_confluence_score",
    ]
    st.dataframe(view[[col for col in option_cols if col in view.columns]], width="stretch", hide_index=True)

    if selected_symbol != "Todos" and not confluence_df.empty and "symbol" in confluence_df.columns:
        underlying = confluence_df[confluence_df["symbol"].astype(str).str.upper().eq(selected_symbol)]
        if not underlying.empty:
            st.markdown("**Setup de la accion base**")
            cols = [
                "symbol",
                "signal",
                "trade_decision",
                "confluence_score",
                "entry",
                "stop",
                "risk_pct",
                "recommended_target_pct",
                "recommended_target_price",
            ]
            st.dataframe(underlying[[col for col in cols if col in underlying.columns]], width="stretch", hide_index=True)


def render_backtest_strategy_visual(expanded: bool = True) -> None:
    trades_path, trades_df = latest_backtest_trades()
    summary = summarize_backtest_by_strategy(trades_df)
    if summary.empty:
        st.info("Todavia no hay trades de backtest por estrategia. Corre el flujo de backtest MA para llenar esta tabla.")
        return

    chart_data = summary.copy()
    for column in ["win_rate", "hit_2pct_rate", "hit_5pct_rate", "hit_10pct_rate", "stop_rate"]:
        chart_data[f"{column}_pct"] = chart_data[column] * 100.0
    finite_pf = chart_data["profit_factor"].replace([float("inf")], pd.NA).dropna()
    cap = float(finite_pf.max()) + 1.0 if not finite_pf.empty else 5.0
    chart_data["profit_factor_display"] = chart_data["profit_factor"].map(lambda value: cap if value == float("inf") else value)

    top = chart_data.iloc[0].to_dict()
    top_cols = st.columns(5)
    with top_cols[0]:
        render_kpi_card("Mejor estrategia", top.get("strategy_family", "-"), tone="buy")
    with top_cols[1]:
        render_kpi_card("Win rate", pct_display((safe_float(top.get("win_rate")) or 0)))
    with top_cols[2]:
        render_kpi_card("Profit factor", "inf" if top.get("profit_factor") == float("inf") else num_display(top.get("profit_factor")))
    with top_cols[3]:
        render_kpi_card("Llega 2%", pct_display((safe_float(top.get("hit_2pct_rate")) or 0)))
    with top_cols[4]:
        render_kpi_card("Toca stop", pct_display((safe_float(top.get("stop_rate")) or 0)), tone="avoid" if (safe_float(top.get("stop_rate")) or 0) > 0.45 else "neutral")

    cols = st.columns([1, 1])
    with cols[0]:
        win_chart = (
            alt.Chart(chart_data)
            .mark_bar()
            .encode(
                x=alt.X("win_rate_pct:Q", title="Win rate %"),
                y=alt.Y("strategy_family:N", title="Estrategia", sort="-x"),
                color=alt.Color("strategy_family:N", legend=None, scale=alt.Scale(range=["#22c55e", "#38bdf8", "#a78bfa", "#f59e0b", "#ef4444", "#94a3b8"])),
                tooltip=["strategy_family:N", alt.Tooltip("win_rate_pct:Q", format=".1f"), "trades:Q"],
            )
        )
        st.altair_chart(win_chart.properties(height=280), width="stretch")
    with cols[1]:
        pf_chart = (
            alt.Chart(chart_data)
            .mark_bar(color="#a78bfa")
            .encode(
                x=alt.X("profit_factor_display:Q", title="Profit factor"),
                y=alt.Y("strategy_family:N", title="Estrategia", sort="-x"),
                tooltip=["strategy_family:N", alt.Tooltip("profit_factor_display:Q", format=".2f"), "total_pnl:Q"],
            )
        )
        st.altair_chart(pf_chart.properties(height=280), width="stretch")

    target_view = chart_data[
        ["strategy_family", "hit_2pct_rate_pct", "hit_5pct_rate_pct", "hit_10pct_rate_pct", "stop_rate_pct"]
    ].melt("strategy_family", var_name="metric", value_name="rate")
    target_view["metric"] = target_view["metric"].map(
        {
            "hit_2pct_rate_pct": "Llega 2%",
            "hit_5pct_rate_pct": "Llega 5%",
            "hit_10pct_rate_pct": "Llega 10%",
            "stop_rate_pct": "Stop",
        }
    )
    target_chart = (
        alt.Chart(target_view)
        .mark_bar()
        .encode(
            x=alt.X("rate:Q", title="Rate %"),
            y=alt.Y("strategy_family:N", title="Estrategia", sort="-x"),
            color=alt.Color(
                "metric:N",
                title="Resultado",
                scale=alt.Scale(domain=["Llega 2%", "Llega 5%", "Llega 10%", "Stop"], range=["#22c55e", "#38bdf8", "#a78bfa", "#ef4444"]),
            ),
            tooltip=["strategy_family:N", "metric:N", alt.Tooltip("rate:Q", format=".1f")],
        )
    )
    st.altair_chart(target_chart.properties(height=330), width="stretch")

    display = summary.copy()
    for column in ["win_rate", "hit_2pct_rate", "hit_5pct_rate", "hit_10pct_rate", "stop_rate", "avg_return_pct"]:
        if column in display.columns:
            display[column] = display[column].map(lambda value: pct_display(value) if pd.notna(value) else "-")
    display["total_pnl"] = display["total_pnl"].map(lambda value: num_display(value))
    display["profit_factor"] = display["profit_factor"].map(lambda value: "inf" if value == float("inf") else num_display(value))
    st.caption(f"Fuente: `{trades_path}`")
    st.dataframe(display, width="stretch", hide_index=True)


def show_backtest_screen() -> None:
    st.subheader("Backtest por estrategia")
    render_backtest_strategy_visual()


def show_accuracy_screen(brief: dict) -> None:
    memory = brief.get("memory") or load_memory()
    report = build_accuracy_report(memory)
    headline = report["headline"]

    st.subheader("Precision / rendimiento")
    if headline.get("sample_status") == "READY":
        st.success("Roxy ya tiene suficientes senales medidas para comparar calidad por estrategia.")
    else:
        st.warning(
            "Roxy todavia esta juntando evidencia. Usala como asistente de decision, no como motor automatico."
        )

    kpis = st.columns(6)
    with kpis[0]:
        render_kpi_card("Alertas", headline.get("alerts", 0))
    with kpis[1]:
        sample = f"{headline.get('measured', 0)}/{headline.get('minimum_sample', 30)}"
        render_kpi_card("Medidas", sample, tone="buy" if headline.get("sample_status") == "READY" else "watch")
    with kpis[2]:
        render_kpi_card("Llega 2%", pct_display(headline.get("hit_2_rate")), tone="buy")
    with kpis[3]:
        render_kpi_card("Llega 5%", pct_display(headline.get("hit_5_rate")), tone="buy")
    with kpis[4]:
        render_kpi_card("Llega 10%", pct_display(headline.get("hit_10_rate")), tone="buy")
    with kpis[5]:
        stop_rate = safe_float(headline.get("stop_rate")) or 0.0
        render_kpi_card("Toca stop", pct_display(headline.get("stop_rate")), tone="avoid" if stop_rate >= 0.35 else "neutral")

    real_memory = report.get("real_memory") or real_signal_memory_summary(memory)
    st.markdown("**Memoria real de senales**")
    real_cols = st.columns(6)
    with real_cols[0]:
        render_kpi_card("Senales", real_memory.get("alerts", 0))
    with real_cols[1]:
        render_kpi_card("Medidas", real_memory.get("measured", 0), tone="buy" if real_memory.get("measured", 0) else "watch")
    with real_cols[2]:
        render_kpi_card("2%", pct_display(real_memory.get("hit_2_rate")), tone="buy")
    with real_cols[3]:
        render_kpi_card("5%", pct_display(real_memory.get("hit_5_rate")), tone="buy")
    with real_cols[4]:
        render_kpi_card("10%", pct_display(real_memory.get("hit_10_rate")), tone="buy")
    with real_cols[5]:
        render_kpi_card("Stop", pct_display(real_memory.get("stop_rate")), tone="avoid" if (safe_float(real_memory.get("stop_rate")) or 0) >= 0.35 else "neutral")
    st.caption(text_display(real_memory.get("lesson")))

    action_cols = st.columns([1.2, 1])
    with action_cols[0]:
        st.markdown("**Proximas acciones**")
        for item in report.get("next_actions", []):
            st.write(f"- {item}")
    with action_cols[1]:
        st.markdown("**Como leerlo**")
        st.caption(
            "La precision se basa en resultados guardados: 2%, 5%, 10% y stop. "
            "Un setup necesita senales repetidas antes de que Roxy suba su peso."
        )

    watch_progress = report.get("watch_progress") or {}
    st.markdown("**Progreso WATCH de laboratorio**")
    watch_cols = st.columns(5)
    with watch_cols[0]:
        render_kpi_card("WATCH trackeados", watch_progress.get("tracked", 0))
    with watch_cols[1]:
        render_kpi_card("Observados", watch_progress.get("observed", 0), tone="watch")
    with watch_cols[2]:
        near_target = safe_float(watch_progress.get("near_2pct_count")) or 0
        render_kpi_card("Cerca 2%", int(near_target), tone="buy" if near_target > 0 else "neutral")
    with watch_cols[3]:
        near_stop = safe_float(watch_progress.get("danger_stop_count")) or 0
        render_kpi_card("Cerca stop", int(near_stop), tone="avoid" if near_stop > 0 else "neutral")
    with watch_cols[4]:
        render_kpi_card("Promedio a 2%", pct_display(watch_progress.get("avg_progress_to_2pct")), tone="watch")
    st.caption(
        "Esto mide setups WATCH que aun no eran suficientemente limpios para alerta. "
        "Si muchos casi llegan al 2%, Roxy puede aflojar filtros; si van hacia stop, los endurece."
    )

    strategy_rows = report.get("strategy_rows") or []
    if strategy_rows:
        strategy_df = pd.DataFrame(strategy_rows)
        chart_df = strategy_df[strategy_df["alerts"] > 0].copy()
        if not chart_df.empty:
            rate_df = chart_df[
                ["strategy_family", "hit_2_rate", "hit_5_rate", "hit_10_rate", "stop_rate"]
            ].melt("strategy_family", var_name="metric", value_name="rate")
            rate_df["metric"] = rate_df["metric"].map(
                {
                    "hit_2_rate": "Llega 2%",
                    "hit_5_rate": "Llega 5%",
                    "hit_10_rate": "Llega 10%",
                    "stop_rate": "Stop",
                }
            )
            rate_df["rate_pct"] = rate_df["rate"].fillna(0) * 100
            rate_chart = (
                alt.Chart(rate_df)
                .mark_bar()
                .encode(
                    x=alt.X("rate_pct:Q", title="Rate %"),
                    y=alt.Y("strategy_family:N", title="Estrategia", sort="-x"),
                    color=alt.Color(
                        "metric:N",
                        title="Outcome",
                        scale=alt.Scale(
                            domain=["Llega 2%", "Llega 5%", "Llega 10%", "Stop"],
                            range=["#22c55e", "#38bdf8", "#a78bfa", "#ef4444"],
                        ),
                    ),
                    tooltip=["strategy_family:N", "metric:N", alt.Tooltip("rate_pct:Q", format=".1f")],
                )
            )
            st.altair_chart(rate_chart.properties(height=320), width="stretch")
        else:
            st.info("Aun no hay resultados de alertas por estrategia. La tabla muestra lo que Roxy esta midiendo.")

        display = strategy_df.copy()
        for col in ["hit_2_rate", "hit_5_rate", "hit_10_rate", "stop_rate"]:
            if col in display.columns:
                display[col] = display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
        cols = [
            "strategy_family",
            "status",
            "seen",
            "alerts",
            "measured",
            "hit_2pct",
            "hit_5pct",
            "hit_10pct",
            "stops",
            "hit_2_rate",
            "stop_rate",
            "sample_gap",
        ]
        with st.expander("Detalle: precision por estrategia", expanded=False):
            st.dataframe(display[[col for col in cols if col in display.columns]], width="stretch", hide_index=True)

    symbol_rows = report.get("symbol_rows") or []
    if symbol_rows:
        symbol_df = pd.DataFrame(symbol_rows)
        display = symbol_df.head(25).copy()
        for col in ["hit_2_rate", "stop_rate"]:
            if col in display.columns:
                display[col] = display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
        with st.expander("Detalle: memoria por simbolo", expanded=False):
            st.dataframe(display, width="stretch", hide_index=True)

    alert_rows = report.get("alert_rows") or []
    with st.expander("Detalle: registro de resultados", expanded=False):
        if alert_rows:
            alert_display = pd.DataFrame(alert_rows).head(50)
            for col in ["max_gain_pct", "max_drawdown_pct", "progress_to_2pct", "progress_to_stop"]:
                if col in alert_display.columns:
                    alert_display[col] = alert_display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
            st.dataframe(alert_display, width="stretch", hide_index=True)
        else:
            st.caption("Aun no hay resultados de alertas guardados. Cuando Roxy envie alertas limpias, aqui veras targets y stops.")

    journal_rows = report.get("signal_journal_rows") or []
    with st.expander("Detalle: diario WATCH del laboratorio", expanded=False):
        st.caption("Laboratorio de observacion para setups WATCH/AVOID fuertes. Ayuda a Roxy a aprender, pero no cuenta como precision real.")
        if journal_rows:
            journal_display = pd.DataFrame(journal_rows).head(50)
            for col in ["max_gain_pct", "max_drawdown_pct", "progress_to_2pct", "progress_to_stop"]:
                if col in journal_display.columns:
                    journal_display[col] = journal_display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
            st.dataframe(journal_display, width="stretch", hide_index=True)
        else:
            st.caption("Aun no hay senales WATCH guardadas.")


def render_smart_alert_gate(brief: dict) -> None:
    rows = []
    for row in brief.get("opportunities") or []:
        blockers = row.get("alert_blockers") or []
        if isinstance(blockers, str):
            blockers = [blockers]
        checks = (row.get("smart_alert") or {}).get("checks") or []
        rows.append(
            {
                "symbol": row.get("symbol"),
                "market": row.get("market"),
                "action": human_trade_action(row),
                "quality": row.get("alert_quality") or (row.get("smart_alert") or {}).get("quality"),
                "gate": alert_gate_label(row.get("alert_gate")),
                "readiness": row.get("alert_readiness_score"),
                "passed": f"{(row.get('smart_alert') or {}).get('passed_count', 0)}/{(row.get('smart_alert') or {}).get('total_checks', 0)}",
                "primary_blocker": row.get("alert_primary_blocker") or (row.get("smart_alert") or {}).get("primary_blocker"),
                "next_action": row.get("alert_next_action") or (row.get("smart_alert") or {}).get("next_action"),
                "reason": human_alert_reason(row),
                "missing": " | ".join(str(item) for item in blockers[:3]) if blockers else "Listo",
                "movement": row.get("alert_movement"),
                "signal": row.get("signal"),
                "decision": row.get("trade_decision"),
                "entry": row.get("entry"),
                "stop": row.get("stop"),
                "checks": " | ".join(
                    f"{check.get('rule')}: {'OK' if check.get('passed') else 'NO'}" for check in checks[:5]
                ),
            }
        )
    st.markdown("**Filtro inteligente de alertas**")
    if not rows:
        st.caption("No hay oportunidades ordenadas por IA en el brief actual.")
        return
    gate_df = pd.DataFrame(rows).sort_values(["action", "readiness"], ascending=[True, False])
    chart_df = gate_df.copy()
    chart_df["readiness"] = pd.to_numeric(chart_df["readiness"], errors="coerce").fillna(0)
    chart = (
        alt.Chart(chart_df.head(12))
        .mark_bar()
        .encode(
            x=alt.X("readiness:Q", title="Checklist %"),
            y=alt.Y("symbol:N", title="Simbolo", sort="-x"),
            color=alt.Color(
                "gate:N",
                title="Filtro",
                scale=alt.Scale(
                    range=["#22c55e", "#f59e0b", "#38bdf8", "#ef4444", "#a78bfa", "#94a3b8"],
                ),
            ),
            tooltip=[
                alt.Tooltip("symbol:N", title="Simbolo"),
                alt.Tooltip("quality:N", title="Calidad"),
                alt.Tooltip("gate:N", title="Filtro"),
                alt.Tooltip("passed:N", title="Pasa"),
                alt.Tooltip("primary_blocker:N", title="Bloqueo principal"),
                alt.Tooltip("next_action:N", title="Proximo paso"),
            ],
        )
    )
    st.altair_chart(chart.properties(height=280), width="stretch")
    display_cols = [
        "symbol",
        "action",
        "quality",
        "gate",
        "readiness",
        "passed",
        "primary_blocker",
        "next_action",
        "reason",
        "entry",
        "stop",
    ]
    gate_display = gate_df[[col for col in display_cols if col in gate_df.columns]].rename(
        columns={
            "symbol": "Simbolo",
            "action": "Accion",
            "quality": "Calidad",
            "gate": "Filtro",
            "readiness": "Checklist %",
            "passed": "Pasa",
            "primary_blocker": "Bloqueo principal",
            "next_action": "Proximo paso",
            "reason": "Razon",
            "entry": "Entrada",
            "stop": "Stop",
        }
    )
    st.dataframe(gate_display, width="stretch", hide_index=True)


def render_roxy_lab_visual(brief: dict, memory: dict) -> None:
    trades_path, trades_df = latest_backtest_trades()
    backtest_summary = summarize_backtest_by_strategy(trades_df)
    lab_rows = build_strategy_lab(memory, backtest_summary=backtest_summary)

    st.subheader("Roxy Lab")
    if not lab_rows:
        st.info("Roxy Lab is waiting for strategy memory or backtest results.")
        return

    lab_df = pd.DataFrame(lab_rows)
    state_labels = {
        "Promote": "Promover",
        "Watch": "Vigilar",
        "Collect data": "Recolectar datos",
        "Tighten filter": "Ajustar filtro",
    }
    state_counts = lab_df["lab_state"].value_counts()
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        render_kpi_card("Promover", int(state_counts.get("Promote", 0)), tone="buy")
    with kpi_cols[1]:
        render_kpi_card("Vigilar", int(state_counts.get("Watch", 0)), tone="watch")
    with kpi_cols[2]:
        render_kpi_card("Ajustar", int(state_counts.get("Tighten filter", 0)), tone="avoid")
    with kpi_cols[3]:
        render_kpi_card("Datos", int(state_counts.get("Collect data", 0)))

    shadow_observed = int(pd.to_numeric(lab_df.get("shadow_observed", 0), errors="coerce").fillna(0).sum())
    shadow_target_weighted = 0.0
    shadow_stop_weighted = 0.0
    if shadow_observed:
        shadow_target_weighted = (
            pd.to_numeric(lab_df.get("shadow_target_rate", 0), errors="coerce").fillna(0)
            * pd.to_numeric(lab_df.get("shadow_observed", 0), errors="coerce").fillna(0)
        ).sum() / shadow_observed
        shadow_stop_weighted = (
            pd.to_numeric(lab_df.get("shadow_stop_pressure", 0), errors="coerce").fillna(0)
            * pd.to_numeric(lab_df.get("shadow_observed", 0), errors="coerce").fillna(0)
        ).sum() / shadow_observed
    shadow_cols = st.columns(3)
    with shadow_cols[0]:
        render_kpi_card("WATCH medidos", shadow_observed, tone="watch")
    with shadow_cols[1]:
        render_kpi_card("WATCH cerca 2%", pct_display(shadow_target_weighted), tone="buy" if shadow_target_weighted >= 0.55 else "neutral")
    with shadow_cols[2]:
        render_kpi_card("WATCH hacia stop", pct_display(shadow_stop_weighted), tone="avoid" if shadow_stop_weighted >= 0.45 else "neutral")

    render_lab_daily_summary(lab_rows)

    chart_df = lab_df.copy()
    chart_df["evidence_score_pct"] = chart_df["evidence_score"] * 100.0
    chart_df["lab_state_label"] = chart_df["lab_state"].map(state_labels).fillna(chart_df["lab_state"])
    state_domain = ["Promote", "Watch", "Collect data", "Tighten filter"]
    state_label_domain = [state_labels[item] for item in state_domain]
    state_range = ["#22c55e", "#f59e0b", "#38bdf8", "#ef4444"]
    lab_chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("evidence_score_pct:Q", title="Evidencia %"),
            y=alt.Y("strategy_family:N", title="Estrategia", sort="-x"),
            color=alt.Color("lab_state_label:N", title="Estado lab", scale=alt.Scale(domain=state_label_domain, range=state_range)),
            tooltip=[
                alt.Tooltip("strategy_family:N", title="Estrategia"),
                alt.Tooltip("lab_state_label:N", title="Estado"),
                alt.Tooltip("evidence_score_pct:Q", title="Evidencia %", format=".1f"),
                alt.Tooltip("alerts:Q", title="Alertas"),
                alt.Tooltip("shadow_observed:Q", title="WATCH medidos"),
                alt.Tooltip("shadow_target_rate:Q", title="WATCH cerca 2%", format=".1%"),
                alt.Tooltip("shadow_stop_pressure:Q", title="WATCH hacia stop", format=".1%"),
                alt.Tooltip("backtest_trades:Q", title="Backtest trades"),
            ],
        )
    )
    st.altair_chart(lab_chart.properties(height=320), width="stretch")

    journal_df = load_learning_journal(limit=40)
    if not journal_df.empty:
        st.markdown("**Bitacora diaria de aprendizaje**")
        chart_rows = journal_df.copy()
        if "generated_at" in chart_rows.columns:
            chart_rows["generated_at"] = pd.to_datetime(chart_rows["generated_at"], errors="coerce")
        if "top_readiness" in chart_rows.columns and chart_rows["top_readiness"].notna().any():
            readiness_chart = (
                alt.Chart(chart_rows.dropna(subset=["generated_at", "top_readiness"]))
                .mark_line(point=True)
                .encode(
                    x=alt.X("generated_at:T", title="Tiempo"),
                    y=alt.Y("top_readiness:Q", title="Checklist %", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color("top_action:N", title="Accion"),
                    tooltip=[
                        alt.Tooltip("generated_at:T", title="Tiempo"),
                        alt.Tooltip("top_symbol:N", title="Simbolo"),
                        alt.Tooltip("top_action:N", title="Accion"),
                        alt.Tooltip("top_gate:N", title="Filtro"),
                        alt.Tooltip("top_quality:N", title="Calidad"),
                        alt.Tooltip("top_readiness:Q", title="Checklist %", format=".0f"),
                        alt.Tooltip("learning_bias:N", title="Memoria"),
                    ],
                )
            )
            st.altair_chart(readiness_chart.properties(height=180), width="stretch")

        display_cols = [
            "generated_at",
            "top_symbol",
            "top_market",
            "top_action",
            "top_strategy",
            "top_gate",
            "top_quality",
            "top_readiness",
            "top_next_action",
            "learning_bias",
            "learning_lesson",
            "next_experiment",
        ]
        journal_display = journal_df[[col for col in display_cols if col in journal_df.columns]].copy()
        if "top_action" in journal_display.columns:
            journal_display["top_action"] = journal_display["top_action"].map(action_label)
        if "top_readiness" in journal_display.columns:
            journal_display["top_readiness"] = journal_display["top_readiness"].map(
                lambda value: num_display(value, 0) if pd.notna(value) else "-"
            )
        if "generated_at" in journal_display.columns:
            journal_display["generated_at"] = journal_display["generated_at"].astype(str).str.replace("T", " ", regex=False).str.slice(0, 16)
        journal_display = journal_display.rename(
            columns={
                "generated_at": "Fecha",
                "top_symbol": "Simbolo",
                "top_market": "Mercado",
                "top_action": "Decision",
                "top_strategy": "Estrategia",
                "top_gate": "Filtro",
                "top_quality": "Calidad",
                "top_readiness": "Checklist",
                "top_next_action": "Que espera",
                "learning_bias": "Memoria",
                "learning_lesson": "Leccion",
                "next_experiment": "Siguiente experimento",
            }
        )
        st.dataframe(journal_display.tail(15), width="stretch", hide_index=True, height=320)

    learning_plan = brief.get("learning_plan") or autonomous_learning_plan(memory, backtest_summary=backtest_summary)
    if learning_plan:
        st.markdown("**Plan autonomo de aprendizaje**")
        plan_df = pd.DataFrame(learning_plan)
        display_cols = [
            "strategy_family",
            "action",
            "safety_mode",
            "evidence_score",
            "proposed_rule",
            "activation_rule",
            "why",
        ]
        plan_display = plan_df[[col for col in display_cols if col in plan_df.columns]].rename(
            columns={
                "strategy_family": "Estrategia",
                "action": "Accion",
                "safety_mode": "Modo",
                "evidence_score": "Evidencia",
                "proposed_rule": "Regla propuesta",
                "activation_rule": "Activacion",
                "why": "Por que",
            }
        )
        if "Accion" in plan_display.columns:
            plan_display["Accion"] = plan_display["Accion"].map(learning_action_label)
        if "Modo" in plan_display.columns:
            plan_display["Modo"] = plan_display["Modo"].map(safety_mode_label)
        st.dataframe(plan_display, width="stretch", hide_index=True)

    experiment_registry = brief.get("experiment_registry") or (memory.get("experiment_registry") if isinstance(memory, dict) else [])
    if experiment_registry:
        st.markdown("**Registro de experimentos Roxy**")
        experiments_df = pd.DataFrame(experiment_registry)
        measured_total = int(pd.to_numeric(experiments_df.get("measured_count", 0), errors="coerce").fillna(0).sum())
        hit_2_total = int(pd.to_numeric(experiments_df.get("hit_2_count", 0), errors="coerce").fillna(0).sum())
        stop_total = int(pd.to_numeric(experiments_df.get("stop_count", 0), errors="coerce").fillna(0).sum())
        exp_cols = st.columns(4)
        with exp_cols[0]:
            render_kpi_card("Experimentos", len(experiments_df), tone="watch")
        with exp_cols[1]:
            render_kpi_card("Senales medidas", measured_total, tone="buy" if measured_total >= 3 else "watch")
        with exp_cols[2]:
            render_kpi_card("Hit 2% lab", pct_display(hit_2_total / measured_total if measured_total else 0.0), tone="buy")
        with exp_cols[3]:
            render_kpi_card("Stop lab", pct_display(stop_total / measured_total if measured_total else 0.0), tone="avoid" if stop_total else "neutral")
        display_cols = [
            "strategy_family",
            "status",
            "outcome_state",
            "action",
            "safety_mode",
            "evidence_score",
            "measured_count",
            "hit_2_rate",
            "stop_rate",
            "seen_count",
            "proposed_rule",
            "activation_rule",
        ]
        for col in ["hit_2_rate", "stop_rate", "evidence_score"]:
            if col in experiments_df.columns:
                experiments_df[col] = experiments_df[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
        experiment_display = experiments_df[[col for col in display_cols if col in experiments_df.columns]].rename(
            columns={
                "strategy_family": "Estrategia",
                "status": "Estado",
                "outcome_state": "Resultado",
                "action": "Accion",
                "safety_mode": "Modo",
                "evidence_score": "Evidencia",
                "measured_count": "Medidas",
                "hit_2_rate": "Hit 2%",
                "stop_rate": "Stop",
                "seen_count": "Visto",
                "proposed_rule": "Regla propuesta",
                "activation_rule": "Activacion",
            }
        )
        if "Estado" in experiment_display.columns:
            experiment_display["Estado"] = experiment_display["Estado"].map(experiment_status_label)
        if "Accion" in experiment_display.columns:
            experiment_display["Accion"] = experiment_display["Accion"].map(learning_action_label)
        if "Modo" in experiment_display.columns:
            experiment_display["Modo"] = experiment_display["Modo"].map(safety_mode_label)
        st.dataframe(
            experiment_display,
            width="stretch",
            hide_index=True,
            height=260,
        )

    display_cols = [
        "strategy_family",
        "lab_state",
        "evidence_score",
        "memory_bias",
        "adaptive_weight",
        "alerts",
        "hit_2_rate",
        "hit_5_rate",
        "stop_rate",
        "shadow_observed",
        "shadow_target_rate",
        "shadow_stop_pressure",
        "backtest_trades",
        "backtest_win_rate",
        "backtest_profit_factor",
        "lab_decision",
        "experiment_rule",
    ]
    display = lab_df[[col for col in display_cols if col in lab_df.columns]].copy()
    for col in [
        "evidence_score",
        "hit_2_rate",
        "hit_5_rate",
        "stop_rate",
        "shadow_target_rate",
        "shadow_stop_pressure",
        "backtest_win_rate",
    ]:
        if col in display.columns:
            display[col] = display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
    if "adaptive_weight" in display.columns:
        display["adaptive_weight"] = display["adaptive_weight"].map(lambda value: f"{float(value):.2f}x")
    if "backtest_profit_factor" in display.columns:
        display["backtest_profit_factor"] = display["backtest_profit_factor"].map(
            lambda value: "inf" if value == float("inf") else num_display(value)
        )
    display = display.rename(
        columns={
            "strategy_family": "Estrategia",
            "lab_state": "Estado lab",
            "evidence_score": "Evidencia",
            "memory_bias": "Memoria",
            "adaptive_weight": "Peso",
            "alerts": "Alertas",
            "hit_2_rate": "Hit 2%",
            "hit_5_rate": "Hit 5%",
            "stop_rate": "Stop",
            "shadow_observed": "WATCH medidos",
            "shadow_target_rate": "WATCH cerca 2%",
            "shadow_stop_pressure": "WATCH hacia stop",
            "backtest_trades": "Backtest trades",
            "backtest_win_rate": "Win rate",
            "backtest_profit_factor": "Profit factor",
            "lab_decision": "Decision lab",
            "experiment_rule": "Regla experimento",
        }
    )
    if "Estado lab" in display.columns:
        display["Estado lab"] = display["Estado lab"].map(lambda value: state_labels.get(str(value), value))
    with st.expander("Detalle: panel de control de estrategias", expanded=False):
        st.dataframe(display, width="stretch", hide_index=True, height=360)

    promote_rows = [row for row in lab_rows if row.get("lab_state") == "Promote"]
    tighten_rows = [row for row in lab_rows if row.get("lab_state") == "Tighten filter"]
    next_rows = promote_rows[:2] + tighten_rows[:2]
    if next_rows:
        st.markdown("**Decisiones de Roxy**")
        cols = st.columns(min(3, len(next_rows)))
        for idx, row in enumerate(next_rows[:3]):
            tone = "buy" if row.get("lab_state") == "Promote" else "avoid"
            strategy_name = text_display(row.get("strategy_family"))
            row_key = f"{idx}_{safe_key(strategy_name)}"
            with cols[idx]:
                render_kpi_card(
                    strategy_name,
                    state_labels.get(str(row.get("lab_state")), row.get("lab_state")),
                    tone=tone,
                    detail=row.get("production_action"),
                )
                st.caption(str(row.get("experiment_rule") or ""))
                if st.button("Mini estudio", key=f"lab_inline_study_{row_key}", width="stretch"):
                    st.session_state["lab_inline_study_strategy"] = strategy_name
                if st.button("Cargar en Estudios", key=f"lab_load_study_{row_key}", width="stretch"):
                    st.session_state["study_strategy_request"] = strategy_name
                    st.session_state["study_focus_message"] = f"Roxy Lab cargo {strategy_name}. Abre la pestana Estudios para verlo completo."
                    st.success("Listo. Abre Estudios para ver el playbook completo con grafica.")

    inline_strategy = st.session_state.get("lab_inline_study_strategy")
    if inline_strategy:
        st.markdown("**Mini estudio conectado al laboratorio**")
        inline_row = next((row for row in lab_rows if row.get("strategy_family") == inline_strategy), {})
        render_strategy_study_preview(str(inline_strategy), inline_row)

    if trades_path:
        st.caption(f"Fuente backtest: `{trades_path}`")
    st.caption("Los cambios del laboratorio afectan ranking y alertas paper. Las ordenes reales siguen manuales hasta conectar un broker explicitamente.")



def render_dashboard_asset_panel(
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    brief: dict,
    best: pd.DataFrame,
    *,
    default_symbol: str,
    symbol_input: str,
    market: str,
    timeframe: str,
    account_equity: float,
    risk_pct: float,
) -> None:
    left, right = st.columns([1.6, 0.72])
    with left:
        symbol = str(symbol_input or default_symbol or "AAPL").strip().upper()
        if not symbol:
            symbol = "AAPL"
        with st.spinner(f"Leyendo {symbol} en {timeframe}..."):
            try:
                context = load_symbol_trade_context(
                    symbol=symbol,
                    market=market,
                    timeframe=timeframe,
                    confluence_df=confluence_df,
                    options_df=options_df,
                    account_equity=float(account_equity),
                    risk_per_trade_pct=float(risk_pct),
                    memory=load_memory(),
                )
            except Exception as exc:
                st.error(f"No se pudo construir el Command Center para {symbol}: {exc}")
                context = {}
        if context:
            render_command_center_analysis(
                context,
                app_brief=brief,
                account_equity=float(account_equity),
                risk_per_trade_pct=float(risk_pct),
            )
    with right:
        render_company_profile_card(symbol, market)
        st.subheader("Carga rapida")
        quick_rows = best.head(7).to_dict("records") if not best.empty else []
        if quick_rows:
            for idx, row in enumerate(quick_rows):
                label = (
                    f"{text_display(row.get('symbol')).upper()} | "
                    f"{human_trade_action(row)} | "
                    f"{strategy_family_for_row(row)}"
                )
                if st.button(label, key=f"command_load_{idx}_{safe_key(row.get('symbol'))}", width="stretch"):
                    st.session_state["command_symbol_pending"] = text_display(row.get("symbol")).upper()
                    st.session_state["command_market_pending"] = "crypto" if str(row.get("market") or "").lower().startswith("crypto") else "stock"
                    st.rerun()
        else:
            st.info("No hay oportunidades ordenadas. Puedes escribir un simbolo manualmente.")

        st.markdown("**Simbolos clave**")
        for symbol_label in ["AAPL", "NVDA", "AMD", "MSFT", "PLTR", "QQQ", "BTC/USD", "SOL/USD"]:
            if st.button(symbol_label, key=f"command_key_symbol_{safe_key(symbol_label)}", width="stretch"):
                st.session_state["command_symbol_pending"] = symbol_label
                st.session_state["command_market_pending"] = "crypto" if "/" in symbol_label else "stock"
                st.rerun()

        status = read_summary_json("alerts/roxy_status.json")
        if status:
            st.subheader("Estado Roxy")
            status_cols = st.columns(2)
            with status_cols[0]:
                alert_count = int(status.get("notifications_ready", 0) or 0)
                render_kpi_card("Alertas listas", alert_count, tone="buy" if alert_count else "neutral")
            with status_cols[1]:
                render_kpi_card("Datos", status.get("data_label", "-"), tone="buy" if status.get("data_label") == "Frescos" else "avoid")
            render_kpi_card(
                "Top watch",
                f"{status.get('top_market', '-')} {status.get('top_symbol', '-')}",
                tone="buy" if status.get("top_action") == "ALERT" else "watch",
                detail=f"{status.get('top_gate', '-')} | {status.get('top_quality', '-')}",
            )
            next_action = text_display(status.get("top_next_action"))
            if next_action != "-":
                st.caption(next_action)
            blockers = status.get("top_blockers") or []
            if blockers:
                st.caption("Bloquea: " + " | ".join(str(item) for item in blockers[:2]))
        st.subheader("Lectura IA")
        lessons = brief.get("lessons", [])[-6:]
        if lessons:
            for lesson in lessons:
                st.write(f"- {lesson}")
        else:
            st.write("La memoria IA se llenara despues del proximo escaneo live.")
        lines = build_notification_lines(brief)
        if lines:
            st.markdown("**Vista previa de alerta**")
            st.code("\n".join(lines))
        if not best.empty:
            with st.expander("Watchlist priorizada", expanded=False):
                watch_controls = st.columns([1, 1, 1])
                with watch_controls[0]:
                    watch_bucket = st.selectbox(
                        "Estado",
                        ["Todos", "Operar", "Vigilar", "Evitar"],
                        key="watchlist_bucket_filter",
                    )
                with watch_controls[1]:
                    markets = ["Todos"] + sorted(
                        market
                        for market in market_pulse_rows(best)["market"].dropna().astype(str).unique().tolist()
                        if market != "-"
                    )
                    watch_market = st.selectbox("Mercado", markets, key="watchlist_market_filter")
                with watch_controls[2]:
                    watch_min_readiness = st.slider("Readiness minimo", 0, 100, 0, step=5, key="watchlist_min_readiness")
                filtered_watchlist = filter_focused_opportunities(
                    best,
                    bucket=watch_bucket,
                    market=watch_market,
                    min_readiness=float(watch_min_readiness),
                )
                if filtered_watchlist.empty:
                    st.info("Ninguna oportunidad coincide con esos filtros.")
                else:
                    st.caption(f"Mostrando {min(len(filtered_watchlist), 15)} de {len(best)} oportunidades priorizadas.")
                    st.dataframe(focused_display_table_es(filtered_watchlist).head(15), width="stretch", height=320)

def show_focused_home(scan_df: pd.DataFrame, confluence_df: pd.DataFrame, options_df: pd.DataFrame, brief: dict) -> None:
    best = focused_opportunity_table(brief)
    default_symbol = default_trade_plan_symbol(confluence_df, brief)
    if "command_symbol" not in st.session_state:
        st.session_state["command_symbol"] = default_symbol
    apply_pending_command_state()

    st.subheader("Command Center")
    current_symbol = st.session_state.get("command_symbol", default_symbol)
    current_market = normalize_command_market(st.session_state.get("command_market"), current_symbol)
    current_timeframe = normalize_command_timeframe(st.session_state.get("command_timeframe"))
    current_equity = float(st.session_state.get("command_equity", 100.0) or 100.0)
    current_risk = float(st.session_state.get("command_risk", 1.0) or 1.0)
    st.markdown(
        f"""
        <section class="command-quick-strip">
          <b>{html.escape(text_display(current_symbol).upper())}</b>
          <span>{html.escape(current_market.upper())}</span>
          <span>{html.escape(current_timeframe)}</span>
          <span>Capital ${current_equity:,.0f}</span>
          <span>Riesgo {current_risk:.1f}%</span>
        </section>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Cambiar activo, mercado y capital", expanded=False):
        control_cols = st.columns([1.0, 0.7, 0.65, 0.65, 0.65, 0.65])
        with control_cols[0]:
            symbol_input = st.text_input(
                "Simbolo o crypto",
                value=current_symbol,
                key="command_symbol",
                on_change=persist_command_symbol_query_params,
            )
        with control_cols[1]:
            inferred_market = "crypto" if "/" in str(symbol_input) else "stock"
            market = st.selectbox(
                "Mercado",
                ["stock", "crypto"],
                index=1 if inferred_market == "crypto" else 0,
                key="command_market",
                on_change=persist_command_query_params,
            )
        with control_cols[2]:
            timeframe = st.selectbox("Marco", TIMEFRAME_OPTIONS, index=1, key="command_timeframe", on_change=persist_command_query_params)
        with control_cols[3]:
            account_equity = st.number_input(
                "Capital disponible",
                min_value=50.0,
                value=100.0,
                step=50.0,
                key="command_equity",
                help="Roxy calcula tamaño, riesgo y potencial según este capital; no usa un riesgo fijo.",
            )
        with control_cols[4]:
            risk_pct_ui = st.number_input("Riesgo %", min_value=0.1, max_value=5.0, value=1.0, step=0.1, key="command_risk")
        with control_cols[5]:
            clean_mode = st.toggle(
                "Modo limpio",
                value=True,
                key="command_clean_mode",
                help="Muestra primero oportunidades accionables y oculta paneles secundarios del Centro.",
            )

    with st.expander("Estado técnico del scan", expanded=False):
        render_alert_noise_contract(brief)

    sync_dashboard_query_params(
        st.query_params,
        symbol=symbol_input,
        market=market,
        timeframe=timeframe,
        page=st.session_state.get("roxy_focused_page", "Dashboard"),
    )
    top_symbol = selected_dashboard_symbol(best)
    render_selected_asset_banner(symbol_input, market, timeframe, top_symbol=top_symbol)
    render_dashboard_asset_panel(
        confluence_df,
        options_df,
        brief,
        best,
        default_symbol=default_symbol,
        symbol_input=symbol_input,
        market=market,
        timeframe=timeframe,
        account_equity=float(account_equity),
        risk_pct=float(risk_pct_ui) / 100.0,
    )
    render_broker_simulation_hub(best, account_equity=float(account_equity), risk_pct=float(risk_pct_ui) / 100.0)
    if clean_mode:
        render_top_opportunity_cards(best, confluence_df)
        render_trading_desk_table(best, confluence_df, scan_df)
        render_confirmation_radar(confluence_df)
        render_buy_readiness_gap_panel(confluence_df)
        render_exit_plan_board(best, confluence_df)
    else:
        render_ticker_intel_strip(best, confluence_df, symbol_input)
        render_company_research_hub(symbol_input, market)
        render_live_provider_center()
        render_alpaca_paper_execution_panel(best, account_equity=account_equity, risk_pct=risk_pct_ui / 100.0)
        paper_journal_snapshot = render_alpaca_paper_journal_panel()
        render_alpaca_paper_open_positions_panel(paper_journal_snapshot, best)
        render_alpaca_paper_strategy_ranking(paper_journal_snapshot, best)
        render_screener_preset_deck(best, confluence_df)
        render_exit_plan_board(best, confluence_df)
        render_executive_cockpit(best, confluence_df, scan_df, brief)
        render_top_opportunity_cards(best, confluence_df)
        render_market_movers_tape(best, confluence_df)
        render_opportunity_compare_board(best, confluence_df)
        render_opportunity_edge_heatmap(best, confluence_df)
        render_trading_desk_table(best, confluence_df, scan_df)
        render_confirmation_radar(confluence_df)
        render_buy_readiness_gap_panel(confluence_df)
        render_finviz_style_wallboard(best, confluence_df, brief)
        render_opportunity_matrix(best, confluence_df)
        render_confluence_validation_board(confluence_df)
        render_market_breadth_strip(scan_df, confluence_df)
        render_market_index_strip(scan_df, confluence_df)
        render_technical_movers_strip(scan_df)
        render_scanner_cockpit(best, confluence_df, options_df, brief)
        render_market_pulse_dashboard(best)



def show_focused_opportunities(confluence_df: pd.DataFrame, options_df: pd.DataFrame, brief: dict) -> None:
    table = focused_opportunity_table(brief)
    st.subheader("Solo lo importante")
    if table.empty:
        st.info("Todavia no hay oportunidades ordenadas por IA.")
    else:
        st.dataframe(focused_display_table_es(table), width="stretch", height=360)

    with st.expander("Confluencia tecnica completa"):
        if confluence_df.empty:
            st.write("No hay datos de confluencia.")
        else:
            cols = [
                "market",
                "symbol",
                "signal",
                "trade_decision",
                "confluence_score",
                "entry",
                "stop",
                "risk_pct",
                "recommended_target_pct",
                "recommended_target_price",
                "trigger_setup",
                "trend_setup",
                "backtest_eligible",
                "reasons",
            ]
            st.dataframe(confluence_df[[col for col in cols if col in confluence_df.columns]], width="stretch")

    with st.expander("Candidatos de opciones"):
        if options_df.empty:
            st.write("No hay candidatos de opciones.")
        else:
            cols = [
                "symbol",
                "contractSymbol",
                "option_decision",
                "option_score",
                "expiry",
                "dte",
                "strike",
                "delta",
                "bid",
                "ask",
                "spread_pct",
                "breakeven_price",
                "breakeven_pct",
                "max_loss_per_contract",
                "volume",
                "openInterest",
            ]
            st.dataframe(options_df[[col for col in cols if col in options_df.columns]], width="stretch")

    with st.expander("Backtest by strategy", expanded=True):
        render_backtest_strategy_visual()


def show_focused_ai_24h(brief: dict) -> None:
    memory = load_memory()
    render_roxy_lab_visual(brief, memory)
    st.divider()
    st.subheader("Alertas IA 24h")
    state = live_service_state()
    cols = st.columns(3)
    with cols[0]:
        render_kpi_card("LaunchAgent", state["loaded"], tone="buy" if state["loaded"] == "yes" else "watch")
    with cols[1]:
        render_kpi_card("Memory symbols", brief.get("memory_symbols", 0))
    with cols[2]:
        render_kpi_card("Modo", brief.get("mode", "AI_WATCH_24H"))

    render_smart_alert_gate(brief)

    with st.expander("Configuracion de notificaciones", expanded=False):
        st.code(
            "ALERT_EMAIL_TO=you@example.com\n"
            "SMTP_HOST=smtp.gmail.com\n"
            "SMTP_PORT=587\n"
            "SMTP_USERNAME=you@example.com\n"
            "SMTP_PASSWORD=app_password\n"
            "# alternativas opcionales\n"
            "DISCORD_WEBHOOK_URL=...\n"
            "SLACK_WEBHOOK_URL=...\n"
            "WEBHOOK_URL=...\n"
            "MACOS_NOTIFICATIONS=1\n"
            "ALERT_COOLDOWN_MINUTES=60"
        )
        st.caption("El escaner puede correr cada 5 minutos. Crypto es 24h; acciones usan 15m/1h/2h/4h y extended-hours cuando el proveedor lo permita.")

    st.markdown("**Centro de alertas**")
    gate_summary = brief.get("alert_gate_summary") or summarize_alert_gates(brief)
    delivery_summary = notifier.notification_history_summary(limit=50)
    gate_status = alert_gate_summary_dashboard_status(gate_summary)
    delivery_status = notification_history_dashboard_status(delivery_summary)
    quality_cols = st.columns(4)
    with quality_cols[0]:
        render_kpi_card("Compuerta", gate_status["label"], tone=gate_status["tone"], detail=gate_status["detail"])
    with quality_cols[1]:
        render_kpi_card(
            "Readiness prom.",
            num_display(gate_summary.get("avg_readiness"), 0) if gate_summary.get("avg_readiness") is not None else "-",
            tone=gate_status["tone"],
            detail=f"Listas {gate_summary.get('notifications_ready', 0)} / {gate_summary.get('total_opportunities', 0)}",
        )
    with quality_cols[2]:
        render_kpi_card("Delivery", delivery_status["label"], tone=delivery_status["tone"], detail=delivery_status["detail"])
    with quality_cols[3]:
        top_blocker = text_display(gate_summary.get("top_blocker"))
        render_kpi_card("Bloqueo top", gate_summary.get("top_gate_label", "-"), tone="watch", detail=top_blocker)

    status_df = notification_channel_display(notifier.notification_channel_status())
    if not status_df.empty:
        st.table(status_df)

    alert_cols = st.columns([1, 2])
    with alert_cols[0]:
        if st.button("Probar notificacion Mac", width="stretch"):
            result = notifier.send_test_macos_notification()
            if result.get("sent"):
                st.success("Notificacion Mac enviada.")
            else:
                st.warning("La notificacion Mac no se envio.")
    with alert_cols[1]:
        active_channels = notifier.configured_channels()
        active_labels = [NOTIFICATION_CHANNEL_LABELS.get(channel, channel) for channel in active_channels]
        st.metric("Canales activos", ", ".join(active_labels) if active_labels else "solo archivos locales")
        lines = build_notification_lines(brief)
        st.metric("Alertas listas", len(lines))
        st.caption(f"Cooldown: {notifier.ALERT_COOLDOWN_MINUTES} minutos por mercado/simbolo.")

    preview_df = alert_preview_table(brief)
    lines = build_notification_lines(brief)
    if not preview_df.empty:
        with st.expander("Vista previa de alerta actual", expanded=True):
            display_df = preview_df.copy()
            for col in ["entry", "stop", "target_2", "target_5", "target_10"]:
                if col in display_df.columns:
                    display_df[col] = display_df[col].map(lambda value: num_display(value) if pd.notna(value) else "-")
            if "risk" in display_df.columns:
                display_df["risk"] = display_df["risk"].map(lambda value: pct_display(value) if pd.notna(value) else "-")
            if "readiness" in display_df.columns:
                display_df["readiness"] = display_df["readiness"].map(lambda value: num_display(value, 0) if pd.notna(value) else "-")
            st.dataframe(display_df, width="stretch", hide_index=True)
            if lines:
                st.caption("Texto exacto que se enviaria por los canales activos:")
                st.text("\n".join(lines))
    else:
        st.caption("No hay alertas limpias ahora. Roxy seguira observando hasta que 1h, 15m, volumen, riesgo y target coincidan.")

    history = notifier.read_notification_history(limit=25)
    st.markdown("**Historial de notificaciones**")
    if history:
        history_df = notification_history_display_table(history)
        cols = ["ts", "effective_sent", "sent", "reason", "cooldown_skipped", "channels", "message"]
        st.dataframe(history_df[[col for col in cols if col in history_df.columns]], width="stretch", hide_index=True)
    else:
        st.caption("Todavia no hay historial de notificaciones.")

    brief_text = Path("alerts/roxy_ai_brief.txt")
    if brief_text.exists():
        st.markdown("**Ultimo brief IA**")
        st.text(brief_text.read_text())
    learning_profiles = brief.get("learning_profiles") or summarize_strategy_learning(memory)
    if learning_profiles:
        learning_df = pd.DataFrame(learning_profiles)
        display_cols = [
            "strategy_family",
            "bias",
            "adaptive_weight",
            "alerts",
            "hit_2_rate",
            "hit_5_rate",
            "hit_10_rate",
            "stop_rate",
            "lesson",
            "recommendation",
        ]
        learning_display = learning_df[[col for col in display_cols if col in learning_df.columns]].copy()
        for col in ["hit_2_rate", "hit_5_rate", "hit_10_rate", "stop_rate"]:
            if col in learning_display.columns:
                learning_display[col] = learning_display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
        if "adaptive_weight" in learning_display.columns:
            learning_display["adaptive_weight"] = learning_display["adaptive_weight"].map(lambda value: f"{float(value):.2f}x")
        st.markdown("**Aprendizaje Roxy**")
        st.dataframe(learning_display, width="stretch", hide_index=True)
        if st.button("Speak learning summary", key="speak_learning_summary"):
            voice_lines = []
            for profile in learning_profiles[:4]:
                lesson = str(profile.get("lesson") or "")
                recommendation = str(profile.get("recommendation") or "")
                if lesson:
                    voice_lines.append(lesson)
                if recommendation:
                    voice_lines.append(recommendation)
            speak_in_browser(" ".join(voice_lines), key="learning-summary")

    research_rows = brief.get("research_queue") or learning_research_queue(memory)
    if research_rows:
        st.markdown("**Lo proximo que Roxy debe probar**")
        st.dataframe(pd.DataFrame(research_rows), width="stretch", hide_index=True)

    gate_research = brief.get("gate_research") or []
    if gate_research:
        st.markdown("**Investigacion de filtros**")
        st.caption("Patrones de WATCH bloqueados. Esto le dice a Roxy que filtro debe mejorar.")
        st.dataframe(pd.DataFrame(gate_research), width="stretch", hide_index=True)

    strategy_stats = memory.get("strategy_stats") or {}
    if strategy_stats:
        rows = []
        for family, stats in strategy_stats.items():
            alerts = int(stats.get("alerts", 0) or 0)
            hit_2 = int(stats.get("hit_2pct", 0) or 0)
            stops = int(stats.get("stops", 0) or 0)
            rows.append(
                {
                    "strategy": family,
                    "seen": stats.get("seen", 0),
                    "alerts": alerts,
                    "hit_2pct": hit_2,
                    "hit_5pct": stats.get("hit_5pct", 0),
                    "hit_10pct": stats.get("hit_10pct", 0),
                    "stops": stops,
                    "hit_2_rate": hit_2 / alerts if alerts else None,
                    "stop_rate": stops / alerts if alerts else None,
                }
            )
        memory_df = pd.DataFrame(rows).sort_values(["hit_2_rate", "alerts"], ascending=[False, False])
        display = memory_df.copy()
        display["hit_2_rate"] = display["hit_2_rate"].map(lambda value: pct_display(value) if pd.notna(value) else "-")
        display["stop_rate"] = display["stop_rate"].map(lambda value: pct_display(value) if pd.notna(value) else "-")
        st.markdown("**Strategy memory**")
        st.dataframe(display, width="stretch", hide_index=True)
    with st.expander("Raw AI memory"):
        st.json(memory)


def show_strategy_study_center(
    scan_df: pd.DataFrame,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    brief: dict,
) -> None:
    st.subheader("Estudios")
    memory = load_memory()
    trades_path, trades_df = latest_backtest_trades()
    backtest_summary = summarize_backtest_by_strategy(trades_df)
    lab_rows = build_strategy_lab(memory, backtest_summary=backtest_summary)
    guides = study_guides_with_lab(lab_rows)
    if not guides:
        st.info("Roxy todavia no tiene guias de estudio cargadas.")
        return

    state_labels = {
        "Promote": "Promover",
        "Watch": "Vigilar",
        "Collect data": "Recolectar datos",
        "Tighten filter": "Ajustar filtro",
    }
    tone_by_state = {
        "Promote": "buy",
        "Watch": "watch",
        "Collect data": "neutral",
        "Tighten filter": "avoid",
    }
    strategy_names = [row["strategy"] for row in guides]
    preferred = next((row["strategy"] for row in guides if row.get("lab_state") == "Promote"), strategy_names[0])
    requested = st.session_state.pop("study_strategy_request", None)
    selected_default = resolve_study_strategy_choice(
        strategy_names,
        preferred,
        requested=requested,
        current=st.session_state.get("study_strategy_select"),
    )
    if selected_default in strategy_names:
        st.session_state["study_strategy_select"] = selected_default
    focus_message = st.session_state.pop("study_focus_message", None)
    if focus_message:
        st.success(str(focus_message))
    selected = st.selectbox(
        "Estrategia para estudiar",
        strategy_names,
        index=strategy_names.index(selected_default) if selected_default in strategy_names else 0,
        key="study_strategy_select",
    )
    guide = next(row for row in guides if row["strategy"] == selected)
    lab_state = str(guide.get("lab_state") or "Collect data")
    lab_tone = tone_by_state.get(lab_state, "neutral")

    st.markdown(
        f"""
        <div class="study-hero study-hero-{lab_tone}">
            <div>
                <div class="study-kicker">Playbook Roxy</div>
                <h2>{html.escape(selected)}</h2>
                <p>{html.escape(text_display(guide.get("headline")))}</p>
            </div>
            <div class="study-status">
                <span>Lab</span>
                <strong>{html.escape(state_labels.get(lab_state, lab_state))}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(4)
    with metric_cols[0]:
        render_kpi_card("Evidencia", pct_display(guide.get("evidence_score")), tone=lab_tone)
    with metric_cols[1]:
        render_kpi_card("Win rate", pct_display(guide.get("backtest_win_rate")), tone="buy")
    with metric_cols[2]:
        profit_factor = guide.get("backtest_profit_factor")
        render_kpi_card(
            "Profit factor",
            "inf" if profit_factor == float("inf") else num_display(profit_factor),
            tone="buy" if safe_float(profit_factor) and safe_float(profit_factor) >= 1.25 else "watch",
        )
    with metric_cols[3]:
        weight = safe_float(guide.get("adaptive_weight"))
        render_kpi_card("Peso IA", f"{weight:.2f}x" if weight is not None else "-", tone=lab_tone)

    study_tabs = st.tabs(["Manual", "Ejemplo con grafica", "Laboratorio"])
    with study_tabs[0]:
        cards = [
            ("Cuando funciona", guide.get("works_when"), "buy"),
            ("Requisitos", guide.get("requirements_text") or "-", "buy"),
            ("Entrada", guide.get("entry"), "watch"),
            ("No operar si", guide.get("avoid"), "avoid"),
            ("Opciones", guide.get("option_note"), "watch"),
            ("Practica", guide.get("practice"), "neutral"),
        ]
        for start in range(0, len(cards), 3):
            cols = st.columns(min(3, len(cards) - start))
            for col, (label, value, tone) in zip(cols, cards[start : start + 3]):
                with col:
                    st.markdown(
                        f"""
                        <div class="study-card study-card-{tone}">
                            <div class="study-card-label">{html.escape(label)}</div>
                            <div class="study-card-text">{html.escape(text_display(value))}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with study_tabs[1]:
        examples = study_example_rows(confluence_df, brief, selected)
        example_symbols = examples["symbol"].dropna().astype(str).str.upper().unique().tolist() if not examples.empty else []
        fallback_symbols = ["AAPL", "NVDA", "AMD", "MSFT", "PLTR", "QQQ"]
        symbols = sorted(dict.fromkeys(example_symbols + fallback_symbols))
        control_cols = st.columns([1, 0.8, 0.8])
        with control_cols[0]:
            symbol_choice = st.selectbox("Simbolo de ejemplo", symbols, key=f"study_symbol_{selected}")
        with control_cols[1]:
            default_market = "crypto" if "/" in symbol_choice else "stock"
            market = st.selectbox(
                "Mercado",
                ["stock", "crypto"],
                index=1 if default_market == "crypto" else 0,
                key=f"study_market_{selected}",
            )
        with control_cols[2]:
            timeframe = st.selectbox("Marco", TIMEFRAME_OPTIONS, index=1, key=f"study_tf_{selected}")

        resolved_symbol = resolve_symbol_query(symbol_choice, market)
        with st.spinner(f"Estudiando {resolved_symbol} en {timeframe}..."):
            try:
                history = fetch_symbol_history(resolved_symbol, market=market, timeframe=timeframe)
                chart_df = prepare_symbol_chart_data(history)
                setup = analyze_moving_average_setup(history) if not history.empty else {}
            except Exception as exc:
                st.warning(f"No se pudo cargar la grafica de estudio para {resolved_symbol}: {exc}")
                setup = {}
                chart_df = pd.DataFrame()

        if chart_df.empty or not setup:
            st.info("No hay suficiente historial para graficar este ejemplo ahora.")
        else:
            confluence = latest_confluence_row(confluence_df, resolved_symbol)
            trade_brief = build_symbol_trade_brief(
                symbol=resolved_symbol,
                market=market,
                timeframe=timeframe,
                setup=setup,
                confluence=confluence,
                options_df=options_df,
                account_equity=float(DEFAULT_ACCOUNT_EQUITY),
                account_risk_pct=0.01,
                memory=memory,
            )
            render_ai_trade_brief(trade_brief)
            render_chart_readout(setup, confluence, trade_brief, chart_df)
            render_chart_strategy_summary(setup, confluence, trade_brief, chart_df)
            render_strategy_event_panel(chart_df, setup)
            render_chart_level_plan(chart_df, setup, confluence, trade_brief)
            price_chart = build_professional_price_chart(
                chart_df,
                setup,
                confluence,
                trade_brief,
                paper_snapshot=st.session_state.get("alpaca_paper_journal_snapshot"),
                symbol=resolved_symbol,
            ).properties(height=440)
            volume_chart = build_professional_volume_chart(chart_df)
            oscillator_chart = build_professional_oscillator_chart(chart_df)
            chart_panels = [price_chart]
            if volume_chart is not None:
                chart_panels.append(volume_chart.properties(height=120))
            if oscillator_chart is not None:
                chart_panels.append(oscillator_chart.properties(height=110))
            if len(chart_panels) > 1:
                combined_chart = alt.vconcat(*chart_panels).resolve_scale(x="shared")
                st.altair_chart(style_trading_chart(combined_chart), width="stretch")
            else:
                st.altair_chart(style_trading_chart(price_chart), width="stretch")

        if not examples.empty:
            display_cols = [
                "symbol",
                "source",
                "signal",
                "trade_decision",
                "ai_action",
                "confluence_score",
                "entry",
                "stop",
                "risk_pct",
                "recommended_target_pct",
                "trigger_setup",
                "trend_setup",
            ]
            display = examples[[col for col in display_cols if col in examples.columns]].copy()
            for col in ["entry", "stop"]:
                if col in display.columns:
                    display[col] = display[col].map(lambda value: num_display(value) if pd.notna(value) else "-")
            for col in ["risk_pct", "recommended_target_pct"]:
                if col in display.columns:
                    display[col] = display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
            st.markdown("**Ejemplos detectados por Roxy**")
            st.dataframe(display.head(12), width="stretch", hide_index=True)

    with study_tabs[2]:
        lab_display = pd.DataFrame(guides)
        lab_display = lab_display[
            [
                "strategy",
                "lab_state",
                "evidence_score",
                "memory_bias",
                "adaptive_weight",
                "backtest_win_rate",
                "backtest_profit_factor",
                "lab_decision",
                "experiment_rule",
            ]
        ].copy()
        lab_display["lab_state"] = lab_display["lab_state"].map(lambda value: state_labels.get(str(value), value))
        for col in ["evidence_score", "backtest_win_rate"]:
            lab_display[col] = lab_display[col].map(lambda value: pct_display(value) if pd.notna(value) else "-")
        lab_display["adaptive_weight"] = lab_display["adaptive_weight"].map(
            lambda value: f"{float(value):.2f}x" if pd.notna(value) else "-"
        )
        lab_display["backtest_profit_factor"] = lab_display["backtest_profit_factor"].map(
            lambda value: "inf" if value == float("inf") else num_display(value)
        )
        lab_display = lab_display.rename(
            columns={
                "strategy": "Estrategia",
                "lab_state": "Estado lab",
                "evidence_score": "Evidencia",
                "memory_bias": "Memoria",
                "adaptive_weight": "Peso IA",
                "backtest_win_rate": "Win rate",
                "backtest_profit_factor": "Profit factor",
                "lab_decision": "Decision lab",
                "experiment_rule": "Regla experimento",
            }
        )
        st.dataframe(lab_display, width="stretch", hide_index=True, height=300)
        selected_rule = text_display(guide.get("experiment_rule"))
        selected_decision = text_display(guide.get("lab_decision"))
        if selected_rule != "-" or selected_decision != "-":
            st.markdown("**Lectura del laboratorio para esta estrategia**")
            if selected_decision != "-":
                st.info(selected_decision)
            if selected_rule != "-":
                st.caption(selected_rule)
        if trades_path:
            st.caption(f"Fuente backtest: `{trades_path}`")


def show_focused_voice(brief: dict) -> None:
    st.subheader("Roxy Voice Desk")
    st.caption("Respuesta operativa limpia: oportunidad actual, que falta y proximo paso. Los detalles tecnicos quedan ocultos.")
    try:
        from tools import voice_assistant as va
    except Exception as exc:
        st.error(f"Voice assistant unavailable: {exc}")
        return

    user = st.session_state.get("user")
    opportunity = (brief.get("opportunities") or [{}])[0] if brief.get("opportunities") else {}
    if opportunity:
        symbol = html.escape(text_display(opportunity.get("symbol") or opportunity.get("ticker") or "-"))
        decision = html.escape(text_display(opportunity.get("decision") or opportunity.get("action") or "Esperar"))
        setup = html.escape(text_display(opportunity.get("setup") or opportunity.get("strategy") or "-"))
        score = html.escape(text_display(opportunity.get("score") or opportunity.get("ai_score") or "-"))
        reason = html.escape(_summarize_voice_context(opportunity))
        st.markdown(
            f"""
            <div style="border:1px solid rgba(96,165,250,.34);border-radius:18px;padding:16px 18px;
                        background:linear-gradient(135deg,rgba(15,23,42,.94),rgba(30,41,59,.78));margin:10px 0 14px;">
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#93c5fd;font-weight:900;">Roxy esta mirando</div>
              <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-top:8px;">
                <div style="font-size:30px;font-weight:950;color:#f8fafc;line-height:1;">{symbol}</div>
                <div style="padding:5px 10px;border-radius:999px;background:rgba(251,191,36,.18);color:#fde68a;font-weight:900;">{decision}</div>
                <div style="padding:5px 10px;border-radius:999px;background:rgba(59,130,246,.16);color:#bfdbfe;font-weight:800;">{setup}</div>
                <div style="padding:5px 10px;border-radius:999px;background:rgba(16,185,129,.14);color:#bbf7d0;font-weight:800;">Score {score}</div>
              </div>
              <div style="margin-top:10px;color:#cbd5e1;font-size:13px;line-height:1.35;">{reason}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    quick_cols = st.columns(4)
    quick_prompts = [
        ("Ahora", "resumen de oportunidad"),
        ("Que falta", "que falta para operar la mejor oportunidad"),
        ("Salida", "como salgo a tiempo de la oportunidad actual"),
        ("Cuenta", "como esta mi cuenta"),
    ]
    for idx, (label, prompt) in enumerate(quick_prompts):
        with quick_cols[idx]:
            if st.button(label, key=f"voice_quick_{idx}", width="stretch"):
                reply = va.generate_reply(prompt, user=user)
                st.session_state["voice_last_reply"] = reply
                st.session_state["voice_last_query"] = prompt

    query = st.text_input(
        "Preguntar a Roxy",
        value=st.session_state.get("voice_last_query", ""),
        placeholder="Ejemplo: Roxy, explicame AAPL o que estas aprendiendo",
        key="focused_voice_query",
    )
    ask_cols = st.columns([1, 1, 2])
    with ask_cols[0]:
        if st.button("Preguntar", key="focused_voice_ask", width="stretch"):
            reply = va.generate_reply(query, user=user)
            st.session_state["voice_last_reply"] = reply
            st.session_state["voice_last_query"] = query
    with ask_cols[1]:
        auto_speak = st.toggle("Leer respuesta", value=True, key="focused_voice_auto_speak")

    reply = st.session_state.get("voice_last_reply")
    if reply:
        st.markdown("**Respuesta operativa de Roxy**")
        st.info(reply)
        if auto_speak:
            speak_in_browser(str(reply), key="voice-panel")
        elif st.button("Leer ultima respuesta", key="focused_voice_speak_last"):
            speak_in_browser(str(reply), key="voice-panel-manual")

    with st.expander("Captura de voz"):
        st.caption("Chrome puede transcribir tu voz aqui. Copia el texto a Preguntar a Roxy si Streamlit no lo llena automaticamente.")
        st.components.v1.html(
            """
            <div style="font-family: system-ui; color: #f8fafc;">
              <button id="roxy-start" style="padding:8px 12px;border-radius:8px;border:1px solid #64748b;background:#111827;color:#f8fafc;">Escuchar</button>
              <button id="roxy-stop" style="padding:8px 12px;border-radius:8px;border:1px solid #64748b;background:#111827;color:#f8fafc;">Parar</button>
              <div id="roxy-transcript" style="margin-top:10px;padding:10px;border:1px solid #334155;border-radius:8px;background:#0f172a;min-height:42px;">
                La transcripcion aparecera aqui.
              </div>
              <script>
                let recognition = null;
                const out = document.getElementById('roxy-transcript');
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (SpeechRecognition) {
                  recognition = new SpeechRecognition();
                  recognition.lang = 'es-US';
                  recognition.interimResults = false;
                  recognition.continuous = false;
                  recognition.onresult = (event) => {
                    out.innerText = event.results[0][0].transcript;
                    navigator.clipboard?.writeText(event.results[0][0].transcript).catch(() => {});
                  };
                  recognition.onerror = (event) => {
                    out.innerText = 'Error: ' + event.error;
                  };
                } else {
                  out.innerText = 'El reconocimiento de voz no esta disponible en este navegador.';
                }
                document.getElementById('roxy-start').onclick = () => { if (recognition) recognition.start(); };
                document.getElementById('roxy-stop').onclick = () => { if (recognition) recognition.stop(); };
              </script>
            </div>
            """,
            height=170,
        )

    if opportunity:
        with st.expander("Contexto completo que esta leyendo Roxy", expanded=False):
            st.write(_summarize_voice_context(opportunity))


def show_million_plan_screen() -> None:
    st.subheader("Plan de capital 500 a 1M")
    st.warning(
        "Esto es un marco de riesgo, no una promesa. Con $500, la primera meta es proteger capital y probar el setup."
    )

    controls = st.columns([1, 1, 1])
    with controls[0]:
        starting_capital = st.number_input("Capital inicial", min_value=100.0, max_value=100_000.0, value=500.0, step=50.0)
    with controls[1]:
        target_capital = st.number_input("Meta de capital", min_value=1_000.0, max_value=5_000_000.0, value=1_000_000.0, step=10_000.0)
    with controls[2]:
        risk_pct_ui = st.slider("Riesgo por trade %", min_value=0.25, max_value=2.00, value=1.00, step=0.25)

    plan = build_million_growth_plan(
        starting_capital=starting_capital,
        target_capital=target_capital,
        risk_per_trade_pct=risk_pct_ui / 100.0,
    )

    kpis = st.columns(5)
    with kpis[0]:
        render_kpi_card("Inicio", num_display(plan["starting_capital"]))
    with kpis[1]:
        render_kpi_card("Meta", num_display(plan["target_capital"], 0))
    with kpis[2]:
        render_kpi_card("Multiplicador", f"{num_display(plan['multiplier'], 0)}x", tone="watch")
    with kpis[3]:
        render_kpi_card("Riesgo/trade", num_display(plan["risk_per_trade"]), detail=f"{risk_pct_ui:.2f}%")
    with kpis[4]:
        render_kpi_card("Stop diario", num_display(plan["daily_stop"]), tone="avoid", detail="2R max")

    guardrail = plan.get("guardrail") or {}
    if guardrail:
        st.markdown("**Gobernador de riesgo**")
        guard_cols = st.columns(4)
        with guard_cols[0]:
            render_kpi_card("Estado", guardrail.get("status"), tone="buy" if guardrail.get("allowed") else "avoid")
        with guard_cols[1]:
            render_kpi_card("1R max", num_display(guardrail.get("per_trade_budget")))
        with guard_cols[2]:
            render_kpi_card("2R stop diario", num_display(guardrail.get("daily_stop")), tone="avoid")
        with guard_cols[3]:
            render_kpi_card("Riesgo libre", num_display(guardrail.get("remaining_daily_risk")))
        st.caption(str(guardrail.get("message") or ""))

    steps = pd.DataFrame(
        [
            {
                "movimiento_neto": move,
                "pasos_ganadores_netos": steps_needed,
                "semanas_a_3_pasos": int(math.ceil((steps_needed or 0) / 3)) if steps_needed else 0,
            }
            for move, steps_needed in plan["steps_to_target"].items()
        ]
    )
    st.markdown("**Chequeo realista de crecimiento compuesto**")
    st.dataframe(steps, width="stretch", hide_index=True)

    milestones = pd.DataFrame(plan["milestones"])
    if not milestones.empty:
        chart_df = milestones[["stage", "target"]].copy()
        chart_df["target_label"] = chart_df["target"].map(lambda value: f"${value:,.0f}")
        milestone_chart = (
            alt.Chart(chart_df)
            .mark_line(point=True, color="#38bdf8")
            .encode(
                x=alt.X("stage:O", title="Etapa"),
                y=alt.Y("target:Q", title="Meta de cuenta", scale=alt.Scale(type="log")),
                tooltip=["stage:O", "target_label:N"],
            )
        )
        st.altair_chart(style_trading_chart(milestone_chart.properties(height=280)), width="stretch")

        display = milestones.copy()
        for col in ["from", "target", "risk_per_trade", "daily_stop"]:
            display[col] = display[col].map(lambda value: num_display(value))
        display = display.rename(
            columns={
                "stage": "etapa",
                "phase": "fase",
                "from": "desde",
                "target": "meta",
                "risk_per_trade": "riesgo_trade",
                "daily_stop": "stop_diario",
                "trades_2pct": "trades_2pct",
                "trades_5pct": "trades_5pct",
                "trades_10pct": "trades_10pct",
                "products": "productos",
                "rule": "regla",
            }
        )
        st.markdown("**Escalera de metas**")
        st.dataframe(
            display[
                [
                    "etapa",
                    "fase",
                    "desde",
                    "meta",
                    "riesgo_trade",
                    "stop_diario",
                    "trades_2pct",
                    "trades_5pct",
                    "trades_10pct",
                    "productos",
                    "regla",
                ]
            ],
            width="stretch",
            hide_index=True,
            height=360,
        )

    st.markdown("**Reglas Roxy para una cuenta de $500**")
    rule_cols = st.columns(2)
    for idx, rule in enumerate(plan["rules"]):
        with rule_cols[idx % 2]:
            render_kpi_card("Regla", rule, tone="watch" if idx < 3 else "neutral")

    st.info(
        "Para opciones, Roxy debe comparar perdida maxima por contrato contra el presupuesto de riesgo. "
        f"Con {risk_pct_ui:.2f}% de riesgo, el primer presupuesto es {num_display(plan['max_option_debit'])}."
    )
    st.caption(
        "Las reglas del broker importan: cambios de margen intradia en EE. UU. empezaron el 4 de junio de 2026, "
        "pero los brokers pueden transicionar hasta el 20 de octubre de 2027. Confirma con tu broker antes de asumir margen o day-trading."
    )


def show_platform_router_screen(brief: dict) -> None:
    st.subheader("Plataformas")
    st.warning(
        "Roxy prepara tickets e instrucciones manuales solamente. El envio real al broker sigue apagado hasta tener credenciales, OAuth y confirmacion explicita."
    )
    st.info(
        "Uso actual: Roxy detecta oportunidad, calcula entrada/stop/tamano y te prepara la orden para copiarla manualmente en Crypto.com, Charles Schwab o Webull."
    )
    render_live_provider_center()

    platform_name = lambda platform_id: PLATFORM_PROFILES[platform_id]["name"]
    crypto_platforms = [pid for pid, profile in PLATFORM_PROFILES.items() if "crypto" in profile["assets"]]
    stock_platforms = [pid for pid, profile in PLATFORM_PROFILES.items() if "stock" in profile["assets"]]
    option_platforms = [pid for pid, profile in PLATFORM_PROFILES.items() if "option" in profile["assets"]]

    controls = st.columns([0.8, 0.8, 1.0, 1.0, 1.0])
    with controls[0]:
        account_equity = st.number_input("Capital", min_value=100.0, max_value=5_000_000.0, value=500.0, step=50.0, key="platform_equity")
    with controls[1]:
        risk_pct_ui = st.slider("Riesgo por trade %", min_value=0.25, max_value=2.00, value=1.00, step=0.25, key="platform_risk_pct")
    with controls[2]:
        preferred_crypto = st.selectbox(
            "Crypto",
            crypto_platforms,
            index=crypto_platforms.index("crypto_com") if "crypto_com" in crypto_platforms else 0,
            format_func=platform_name,
            key="platform_crypto",
        )
    with controls[3]:
        preferred_stock = st.selectbox(
            "Acciones",
            stock_platforms,
            index=stock_platforms.index("schwab") if "schwab" in stock_platforms else 0,
            format_func=platform_name,
            key="platform_stock",
        )
    with controls[4]:
        preferred_option = st.selectbox(
            "Opciones",
            option_platforms,
            index=option_platforms.index("schwab") if "schwab" in option_platforms else 0,
            format_func=platform_name,
            key="platform_option",
        )

    table = focused_opportunity_table(brief)
    opportunities = table.to_dict("records") if not table.empty else list(brief.get("opportunities") or [])
    if not opportunities:
        st.info("No hay oportunidades actuales. Corre el escaner y esta pantalla preparara tickets manuales.")
    else:
        route_rows = build_platform_route_rows(
            opportunities,
            account_equity=float(account_equity),
            risk_per_trade_pct=float(risk_pct_ui) / 100.0,
            preferred_crypto=preferred_crypto,
            preferred_stock=preferred_stock,
            preferred_option=preferred_option,
            source_freshness=brief.get("source_freshness"),
            market_session=brief.get("market_session"),
        )
        route_df = pd.DataFrame(route_rows)
        if not route_df.empty:
            route_df.insert(0, "route", range(1, len(route_df) + 1))
            display_routes = route_df.copy()
            if "asset_type" in display_routes.columns:
                display_routes["asset_type"] = display_routes["asset_type"].map(asset_type_label)
            if "status" in display_routes.columns:
                display_routes["status"] = display_routes["status"].map(platform_status_label)
            for column in ["entry", "stop", "target_price", "risk_dollars", "quantity"]:
                if column in display_routes.columns:
                    display_routes[column] = display_routes[column].map(lambda value: num_display(value, 4 if column == "quantity" else 2))
            summary_cols = st.columns(3)
            for idx, platform_id in enumerate([preferred_crypto, preferred_stock, preferred_option]):
                profile = PLATFORM_PROFILES.get(platform_id, {})
                status = platform_credential_status(platform_id)
                mode = connection_mode_label(status.get("mode", "NEEDS_CREDENTIALS"))
                with summary_cols[idx]:
                    render_kpi_card(
                        profile.get("name", platform_id),
                        mode,
                        tone="buy" if status.get("configured") else "watch",
                        detail=profile.get("best_for", ""),
                    )

            route_display_cols = [
                "route",
                "symbol",
                "asset_type",
                "platform",
                "status",
                "order_symbol",
                "entry",
                "stop",
                "target_price",
                "risk_dollars",
                "quantity",
            ]
            st.markdown("**Ruta por plataforma**")
            st.dataframe(
                display_routes[[col for col in route_display_cols if col in display_routes.columns]],
                width="stretch",
                hide_index=True,
                height=230,
            )

            labels = [
                f"{idx + 1}. {row.get('symbol')} -> {row.get('platform')} | {platform_status_label(row.get('status'))}"
                for idx, row in enumerate(route_rows)
            ]
            selected_label = st.selectbox("Ticket a preparar", labels, key="platform_ticket_choice")
            selected_index = labels.index(selected_label)
            selected_row = opportunities[selected_index]
            ticket = build_platform_ticket(
                selected_row,
                account_equity=float(account_equity),
                risk_per_trade_pct=float(risk_pct_ui) / 100.0,
                preferred_crypto=preferred_crypto,
                preferred_stock=preferred_stock,
                preferred_option=preferred_option,
                source_freshness=brief.get("source_freshness"),
                market_session=brief.get("market_session"),
            )

            status_tone_map = {
                "READY_TO_PREVIEW": "buy",
                "WAIT_FOR_CONFIRMATION": "watch",
                "NO_TRADE": "avoid",
                "BLOCKED_STALE_DATA": "avoid",
                "BLOCKED_MARKET_CLOSED": "avoid",
            }
            cols = st.columns([1.0, 1.0, 1.0, 0.9, 0.9, 0.9])
            with cols[0]:
                render_kpi_card("Plataforma", ticket["platform"])
            with cols[1]:
                render_kpi_card("Estado", platform_status_label(ticket["status"]), tone=status_tone_map.get(ticket["status"], "neutral"))
            with cols[2]:
                render_kpi_card("Orden", ticket["order_symbol"])
            with cols[3]:
                render_kpi_card("Entrada", num_display(ticket["entry"]))
            with cols[4]:
                render_kpi_card("Stop", num_display(ticket["stop"]))
            with cols[5]:
                render_kpi_card("Qty", num_display(ticket["quantity"], 4), detail=f"Riesgo {num_display(ticket['risk_dollars'])}")

            ticket_payload = {
                "platform": ticket["platform"],
                "asset_type": ticket["asset_type"],
                "symbol": ticket["symbol"],
                "order_symbol": ticket["order_symbol"],
                "side": ticket["side"],
                "order_type": ticket["order_type"],
                "time_in_force": ticket["time_in_force"],
                "entry": ticket["entry"],
                "stop": ticket["stop"],
                "target_price": ticket["target_price"],
                "risk_dollars": ticket["risk_dollars"],
                "quantity": ticket["quantity"],
                "status": platform_status_label(ticket["status"]),
                "execution_gate": platform_status_label(ticket["execution_gate"]),
            }
            order_preview = build_order_preview(ticket, connection_status=platform_credential_status(ticket["platform_id"]))
            st.markdown("**Ticket listo para copiar manualmente**")
            ticket_cols = st.columns([1.0, 1.0, 1.0, 0.8, 0.8])
            with ticket_cols[0]:
                render_kpi_card("Producto", asset_type_label(ticket["asset_type"]), detail=ticket["platform"])
            with ticket_cols[1]:
                render_kpi_card("Accion", platform_status_label(ticket["status"]), tone=status_tone_map.get(ticket["status"], "neutral"))
            with ticket_cols[2]:
                render_kpi_card("Orden", ticket["order_symbol"])
            with ticket_cols[3]:
                render_kpi_card("Riesgo $", num_display(ticket["risk_dollars"]), tone="watch")
            with ticket_cols[4]:
                render_kpi_card("Manual", "SI", tone="watch", detail="Envio real OFF")

            left, right = st.columns([1.1, 0.9])
            with left:
                with st.expander("Ticket JSON avanzado", expanded=False):
                    st.code(json.dumps(ticket_payload, indent=2), language="json")
            with right:
                with st.expander("Checklist antes de operar", expanded=True):
                    for item in ticket["checklist"]:
                        st.checkbox(item, value=False, key=f"platform_check_{selected_index}_{item[:20]}")
                    st.caption(platform_reason_label(ticket["status_reason"]))

            with st.expander(f"Pasos manuales para {ticket['platform']}", expanded=True):
                for step in ticket["manual_steps"]:
                    st.write(f"- {step}")

            st.markdown("**Seguridad de ejecucion**")
            readiness_cols = st.columns([0.9, 1.0, 1.0, 1.0, 1.4])
            with readiness_cols[0]:
                render_kpi_card("Readiness", f"{order_preview['readiness_score']}%")
            with readiness_cols[1]:
                render_kpi_card("Modo conexion", connection_mode_label(order_preview["mode"]), tone="buy" if order_preview["mode"] == "LIVE_ARMED" else "watch")
            with readiness_cols[2]:
                render_kpi_card(
                    "Payload preview",
                    "READY" if order_preview["preview_payload_ready"] else "BLOCKED",
                    tone="buy" if order_preview["preview_payload_ready"] else "avoid",
                )
            with readiness_cols[3]:
                render_kpi_card(
                    "Envio real",
                    "ON" if order_preview["live_send_ready"] else "OFF",
                    tone="buy" if order_preview["live_send_ready"] else "avoid",
                    detail=adapter_status_label(order_preview["adapter_status"]["status"]),
                )
            with readiness_cols[4]:
                render_kpi_card(
                    "Credenciales",
                    "ARMED" if order_preview["credential_gate_ready"] else "BLOCKED",
                    tone="buy" if order_preview["credential_gate_ready"] else "avoid",
                )
            missing = order_preview["credential_status"]["missing_keys"]
            if missing:
                st.caption("Faltan credenciales de conexion. No se muestran en la vista principal por seguridad.")
            with st.expander("Por que el envio real esta bloqueado", expanded=False):
                if order_preview["send_blockers"]:
                    for blocker in order_preview["send_blockers"]:
                        st.write(f"- {execution_blocker_label(blocker)}")
                else:
                    st.write("- Sin bloqueos adicionales.")
                st.caption(execution_blocker_label(order_preview["adapter_status"]["reason"]))
                st.caption(execution_blocker_label(order_preview["guardrail"]))
            with st.expander("Payload preview para futuro adaptador broker", expanded=False):
                st.code(json.dumps(order_preview["manual_order"], indent=2), language="json")

            schwab_preview = build_schwab_preview(ticket, order_preview=order_preview)
            if schwab_preview.get("applicable"):
                st.markdown("**Preview Schwab**")
                schwab_cols = st.columns([1.0, 1.0, 1.4])
                with schwab_cols[0]:
                    render_kpi_card(
                        "Schwab preview",
                        "READY" if schwab_preview["api_preview_ready"] else "BLOCKED",
                        tone="buy" if schwab_preview["api_preview_ready"] else "avoid",
                    )
                with schwab_cols[1]:
                    qty = (
                        schwab_preview["payload"].get("orderLegCollection", [{}])[0].get("quantity")
                        if schwab_preview.get("payload")
                        else "-"
                    )
                    render_kpi_card("Schwab qty", qty)
                with schwab_cols[2]:
                    render_kpi_card("Endpoint", "/previewOrder", detail="Plantilla POST; no enviada")
                with st.expander("Bloqueos y payload Schwab", expanded=False):
                    if schwab_preview["blockers"]:
                        st.markdown("**Bloqueos Schwab**")
                        for blocker in schwab_preview["blockers"]:
                            st.write(f"- {execution_blocker_label(blocker)}")
                    st.caption(execution_blocker_label(schwab_preview["guardrail"]))
                    st.code(json.dumps(schwab_preview["payload"], indent=2), language="json")
                    st.caption(schwab_preview["preview_endpoint"])

    with st.expander("Credenciales y configuracion avanzada", expanded=False):
        st.markdown("**Boveda segura de credenciales**")
        vault = encryption_status()
        if not vault["enabled"]:
            st.warning("La boveda encriptada no esta activa. Inicializa la llave local antes de guardar credenciales.")
            st.caption(f"Archivo local de llave: {vault['default_key_file']}")
            if st.button("Inicializar boveda local", key="init_local_vault"):
                try:
                    result = initialize_local_vault_key()
                    st.success(f"Llave lista: {result['path']} ({result['mode']}). El valor no se muestra.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"No se pudo inicializar la llave: {exc}")
            with st.expander("Opcion manual de llave", expanded=False):
                st.code("python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
                st.caption("Usa el valor como FERNET_KEY solo si prefieres configurarlo por variable de entorno.")
        else:
            st.success("Boveda encriptada activa. Los secretos no se imprimen en pantalla.")
            st.caption(f"Store: {vault['store']}")

        credential_platform = st.selectbox(
            "Plataforma de credenciales",
            list(PLATFORM_PROFILES.keys()),
            index=0,
            format_func=platform_name,
            key="credential_platform",
        )
        credential_status = platform_credential_status(credential_platform)
        st.dataframe(pd.DataFrame(credential_status["key_rows"]), width="stretch", hide_index=True)
        with st.expander(f"Guardar o rotar credenciales para {platform_name(credential_platform)}", expanded=False):
            entered_values = {}
            for key_name in credential_status["required_keys"]:
                entered_values[key_name] = st.text_input(
                    key_name,
                    value="",
                    type="password",
                    key=f"credential_input_{credential_platform}_{key_name}",
                    help="Roxy guarda esto encriptado cuando la boveda esta activa. El valor no se imprime en pantalla.",
                )
            if st.button("Guardar credenciales escritas", key=f"save_credentials_{credential_platform}"):
                values_to_save = {key: value for key, value in entered_values.items() if str(value or "").strip()}
                if not values_to_save:
                    st.info("No escribiste valores de credenciales.")
                else:
                    try:
                        saved = save_platform_credentials(credential_platform, values_to_save)
                        st.success(f"Guardadas/rotadas {len(saved)} credencial(es). Los valores no se muestran.")
                    except Exception as exc:
                        st.error(f"No se pudieron guardar credenciales: {exc}")

    st.markdown("**Estado de plataformas**")
    credential_lookup = {row["platform"]: row for row in credential_table_rows()}
    profile_rows = [
        {
            "platform": profile["name"],
            "assets": ", ".join(profile["assets"]),
            "mode": connection_mode_label(credential_lookup.get(profile["name"], {}).get("mode", "NEEDS_CREDENTIALS")),
            "missing": credential_lookup.get(profile["name"], {}).get("missing", "-"),
            "auth": profile["auth"],
            "api_status": profile["api_status"],
            "best_for": profile["best_for"],
        }
        for profile in PLATFORM_PROFILES.values()
    ]
    profile_df = pd.DataFrame(profile_rows)
    clean_profile_df = profile_df[["platform", "assets", "mode", "best_for"]].rename(
        columns={"platform": "Plataforma", "assets": "Opera", "mode": "Conexion", "best_for": "Mejor uso"}
    )
    st.dataframe(clean_profile_df, width="stretch", hide_index=True)
    with st.expander("Detalles tecnicos de plataformas", expanded=False):
        st.dataframe(profile_df, width="stretch", hide_index=True)
    st.caption("Plataformas configuradas: Crypto.com para crypto, Charles Schwab para acciones/opciones y Webull como ruta alterna.")
    st.info(
        "Siguiente paso seguro: credenciales encriptadas + OAuth + adaptador preview-only. El envio automatico debe requerir una segunda confirmacion."
    )


def _summarize_voice_context(row: dict) -> str:
    symbol = text_display(row.get("symbol"))
    family = text_display(row.get("strategy_family"))
    action = text_display(row.get("ai_action"))
    entry = num_display(row.get("entry"))
    stop = num_display(row.get("stop"))
    return f"{symbol} | {action} | {family} | Entry {entry} | Stop {stop}"




def selected_dashboard_symbol(table: pd.DataFrame) -> str:
    if not isinstance(table, pd.DataFrame) or table.empty:
        return ""
    try:
        return text_display(table.iloc[0].get("symbol")).upper()
    except Exception:
        return ""


def render_selected_asset_banner(symbol: str, market: str, timeframe: str, *, top_symbol: str = "") -> None:
    active_symbol = text_display(symbol).upper() or "AAPL"
    active_market = normalize_command_market(market, active_symbol).upper()
    active_timeframe = normalize_command_timeframe(timeframe)
    top_label = text_display(top_symbol).upper()
    scanner_scope = f"Scanner global: {top_label}" if top_label and top_label != active_symbol else "Scanner alineado"
    detail = "Grafica, indicadores y simulacion usan esta busqueda."
    if top_label and top_label != active_symbol:
        detail = "Tu grafica no cambia al top global; las oportunidades de abajo siguen siendo del scanner."
    st.markdown(
        f"""
        <section class="selected-asset-banner">
          <div class="selected-asset-main">
            <span>Activo seleccionado</span>
            <strong>{html.escape(active_symbol)} · {html.escape(active_market)} · {html.escape(active_timeframe)}</strong>
            <small>{html.escape(detail)}</small>
          </div>
          <div class="selected-asset-scope">
            <span>Contexto</span>
            <b>{html.escape(scanner_scope)}</b>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

def render_dashboard_action_queue(table: pd.DataFrame) -> None:
    if table.empty:
        return
    pulse = market_pulse_summary(table)
    readiness = num_display(pulse.get("avg_readiness"), 0)
    dominant_filter = text_display(pulse.get("top_gate"))
    header_status = (
        f"Operar {int(pulse.get('ready') or 0)} · "
        f"Vigilar {int(pulse.get('watch') or 0)} · "
        f"Evitar {int(pulse.get('avoid') or 0)} · "
        f"Readiness {readiness}"
    )
    if dominant_filter != "-":
        header_status += f" · Filtro {dominant_filter}"
    cards = []
    for rank, (_, item) in enumerate(table.head(3).iterrows(), start=1):
        row = item.to_dict()
        action = human_trade_action(row)
        tone = signal_tone(row.get("signal", ""))
        if str(action).lower().startswith("esperar"):
            tone = "watch"
        symbol = text_display(row.get("symbol")).upper()
        strategy = dashboard_strategy_label(row)
        market = text_display(row.get("market")).upper()
        timeframe = text_display(row.get("timeframe") or row.get("tf"))
        context_line = " · ".join(part for part in [strategy, market, timeframe] if part and part != "-")
        market_slug = "crypto" if market.lower().startswith("crypto") or "/" in symbol else "stock"
        tf_slug = timeframe if timeframe != "-" else "1h"
        asset_href = f"?view=Activo&symbol={quote(symbol, safe='')}&market={quote(market_slug, safe='')}&tf={quote(tf_slug, safe='')}"
        score = num_display(row.get("ai_score") or row.get("score"), 0)
        readiness = num_display(row.get("readiness"), 0)
        risk = pct_display(row.get("risk_pct"))
        next_step = text_display(row.get("waiting_for") or row.get("next") or row.get("gate") or "Confirmar estructura.")
        next_prefix = "Acción" if tone == "buy" else "Evitar" if tone == "avoid" else "Falta"
        entry_value = safe_float(row.get("entry") or row.get("current_price") or row.get("price"))
        stop_value = safe_float(row.get("stop"))
        target_value = safe_float(row.get("target") or row.get("take_profit") or row.get("target_price"))
        entry = price_display(entry_value)
        stop = price_display(stop_value)
        target = price_display(target_value)
        target = target if target != "-" else "pendiente"
        rr_value = None
        if entry_value is not None and stop_value is not None and target_value is not None and abs(entry_value - stop_value) > 0:
            rr_value = abs(target_value - entry_value) / abs(entry_value - stop_value)
        rr_text = f"1:{rr_value:.2f}" if rr_value is not None else "pendiente"
        rank_label = "prioridad" if rank == 1 else "seguimiento" if rank == 2 else "alternativa"
        cards.append(
            f'<article class="dashboard-action-card dashboard-action-{html.escape(tone)}">'
            f'<span>{html.escape(action)}</span>'
            f'<i class="dashboard-action-rank">#{rank} {html.escape(rank_label)}</i>'
            f'<a class="dashboard-action-symbol" href="{html.escape(asset_href)}">{html.escape(symbol)}</a>'
            f'<small>{html.escape(context_line)}</small>'
            f'<p><strong>{html.escape(next_prefix)}:</strong> {html.escape(next_step[:100])}</p>'
            f'<em>Score {html.escape(score)} · Ready {html.escape(readiness)} · Riesgo {html.escape(risk)}</em>'
            f'<b>Entrada {html.escape(entry)} · Stop {html.escape(stop)} · Target {html.escape(target)} · R:R {html.escape(rr_text)}</b>'
            f'<a class="dashboard-action-cta" href="{html.escape(asset_href)}">Ver gráfica interactiva →</a>'
            "</article>"
        )
    st.markdown(
        '<section class="dashboard-action-queue">'
        f"<header><strong>Próximas decisiones</strong><span>{html.escape(header_status)}</span></header>"
        f'<div>{"".join(cards)}</div>'
        "</section>",
        unsafe_allow_html=True,
    )


def render_roxy_now_strip(brief: dict[str, Any]) -> None:
    table = focused_opportunity_table(brief)
    best = table.iloc[0].to_dict() if not table.empty else {}
    symbol = text_display(best.get("symbol") if best else "-").upper()
    action = human_trade_action(best) if best else "Esperar"
    tone = signal_tone(best.get("signal", "")) if best else "watch"
    if str(action).lower().startswith("esperar"):
        tone = "watch"
    reason = dashboard_now_reason(best, brief)
    entry = num_display(best.get("entry") or best.get("current_price") or best.get("price"), 2)
    stop = num_display(best.get("stop"), 2)
    target = num_display(best.get("target") or best.get("take_profit"), 2)
    score = num_display(best.get("ai_score") or best.get("score"), 0)
    st.markdown(
        f"""
        <section class="roxy-now roxy-now-{html.escape(tone)}">
          <div class="roxy-now-main">
            <span>Qué hago ahora</span>
            <strong>{html.escape(action)}</strong>
            <p>{html.escape(reason[:210])}</p>
          </div>
          <div><span>Activo</span><strong>{html.escape(symbol)}</strong><p>Score {html.escape(score)}</p></div>
          <div><span>Niveles</span><strong>{html.escape(entry)} / {html.escape(stop)} / {html.escape(target)}</strong><p>Entrada · Stop · Target</p></div>
          <div><span>Regla</span><strong>Confirmar antes de operar</strong><p>Educativo; no garantiza ganancias.</p></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_dashboard_action_queue(table)

def show_focused_roxy_app() -> None:
    daily_path, daily_df = load_latest_ma_scan("ma_strategy")
    live_path, live_df = load_latest_ma_scan("ma_live_strategy")
    confluence_path, confluence_df = load_latest_ma_confluence()
    options_path, options_df = load_latest_options_candidates()
    scan_df = live_df if not live_df.empty else daily_df
    source_files = {"scan": live_path or daily_path, "confluence": confluence_path, "options": options_path}
    brief = read_summary_json("alerts/roxy_ai_brief.json")
    if not brief:
        memory_preview = json.loads(json.dumps(load_memory()))
        brief = build_brief(
            confluence_df=confluence_df,
            options_df=options_df,
            scan_df=scan_df,
            memory=memory_preview,
        )
    brief["source_files"] = source_files
    brief["source_freshness"] = source_freshness_status(source_files)
    brief["market_session"] = market_session_status()
    brief["realtime_health"] = realtime_health_status()
    brief = apply_global_alert_context(brief)

    render_roxy_brand_header(
        scan_df=scan_df,
        confluence_df=confluence_df,
        options_df=options_df,
        daily_path=daily_path,
        live_path=live_path,
        confluence_path=confluence_path,
        options_path=options_path,
        brief=brief,
    )
    show_focused_sidebar()
    realtime = configure_realtime_refresh()
    brief["realtime"] = realtime
    show_ai_status_cards(
        scan_df=scan_df,
        confluence_df=confluence_df,
        options_df=options_df,
        daily_path=daily_path,
        live_path=live_path,
        confluence_path=confluence_path,
        options_path=options_path,
        brief=brief,
    )
    show_focused_controls()
    render_roxy_now_strip(brief)
    with st.expander("Roxy IA / voz global", expanded=False):
        show_focused_voice(brief)

    page_tabs = st.tabs(["Dashboard", "Activo", "Capital", "Estudios", "Roxy IA"])
    with page_tabs[0]:
        show_focused_home(scan_df, confluence_df, options_df, brief)
    with page_tabs[1]:
        show_trade_plan_screen(scan_df, confluence_df, options_df, brief)
    with page_tabs[2]:
        show_million_plan_screen()
    with page_tabs[3]:
        show_strategy_study_center(scan_df, confluence_df, options_df, brief)
    with page_tabs[4]:
        show_focused_ai_24h(brief)


def main() -> None:
    st.set_page_config(page_title="Roxy AI Trading", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(
        """
        <style>
        :root{--roxy-bg:#0f1720;--card-bg:#0b1220;--muted:#9aa4b2;--accent:#38bdf8;--accent-2:#22c55e;--card-radius:8px}
        .stApp{background:#0b1020;color:#e5edf7}
        .block-container{padding-top:.75rem;padding-bottom:1.2rem;max-width:98vw}
        [data-testid="stSidebar"]{background:#0f172a;border-right:1px solid rgba(148,163,184,.16)}
        [data-testid="stHeader"]{background:rgba(14,22,36,.9)}
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], #MainMenu, footer{display:none!important}
        .chart-empty-state{display:flex;justify-content:space-between;gap:14px;align-items:center;border:1px dashed rgba(251,191,36,.46);border-left:4px solid #f59e0b;border-radius:8px;background:linear-gradient(135deg,rgba(120,74,15,.24),rgba(15,23,42,.92));padding:12px;margin:10px 0 8px}
        .chart-empty-state span{display:block;color:#fbbf24;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.07em}
        .chart-empty-state strong{display:block;color:#f8fafc;font-size:20px;line-height:1.08;margin-top:4px}
        .chart-empty-state p{margin:5px 0 0;color:#cbd5e1;font-size:12px;line-height:1.3}
        .chart-empty-state ul{margin:0;padding-left:18px;color:#e2e8f0;font-size:12px;line-height:1.35}
        .chart-fallback-state{border:1px solid rgba(56,189,248,.30);border-left:4px solid #38bdf8;border-radius:8px;background:linear-gradient(135deg,rgba(8,47,73,.34),rgba(15,23,42,.92));padding:10px 12px;margin:8px 0}
        .chart-fallback-state span{display:block;color:#7dd3fc;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.07em}
        .chart-fallback-state strong{display:block;color:#f8fafc;font-size:16px;line-height:1.1;margin-top:4px}
        .chart-fallback-state p{margin:5px 0 0;color:#cbd5e1;font-size:11px;line-height:1.3}
        .chart-command-head{display:flex;justify-content:space-between;gap:14px;align-items:center;border:1px solid rgba(96,165,250,.30);border-left:4px solid #38bdf8;border-radius:8px;background:linear-gradient(135deg,rgba(15,23,42,.95),rgba(8,47,73,.45));padding:10px 12px;margin:10px 0 6px}
        .chart-command-head span{display:block;color:#93c5fd;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.06em}
        .chart-command-head strong{display:block;color:#f8fafc;font-size:22px;line-height:1.05;margin-top:3px}
        .chart-next-action{display:block;color:#cbd5e1;font-size:11px;line-height:1.25;margin-top:5px;max-width:760px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .chart-command-head aside{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}
        .chart-command-head b{display:inline-flex;border:1px solid rgba(148,163,184,.24);border-radius:999px;background:#0b1220;color:#e2e8f0;padding:6px 9px;font-size:11px;line-height:1;font-weight:950}
        .chart-level-decision-buy{border-color:rgba(34,197,94,.70)!important;color:#dcfce7!important;background:rgba(22,101,52,.30)!important}
        .chart-level-decision-watch{border-color:rgba(245,158,11,.70)!important;color:#fef3c7!important;background:rgba(146,64,14,.28)!important}
        .chart-level-decision-avoid{border-color:rgba(248,113,113,.70)!important;color:#fee2e2!important;background:rgba(153,27,27,.30)!important}
        .chart-level-entry{border-color:rgba(56,189,248,.55)!important;color:#bae6fd!important;background:rgba(8,47,73,.20)!important}
        .chart-level-stop{border-color:rgba(248,113,113,.60)!important;color:#fecaca!important;background:rgba(127,29,29,.20)!important}
        .chart-level-target{border-color:rgba(34,197,94,.55)!important;color:#bbf7d0!important;background:rgba(20,83,45,.20)!important}
        .chart-level-rr{border-color:rgba(245,158,11,.58)!important;color:#fde68a!important;background:rgba(120,53,15,.18)!important}
        .chart-level-check-buy{border-color:rgba(34,197,94,.55)!important;color:#bbf7d0!important;background:rgba(20,83,45,.20)!important}
        .chart-level-check-watch{border-color:rgba(245,158,11,.58)!important;color:#fde68a!important;background:rgba(120,53,15,.18)!important}
        .chart-level-check-avoid{border-color:rgba(248,113,113,.60)!important;color:#fecaca!important;background:rgba(127,29,29,.20)!important}
        .chart-level-data{border-color:rgba(14,165,233,.46)!important;color:#bfdbfe!important;background:rgba(30,64,175,.15)!important}.chart-level-candle-buy{border-color:rgba(34,197,94,.56)!important;color:#bbf7d0!important;background:rgba(21,128,61,.18)!important}.chart-level-candle-avoid{border-color:rgba(239,68,68,.56)!important;color:#fecaca!important;background:rgba(127,29,29,.18)!important}
        .chart-level-interact{border-color:rgba(168,85,247,.50)!important;color:#ddd6fe!important;background:rgba(76,29,149,.18)!important}
        .chart-check-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;border:1px solid rgba(148,163,184,.18);border-radius:8px;background:rgba(148,163,184,.14);overflow:hidden;margin:-2px 0 6px}
        .chart-check-pill{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#0b1220;padding:6px 8px;min-width:0;border-top:2px solid rgba(148,163,184,.28)}
        .chart-check-pill span{min-width:0}
        .chart-check-pill em{font-style:normal;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .chart-check-pill small{display:block;color:#cbd5e1;font-size:9px;line-height:1.1;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .chart-check-pill strong{color:#f8fafc;font-size:11px;line-height:1;font-weight:950;white-space:nowrap}
        .chart-check-buy{border-top-color:#22c55e;background:rgba(21,93,62,.20)}
        .chart-check-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.18)}
        .chart-check-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.20)}
        .command-quick-strip{display:flex;gap:7px;align-items:center;flex-wrap:wrap;border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0d1426;padding:7px 8px;margin:0 0 6px}
        .command-quick-strip b{color:#f8fafc;font-size:16px;line-height:1}
        .command-quick-strip span{display:inline-flex;align-items:center;border:1px solid rgba(148,163,184,.18);border-radius:999px;background:#111827;color:#cbd5e1;padding:4px 8px;font-size:11px;font-weight:850;line-height:1}
        .roxy-now{display:grid;grid-template-columns:1.35fr .55fr .85fr .9fr;gap:1px;border:1px solid rgba(148,163,184,.24);border-radius:8px;background:rgba(148,163,184,.16);overflow:hidden;margin:8px 0 10px;box-shadow:0 14px 34px rgba(0,0,0,.20)}
        .roxy-now>div{background:#0b1220;padding:10px 12px;min-height:78px}
        .roxy-now span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.05em}
        .roxy-now strong{display:block;color:#f8fafc;font-size:18px;line-height:1.1;margin-top:5px;font-weight:950}
        .roxy-now p{margin:5px 0 0;color:#cbd5e1;font-size:12px;line-height:1.28}
        .roxy-now-main strong{font-size:24px}
        .roxy-now-buy{border-left:4px solid #22c55e}.roxy-now-buy .roxy-now-main{background:rgba(21,93,62,.24)}
        .roxy-now-watch{border-left:4px solid #f59e0b}.roxy-now-watch .roxy-now-main{background:rgba(120,74,15,.22)}
        .roxy-now-avoid{border-left:4px solid #ef4444}.roxy-now-avoid .roxy-now-main{background:rgba(127,29,29,.24)}

        .selected-asset-banner{display:flex;justify-content:space-between;gap:14px;align-items:center;border:1px solid rgba(34,211,238,.36);border-left:4px solid #22d3ee;border-radius:8px;background:linear-gradient(135deg,rgba(8,47,73,.72),rgba(15,23,42,.92));padding:9px 11px;margin:7px 0 8px;box-shadow:0 12px 28px rgba(8,47,73,.18)}
        .selected-asset-banner span{display:block;color:#67e8f9;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.08em;line-height:1}
        .selected-asset-banner strong{display:block;color:#f8fafc;font-size:16px;line-height:1.1;margin-top:4px}
        .selected-asset-banner small{display:block;color:#cbd5e1;font-size:11px;line-height:1.25;margin-top:4px}
        .selected-asset-scope{border:1px solid rgba(148,163,184,.20);border-radius:7px;background:rgba(15,23,42,.66);padding:7px 9px;text-align:right;min-width:180px}
        .selected-asset-scope b{display:block;color:#e2e8f0;font-size:12px;line-height:1.15;margin-top:4px}
        .dashboard-action-queue{border:1px solid rgba(148,163,184,.18);border-radius:8px;background:#0b1220;margin:-2px 0 8px;overflow:hidden}
        .dashboard-action-queue header{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:8px 10px;border-bottom:1px solid rgba(148,163,184,.14)}
        .dashboard-action-queue header strong{color:#f8fafc;font-size:14px;line-height:1}
        .dashboard-action-queue header span{color:#94a3b8;font-size:11px;text-align:right}
        .dashboard-action-queue>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .dashboard-action-card{background:#0f172a;padding:9px 10px;border-top:3px solid rgba(148,163,184,.36);min-width:0}
        .dashboard-action-card span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.06em}
        .dashboard-action-rank{display:inline-flex;margin-top:6px;padding:2px 6px;border-radius:999px;background:rgba(59,130,246,.16);border:1px solid rgba(147,197,253,.28);color:#bfdbfe;font-size:9px;font-style:normal;font-weight:950;text-transform:uppercase;letter-spacing:.05em}
        .dashboard-action-card strong,.dashboard-action-symbol{display:block;color:#f8fafc!important;font-size:22px;line-height:1;margin-top:3px;font-weight:950;text-decoration:none!important}
        .dashboard-action-symbol:hover{text-decoration:underline!important;text-underline-offset:3px}
        .dashboard-action-card small{display:block;color:#cbd5e1;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .dashboard-action-card p{margin:6px 0 0;color:#e2e8f0;font-size:11px;line-height:1.25;min-height:28px}
        .dashboard-action-card p strong{color:#f8fafc;font-weight:950}
        .dashboard-action-card em,.dashboard-action-card b{display:block;font-style:normal;color:#94a3b8;font-size:10px;line-height:1.2;margin-top:5px;font-weight:850}
        .dashboard-action-cta{display:inline-flex;margin-top:7px;color:#93c5fd!important;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.05em;text-decoration:none!important}
        .dashboard-action-cta:hover{color:#bfdbfe!important;text-decoration:underline!important;text-underline-offset:3px}
        .dashboard-action-buy{border-top-color:#22c55e;background:rgba(21,93,62,.18)}
        .dashboard-action-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.16)}
        .dashboard-action-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.18)}

        .broker-sim-hub{border:1px solid rgba(148,163,184,.18);border-radius:8px;background:#0b1220;margin:8px 0 10px;overflow:hidden}
        .broker-sim-hub>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(148,163,184,.14)}
        .broker-sim-hub>header strong{display:block;color:#f8fafc;font-size:15px;line-height:1}
        .broker-sim-hub>header span{display:block;color:#94a3b8;font-size:11px;margin-top:4px}
        .broker-sim-hub>header em{font-style:normal;color:#fecaca;background:rgba(127,29,29,.28);border:1px solid rgba(248,113,113,.40);border-radius:999px;padding:5px 8px;font-size:10px;font-weight:950;text-transform:uppercase;white-space:nowrap}
        .broker-sim-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .broker-sim-card{background:#0f172a;padding:9px 10px;border-top:3px solid rgba(148,163,184,.36);min-width:0}
        .broker-sim-card header{display:block;padding:0;border:0}
        .broker-sim-card strong{display:block;color:#f8fafc;font-size:13px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .broker-sim-card span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase;letter-spacing:.05em;margin-top:3px}
        .broker-sim-card p{margin:6px 0 0;color:#cbd5e1;font-size:10px;line-height:1.2;min-height:24px}
        .broker-sim-card b{display:block;color:#e2e8f0;font-size:10px;line-height:1.15;margin-top:5px}
        .broker-sim-card small{display:block;color:#94a3b8;font-size:9px;line-height:1.15;margin-top:4px}
        .broker-sim-buy{border-top-color:#22c55e;background:rgba(21,93,62,.17)}
        .broker-sim-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.14)}
        .broker-sim-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.18)}
        .broker-feature-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14);border-top:1px solid rgba(148,163,184,.14)}
        .broker-feature-grid>div{background:#0b1220;padding:8px 9px;min-width:0}
        .broker-feature-grid span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .broker-feature-grid strong{display:block;color:#f8fafc;font-size:14px;line-height:1;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .broker-feature-grid p{margin:5px 0 0;color:#cbd5e1;font-size:10px;line-height:1.18}
        @media (max-width:1200px){.broker-sim-grid,.broker-feature-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.roxy-now{grid-template-columns:1fr 1fr}}
        @media (max-width:760px){.broker-sim-hub>header{display:block}.broker-sim-hub>header em{display:inline-flex;margin-top:7px}.broker-sim-grid,.broker-feature-grid,.roxy-now{grid-template-columns:1fr}.broker-sim-card p{min-height:0}.broker-feature-grid p{min-height:0}}
        .roxy-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,520px);gap:18px;align-items:stretch;border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0d1426;padding:16px 18px;margin:0 0 10px;box-shadow:0 16px 42px rgba(0,0,0,.24)}
        .roxy-brand-row{display:flex;align-items:center;gap:14px}
        .roxy-logo-svg{width:58px;height:58px;flex:0 0 auto;filter:drop-shadow(0 10px 18px rgba(34,197,94,.15))}
        .brand-logo-img{width:178px;max-width:32vw;height:auto;display:block;border:1px solid rgba(212,175,96,.32);border-radius:8px;background:#030307;box-shadow:0 12px 30px rgba(0,0,0,.32)}
        .roxy-hero h1{font-size:34px;line-height:1.05;margin:0;color:#f8fafc;letter-spacing:0}
        .roxy-hero p{margin:6px 0 0;color:#b7c1d0;font-size:14px;line-height:1.35}
        .hero-flow{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
        .flow-step{display:flex;align-items:center;gap:7px;border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#111827;padding:8px 10px;color:#dbeafe;font-weight:750;font-size:12px;line-height:1.2}
        .flow-step span{display:inline-grid;place-items:center;width:19px;height:19px;border-radius:50%;background:#1f2937;color:#93c5fd;font-size:11px;font-weight:900}
        .roxy-hero-right{display:grid;grid-template-columns:1fr 1fr;gap:10px}
        .hero-chip{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#111827;padding:10px 12px;min-height:68px}
        .hero-chip span{display:block;color:#94a3b8;font-size:12px;font-weight:800;margin-bottom:6px}
        .hero-chip strong{display:block;color:#f8fafc;font-size:18px;line-height:1.18;overflow-wrap:anywhere}
        .hero-chip-buy{border-color:rgba(34,197,94,.42);box-shadow:inset 0 0 0 1px rgba(34,197,94,.12)}
        .hero-chip-watch{border-color:rgba(245,158,11,.42);box-shadow:inset 0 0 0 1px rgba(245,158,11,.10)}
        .hero-chip-avoid{border-color:rgba(239,68,68,.42);box-shadow:inset 0 0 0 1px rgba(239,68,68,.10)}
        .hero-subline{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:#9aa4b2;font-size:12px;margin:0 0 12px;padding:0 2px}
        .platform-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0 0 14px}
        .platform-badge{display:flex;align-items:center;gap:10px;border:1px solid rgba(148,163,184,.18);border-radius:8px;background:#0b1220;padding:10px 12px;min-height:70px}
        .platform-badge-buy{border-color:rgba(34,197,94,.32)}
        .platform-badge-watch{border-color:rgba(245,158,11,.26)}
        .platform-mark{display:grid;place-items:center;width:42px;height:42px;border:2px solid;border-radius:8px;font-size:13px;font-weight:900;background:#111827}
        .platform-name{font-size:14px;line-height:1.2;color:#f8fafc;font-weight:850}
        .platform-meta{font-size:12px;line-height:1.25;color:#a7b3c5;margin-top:4px}
        .scanner-tape{display:grid;grid-template-columns:1.1fr 1fr .9fr;gap:8px;align-items:center;border:1px solid rgba(148,163,184,.24);border-radius:8px;background:#111827;padding:8px 10px;margin:6px 0 10px}
        .scanner-tape div{display:flex;align-items:center;justify-content:space-between;gap:10px;border-right:1px solid rgba(148,163,184,.18);padding-right:10px;min-width:0}
        .scanner-tape div:last-child{border-right:0;padding-right:0}
        .scanner-tape strong{color:#f8fafc;font-size:12px;font-weight:950;text-transform:uppercase;white-space:nowrap}
        .scanner-tape span{color:#cbd5e1;font-size:12px;line-height:1.25;text-align:right;overflow-wrap:anywhere}
        .scanner-compass{display:grid;grid-template-columns:.55fr 1.45fr .8fr;gap:10px;align-items:center;border:1px solid rgba(148,163,184,.24);border-left-width:4px;border-radius:8px;background:#0b1220;padding:8px 10px;margin:-2px 0 10px}
        .scanner-compass strong{color:#f8fafc;font-size:17px;line-height:1;font-weight:950}
        .scanner-compass span{color:#e2e8f0;font-size:12px;line-height:1.25;font-weight:800}
        .scanner-compass em{color:#94a3b8;font-size:10px;line-height:1.25;font-style:normal;text-align:right}
        .scanner-compass-buy{border-left-color:#22c55e;background:rgba(21,93,62,.20)}.scanner-compass-watch{border-left-color:#f59e0b;background:rgba(120,74,15,.18)}.scanner-compass-avoid{border-left-color:#ef4444;background:rgba(127,29,29,.18)}
        .roxy-radar-head{display:flex;justify-content:space-between;gap:14px;align-items:center;border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#111827;padding:8px 10px;margin:6px 0 8px}.roxy-radar-head strong{display:block;color:#f8fafc;font-size:12px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.roxy-radar-head span{display:block;color:#94a3b8;font-size:11px;line-height:1.2;margin-top:2px}.roxy-radar-head aside{text-align:right}.roxy-radar-head b{display:block;color:#f8fafc;font-size:18px;line-height:1;font-weight:950}.roxy-radar-head small{display:block;color:#cbd5e1;font-size:11px;line-height:1.2;margin-top:4px}
        .roxy-radar-guide{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;border:1px solid rgba(148,163,184,.18);border-radius:8px;background:rgba(148,163,184,.14);overflow:hidden;margin:-2px 0 8px}.roxy-radar-guide div{padding:7px 9px;background:#0b1220;border-top:2px solid rgba(148,163,184,.30)}.roxy-radar-guide strong{display:block;color:#f8fafc;font-size:11px;line-height:1;font-weight:950}.roxy-radar-guide span{display:block;color:#cbd5e1;font-size:10px;line-height:1.15;margin-top:4px}.radar-guide-buy{border-top-color:#22c55e!important;background:rgba(21,93,62,.20)!important}.radar-guide-watch{border-top-color:#f59e0b!important;background:rgba(120,74,15,.18)!important}.radar-guide-avoid{border-top-color:#ef4444!important;background:rgba(127,29,29,.18)!important}
        .scanner-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 10px}
        .scanner-card{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#0b1220;padding:10px 12px;min-height:90px;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
        .scanner-card span{display:block;color:#94a3b8;font-size:11px;line-height:1.2;font-weight:900;text-transform:uppercase}
        .scanner-card strong{display:block;color:#f8fafc;font-size:28px;line-height:1;margin:8px 0 7px;letter-spacing:0}
        .scanner-card small{display:block;color:#cbd5e1;font-size:12px;line-height:1.25}
        .scanner-card-buy{border-color:rgba(34,197,94,.42);background:rgba(21,93,62,.32)}
        .scanner-card-watch{border-color:rgba(245,158,11,.42);background:rgba(120,74,15,.28)}
        .scanner-card-avoid{border-color:rgba(239,68,68,.42);background:rgba(127,29,29,.30)}
        .scanner-lane-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:2px 0 12px}
        .scanner-lane{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#0b1220;overflow:hidden}
        .scanner-lane header{padding:8px 10px;color:#f8fafc;font-size:12px;font-weight:950;text-transform:uppercase;border-bottom:1px solid rgba(148,163,184,.16);letter-spacing:.02em}
        .scanner-lane-row{padding:8px 10px;border-bottom:1px solid rgba(148,163,184,.12);display:grid;grid-template-columns:.62fr 1fr;gap:2px 8px;align-items:start}
        .scanner-lane-row:last-child{border-bottom:0}
        .scanner-lane-row strong{color:#f8fafc;font-size:13px;font-weight:950}
        .scanner-lane-row span{color:#e2e8f0;font-size:12px;text-align:right;font-weight:800}
        .scanner-lane-row small{color:#cbd5e1;font-size:11px;line-height:1.25}
        .scanner-lane-row em{color:#94a3b8;font-size:11px;line-height:1.25;text-align:right;font-style:normal}
        .scanner-lane-empty{padding:12px 10px;color:#94a3b8;font-size:12px}
        .scanner-lane-buy header{background:rgba(21,128,61,.28);color:#bbf7d0}
        .scanner-lane-watch header{background:rgba(180,83,9,.28);color:#fde68a}
        .scanner-lane-avoid header{background:rgba(153,27,27,.30);color:#fecaca}
        .finviz-wallboard{border:1px solid rgba(148,163,184,.24);border-radius:8px;background:#080d18;margin:8px 0 12px;overflow:hidden;box-shadow:0 18px 46px rgba(0,0,0,.22)}
        .wall-ticker{display:grid;grid-template-columns:.75fr 1.6fr .8fr;gap:10px;align-items:center;padding:8px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.18)}
        .wall-ticker strong{color:#f8fafc;font-size:12px;font-weight:950;letter-spacing:.04em}.wall-ticker span{color:#cbd5e1;font-size:12px;line-height:1.25;text-align:right}
        .wall-stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.16)}
        .wall-stats div{background:#0b1220;padding:9px 10px;min-height:74px}.wall-stats span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase}.wall-stats strong{display:block;color:#f8fafc;font-size:26px;line-height:1.05;margin:5px 0}.wall-stats small{color:#cbd5e1;font-size:11px;line-height:1.2}
        .wall-stat-buy{box-shadow:inset 0 0 0 1px rgba(34,197,94,.28)}.wall-stat-watch{box-shadow:inset 0 0 0 1px rgba(245,158,11,.30)}.wall-stat-avoid{box-shadow:inset 0 0 0 1px rgba(239,68,68,.30)}
        .wall-main{display:grid;grid-template-columns:1.25fr 1fr;gap:8px;padding:8px}.wall-heatmap{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));grid-auto-rows:74px;gap:4px}
        .wall-tile{border:1px solid rgba(148,163,184,.18);border-radius:4px;padding:7px;min-width:0;display:grid;grid-template-columns:1fr auto;grid-template-rows:auto 1fr auto;gap:2px;background:#172033;overflow:hidden}.wall-tile strong{color:#f8fafc;font-size:16px;line-height:1;font-weight:950}.wall-tile span{font-size:13px;color:#e2e8f0;font-weight:900;text-align:right}.wall-tile small{grid-column:1/3;color:#e2e8f0;font-size:11px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.wall-tile em{grid-column:1/3;color:#cbd5e1;font-size:10px;font-style:normal;line-height:1.1}
        .wall-tile-buy{background:rgba(21,128,61,var(--tile-alpha))}.wall-tile-watch{background:rgba(180,83,9,var(--tile-alpha))}.wall-tile-avoid{background:rgba(153,27,27,var(--tile-alpha))}
        .wall-tables{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.wall-table{border:1px solid rgba(148,163,184,.18);border-radius:6px;overflow:hidden;background:#0b1220}.wall-table header{padding:6px 8px;color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.wall-table table{width:100%;border-collapse:collapse}.wall-table th,.wall-table td{padding:5px 6px;border-bottom:1px solid rgba(148,163,184,.10);font-size:10px;line-height:1.15;text-align:left;color:#cbd5e1}.wall-table th{color:#94a3b8;font-weight:900;text-transform:uppercase}.wall-table td:first-child{color:#f8fafc;font-weight:950}.wall-table tr:last-child td{border-bottom:0}
        .top-opps-header{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#111827;padding:8px 10px;margin:4px 0 8px}.top-opps-header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.top-opps-header span{color:#94a3b8;font-size:11px;text-align:right}
        .top-opp-card{border:1px solid rgba(148,163,184,.22);border-radius:8px 8px 0 0;background:#0b1220;padding:9px 10px;min-height:110px;border-bottom:0}.top-opp-card div{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.top-opp-card span{color:#94a3b8;font-size:10px;text-transform:uppercase;font-weight:950}.top-opp-card strong{color:#f8fafc;font-size:20px;line-height:1;font-weight:950}.top-opp-route{display:inline-flex;margin-top:7px;border:1px solid rgba(148,163,184,.24);border-radius:999px;background:rgba(15,23,42,.56);padding:3px 7px;color:#cbd5e1;font-size:9px;font-style:normal;font-weight:950;text-transform:uppercase;letter-spacing:.03em}.top-opp-card .top-opp-meter{display:block;position:relative;height:15px;border:1px solid rgba(148,163,184,.18);border-radius:999px;background:rgba(15,23,42,.70);overflow:hidden;margin:7px 0 0}.top-opp-meter span{display:block;height:100%;background:linear-gradient(90deg,#38bdf8,#22c55e);opacity:.92}.top-opp-meter em{position:absolute;inset:0;display:grid;place-items:center;color:#f8fafc;font-size:9px;font-style:normal;font-weight:950;text-shadow:0 1px 6px rgba(0,0,0,.55)}.top-opp-card p{margin:8px 0 6px;color:#e2e8f0;font-size:12px;line-height:1.2;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.top-opp-card small{display:block;color:#94a3b8;font-size:10px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.top-opp-card .top-opp-next{color:#f8fafc;margin-top:4px;font-weight:850}.top-opp-card .top-opp-mini-status{color:#7dd3fc;margin-top:4px;font-weight:900}.top-opp-buy{border-color:rgba(34,197,94,.42);background:rgba(21,93,62,.24)}.top-opp-watch{border-color:rgba(245,158,11,.42);background:rgba(120,74,15,.22)}.top-opp-avoid{border-color:rgba(239,68,68,.42);background:rgba(127,29,29,.22)}
        .market-movers-tape{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 12px;overflow:hidden}.market-movers-tape>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.15)}.market-movers-tape>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.market-movers-tape>header span{color:#94a3b8;font-size:11px;text-align:right}.market-mover-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .market-mover-table{background:#0b1220;overflow:hidden;border-top:2px solid rgba(148,163,184,.25)}.market-mover-table header{padding:6px 8px;color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;background:#0f172a;border-bottom:1px solid rgba(148,163,184,.12)}.market-mover-table table{width:100%;border-collapse:collapse}.market-mover-table th,.market-mover-table td{padding:5px 6px;border-bottom:1px solid rgba(148,163,184,.10);font-size:10px;line-height:1.15;text-align:left;color:#cbd5e1}.market-mover-table th{color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase}.market-mover-table td:first-child{color:#f8fafc;font-weight:950}.market-mover-table td:nth-child(2),.market-mover-table td:nth-child(3),.market-mover-table td:nth-child(4){text-align:right}.market-mover-table td:last-child{max-width:110px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.market-mover-buy{border-top-color:#22c55e}.market-mover-watch{border-top-color:#f59e0b}.market-mover-avoid{border-top-color:#ef4444}
        .trading-desk-empty{display:flex;justify-content:space-between;gap:14px;align-items:center;border:1px dashed rgba(251,191,36,.44);border-left:4px solid #f59e0b;border-radius:8px;background:linear-gradient(135deg,rgba(120,74,15,.22),rgba(15,23,42,.92));padding:10px 12px;margin:6px 0 8px}.trading-desk-empty span{display:block;color:#fbbf24;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.06em}.trading-desk-empty strong{display:block;color:#f8fafc;font-size:18px;line-height:1.1;margin-top:4px}.trading-desk-empty p{margin:5px 0 0;color:#cbd5e1;font-size:12px;line-height:1.25}.trading-desk-empty ul{margin:0;padding-left:18px;color:#e2e8f0;font-size:11px;line-height:1.35}
        .trading-desk-filter-scope{display:flex;align-items:center;gap:10px;border:1px solid rgba(56,189,248,.26);border-radius:8px;background:rgba(8,47,73,.24);padding:7px 9px;margin:3px 0 7px}.trading-desk-filter-scope span{color:#7dd3fc;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.06em}.trading-desk-filter-scope strong{color:#f8fafc;font-size:14px;line-height:1}.trading-desk-filter-scope p{margin:0;color:#cbd5e1;font-size:11px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .trading-desk-strip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;border:1px solid rgba(148,163,184,.22);border-radius:8px;background:rgba(148,163,184,.16);overflow:hidden;margin:4px 0 8px}.desk-chip{background:#0b1220;padding:8px 9px;min-width:0;border-top:2px solid rgba(148,163,184,.28)}.desk-chip span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.desk-chip strong{display:block;color:#f8fafc;font-size:20px;line-height:1;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.desk-chip small{display:block;color:#cbd5e1;font-size:10px;line-height:1.12;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.desk-buy{border-top-color:#22c55e;background:rgba(21,93,62,.22)}.desk-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.20)}.desk-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}
        .trading-desk-focus{display:grid;grid-template-columns:minmax(180px,.34fr) minmax(0,1fr);gap:12px;align-items:center;border:1px solid rgba(148,163,184,.24);border-left:4px solid #f59e0b;border-radius:10px;background:linear-gradient(135deg,rgba(15,23,42,.98),rgba(30,41,59,.76));padding:10px 12px;margin:2px 0 8px;box-shadow:0 14px 36px rgba(0,0,0,.16)}.trading-desk-focus span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.06em}.trading-desk-focus strong{display:block;color:#f8fafc;font-size:28px;line-height:1;margin-top:3px;font-weight:950}.trading-desk-focus em{display:block;color:#cbd5e1;font-size:11px;font-style:normal;margin-top:5px;font-weight:800}.trading-desk-focus p{margin:0;color:#f8fafc;font-size:15px;line-height:1.2;font-weight:950}.trading-desk-focus small{grid-column:2;color:#94a3b8;font-size:11px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.desk-focus-buy{border-left-color:#22c55e;background:linear-gradient(135deg,rgba(21,93,62,.32),rgba(15,23,42,.92))}.desk-focus-watch{border-left-color:#f59e0b}.desk-focus-avoid{border-left-color:#ef4444;background:linear-gradient(135deg,rgba(127,29,29,.30),rgba(15,23,42,.92))}
        .trading-desk-queue{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0b1220;margin:0 0 8px;overflow:hidden}.trading-desk-queue>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.trading-desk-queue>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.trading-desk-queue>header span{color:#94a3b8;font-size:11px;line-height:1.2;text-align:right}.trading-desk-queue>div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.desk-queue-card{background:#0b1220;border-top:2px solid rgba(148,163,184,.30);padding:8px 10px;min-width:0}.desk-queue-card header{display:flex;align-items:center;gap:8px}.desk-queue-card header span{color:#94a3b8;font-size:10px;font-weight:950}.desk-queue-card header strong{color:#f8fafc;font-size:16px;font-weight:950;line-height:1}.desk-queue-card header em{margin-left:auto;color:#f8fafc;font-size:12px;font-style:normal;font-weight:950}.desk-queue-card p{margin:6px 0 4px;color:#f8fafc;font-size:11px;line-height:1.15;font-weight:850}.desk-queue-card small,.desk-queue-card i{display:block;color:#cbd5e1;font-size:10px;line-height:1.16;font-style:normal;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.desk-queue-card i{color:#94a3b8;margin-top:4px}.desk-queue-buy{border-top-color:#22c55e;background:rgba(21,93,62,.24)}.desk-queue-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.22)}.desk-queue-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}
        .desk-opportunity-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0 0 8px}.desk-opportunity-card{border:1px solid rgba(148,163,184,.22);border-top:3px solid rgba(148,163,184,.40);border-radius:10px;background:#0b1220;padding:10px 11px;min-width:0;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.desk-opportunity-card header{display:flex;align-items:start;justify-content:space-between;gap:10px}.desk-opportunity-card header strong{color:#f8fafc;font-size:20px;line-height:1;font-weight:950}.desk-opportunity-card header span{color:#cbd5e1;font-size:10px;line-height:1.15;text-align:right;font-weight:900}.desk-card-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.12);border-radius:7px;overflow:hidden;margin:9px 0}.desk-card-metrics b,.desk-card-metrics em{display:block;background:#111827;text-align:center}.desk-card-metrics b{color:#f8fafc;font-size:14px;padding:6px 4px 2px;font-weight:950}.desk-card-metrics em{color:#94a3b8;font-size:9px;padding:0 4px 6px;font-style:normal;font-weight:950;text-transform:uppercase}.desk-opportunity-card p{margin:0 0 5px;color:#f8fafc;font-size:13px;line-height:1.2;font-weight:950}.desk-missing-row{display:flex;gap:4px;flex-wrap:wrap;margin:0 0 6px}.desk-missing-chip{display:inline-flex;border:1px solid rgba(148,163,184,.24);border-radius:999px;padding:3px 6px;font-size:9px;line-height:1;font-weight:950;text-transform:uppercase;letter-spacing:.02em}.desk-missing-buy{color:#bbf7d0;background:rgba(34,197,94,.14);border-color:rgba(34,197,94,.28)}.desk-missing-watch{color:#fde68a;background:rgba(245,158,11,.14);border-color:rgba(245,158,11,.28)}.desk-missing-avoid{color:#fecaca;background:rgba(239,68,68,.14);border-color:rgba(239,68,68,.28)}.desk-opportunity-card small{display:block;color:#94a3b8;font-size:10px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.desk-opportunity-buy{border-top-color:#22c55e;background:rgba(21,93,62,.23)}.desk-opportunity-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.21)}.desk-opportunity-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}
        .compare-board{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 12px;overflow:hidden}.compare-board>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.15)}.compare-board>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.compare-board>header span{color:#94a3b8;font-size:11px;text-align:right}.compare-grid-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .compare-card{background:#0b1220;border-top:2px solid rgba(148,163,184,.25);padding:9px 10px;min-height:168px}.compare-card header{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:start}.compare-card header span{color:#94a3b8;font-size:10px;font-weight:950}.compare-card header strong{color:#f8fafc;font-size:19px;line-height:1;font-weight:950}.compare-card header em{color:#e2e8f0;font-size:10px;font-style:normal;font-weight:950;text-transform:uppercase;text-align:right}.compare-score{display:flex;justify-content:space-between;gap:10px;align-items:end;margin:8px 0}.compare-score b{color:#f8fafc;font-size:30px;line-height:1}.compare-score span{color:#94a3b8;font-size:10px;text-transform:uppercase;font-weight:950}.compare-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.12);border-radius:6px;overflow:hidden}.compare-grid div{background:#0f172a;padding:6px}.compare-grid span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase}.compare-grid strong{display:block;color:#f8fafc;font-size:12px;line-height:1.1;margin-top:3px}.compare-card p{margin:8px 0 4px;color:#e2e8f0;font-size:11px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.compare-card small{display:block;color:#cbd5e1;font-size:10px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.compare-card-buy{border-top-color:#22c55e;background:rgba(21,93,62,.25)}.compare-card-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.22)}.compare-card-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}
        .ticker-intel{display:grid;grid-template-columns:minmax(260px,.95fr) minmax(360px,1.45fr) minmax(260px,.9fr);gap:1px;border:1px solid rgba(148,163,184,.24);border-radius:8px;background:rgba(148,163,184,.14);margin:6px 0 10px;overflow:hidden;box-shadow:0 16px 42px rgba(0,0,0,.22)}
        .ticker-intel-main,.ticker-intel-kpis,.ticker-intel-next{background:#070c16}.ticker-intel-main{padding:10px 12px;border-left:4px solid #f59e0b}.ticker-intel-buy .ticker-intel-main{border-left-color:#22c55e}.ticker-intel-avoid .ticker-intel-main{border-left-color:#ef4444}.ticker-intel-main span,.ticker-intel-next span{display:block;color:#93c5fd;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.06em}.ticker-intel-main h3{margin:4px 0;color:#f8fafc;font-size:26px;line-height:1;font-weight:950}.ticker-intel-main strong{display:block;color:#e2e8f0;font-size:12px;line-height:1.15;font-weight:950;text-transform:uppercase}.ticker-intel-main p{margin:6px 0 0;color:#cbd5e1;font-size:11px;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .ticker-intel-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.ticker-intel-kpis div{background:#0b1220;padding:8px 9px;min-width:0}.ticker-intel-kpis span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase}.ticker-intel-kpis strong{display:block;color:#f8fafc;font-size:16px;line-height:1.05;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ticker-intel-next{padding:9px 11px}.ticker-intel-next ul{margin:6px 0 0;padding-left:16px;color:#e2e8f0}.ticker-intel-next li{font-size:11px;line-height:1.22;margin:0 0 3px;font-weight:850}.ticker-intel-buy .ticker-intel-next li:first-child{color:#bbf7d0}.ticker-intel-watch .ticker-intel-next li:first-child{color:#fde68a}.ticker-intel-avoid .ticker-intel-next li:first-child{color:#fecaca}
        .company-research{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.company-research>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.company-research>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.company-research>header span{color:#94a3b8;font-size:11px;text-align:right}.research-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.research-card{display:block;background:#0b1220;padding:8px 9px;border-top:2px solid rgba(96,165,250,.55);text-decoration:none;min-width:0}.research-card:hover{background:#111827;border-top-color:#f59e0b}.research-card span{display:block;color:#93c5fd;font-size:9px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.research-card strong{display:block;color:#f8fafc;font-size:13px;line-height:1.05;margin-top:5px;font-weight:950}.research-card small{display:block;color:#cbd5e1;font-size:10px;line-height:1.16;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .screener-presets{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.screener-presets>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.screener-presets>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.screener-presets>header span{color:#94a3b8;font-size:11px;text-align:right}.preset-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .preset-card{background:#0b1220;padding:8px 9px;border-top:2px solid rgba(148,163,184,.28);min-width:0}.preset-card header{display:flex;justify-content:space-between;gap:8px;align-items:center}.preset-card header strong{color:#f8fafc;font-size:12px;font-weight:950;text-transform:uppercase}.preset-card header span{color:#f8fafc;font-size:18px;line-height:1;font-weight:950}.preset-card div{display:flex;justify-content:space-between;gap:8px;margin-top:7px}.preset-card div span{color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase}.preset-card b{color:#f8fafc;font-size:18px;line-height:1}.preset-card p{margin:6px 0 3px;color:#e2e8f0;font-size:11px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.preset-card small{display:block;color:#94a3b8;font-size:10px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.preset-card-buy{border-top-color:#22c55e;background:rgba(21,93,62,.22)}.preset-card-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.20)}.preset-card-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}
        .provider-center{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.provider-center>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.provider-center>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.provider-center>header span{color:#94a3b8;font-size:11px;text-align:right}.provider-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .alpaca-gate{display:grid;grid-template-columns:minmax(210px,.46fr) 1fr minmax(240px,.52fr);gap:10px;align-items:center;padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.14);border-left:3px solid rgba(148,163,184,.45);background:rgba(15,23,42,.80)}.alpaca-gate span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.alpaca-gate strong{display:block;color:#f8fafc;font-size:18px;line-height:1.05;font-weight:950;margin-top:3px}.alpaca-gate em{display:block;color:#cbd5e1;font-style:normal;font-size:10px;font-weight:900;margin-top:4px}.alpaca-gate p{margin:0;color:#e2e8f0;font-size:12px;font-weight:850;line-height:1.25}.alpaca-gate aside{display:grid;gap:4px}.alpaca-gate b{color:#f8fafc;font-size:11px;line-height:1.05;text-transform:uppercase}.alpaca-gate small{color:#94a3b8;font-size:10px;line-height:1.2}.alpaca-gate-buy{border-left-color:#22c55e;background:rgba(21,93,62,.18)}.alpaca-gate-watch{border-left-color:#f59e0b;background:rgba(120,74,15,.17)}.alpaca-gate-avoid{border-left-color:#ef4444;background:rgba(127,29,29,.18)}
        .alpaca-paper-panel{display:grid;grid-template-columns:minmax(210px,.46fr) minmax(360px,1fr) minmax(320px,.7fr);gap:10px;align-items:center;padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.14);border-left:3px solid rgba(148,163,184,.45);background:rgba(8,13,24,.86)}.alpaca-paper-panel span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.alpaca-paper-panel strong{display:block;color:#f8fafc;font-size:18px;line-height:1.05;font-weight:950;margin-top:3px}.alpaca-paper-panel em{display:block;color:#cbd5e1;font-style:normal;font-size:10px;font-weight:900;margin-top:4px}.alpaca-paper-panel aside{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14);border-radius:6px;overflow:hidden}.alpaca-paper-panel aside b,.alpaca-paper-panel aside strong{background:#0b1220;margin:0;padding:6px 7px;font-size:10px;line-height:1.05}.alpaca-paper-panel aside b{color:#94a3b8;text-transform:uppercase}.alpaca-paper-panel aside strong{font-size:13px;color:#f8fafc}.alpaca-paper-panel p{margin:0;color:#e2e8f0;font-size:11px;font-weight:850;line-height:1.25}.alpaca-paper-buy{border-left-color:#22c55e;background:rgba(21,93,62,.16)}.alpaca-paper-watch{border-left-color:#f59e0b;background:rgba(120,74,15,.16)}.alpaca-paper-avoid{border-left-color:#ef4444;background:rgba(127,29,29,.16)}
        .paper-journal-panel{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.paper-journal-panel>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.paper-journal-panel>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.paper-journal-panel>header span{color:#94a3b8;font-size:11px;text-align:right}.paper-journal-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.16)}.paper-journal-summary b{display:block;background:#0b1220;padding:7px 8px}.paper-journal-summary span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase}.paper-journal-summary strong{display:block;color:#f8fafc;font-size:15px;line-height:1;margin-top:4px}.paper-journal-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.paper-journal-card{background:rgba(21,93,62,.18);border-top:2px solid #22c55e;padding:8px 9px;min-width:0}.paper-journal-avoid{background:rgba(127,29,29,.20);border-top-color:#ef4444}.paper-journal-card header{display:flex;justify-content:space-between;gap:8px}.paper-journal-card header strong{color:#f8fafc;font-size:15px;line-height:1;font-weight:950}.paper-journal-card header span{color:#cbd5e1;font-size:10px;font-weight:900;text-align:right}.paper-journal-card div{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14);border-radius:6px;overflow:hidden;margin-top:7px}.paper-journal-card b{background:#0b1220;color:#f8fafc;font-size:10px;line-height:1.05;padding:6px 5px}.paper-journal-card p{margin:7px 0 0;color:#cbd5e1;font-size:10px;line-height:1.18;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.paper-journal-empty{grid-column:1/-1;background:#0b1220;color:#94a3b8;font-size:12px;font-weight:850;padding:10px}.paper-journal-table{padding:7px;background:#080d18}.paper-journal-table table{width:100%;border-collapse:collapse}.paper-journal-table th,.paper-journal-table td{padding:5px 6px;border-bottom:1px solid rgba(148,163,184,.10);font-size:10px;line-height:1.15;text-align:left;color:#cbd5e1}.paper-journal-table th{color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase}.paper-journal-table td:first-child{color:#f8fafc;font-weight:950}
        .paper-position-panel{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.paper-position-panel>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.paper-position-panel>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.paper-position-panel>header span{color:#94a3b8;font-size:11px;text-align:right}.paper-position-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.paper-position-card{background:rgba(21,93,62,.18);border-top:2px solid #22c55e;padding:8px 9px;min-width:0}.paper-position-watch{background:rgba(120,74,15,.20);border-top-color:#f59e0b}.paper-position-avoid{background:rgba(127,29,29,.20);border-top-color:#ef4444}.paper-position-card header{display:flex;justify-content:space-between;gap:8px}.paper-position-card header strong{color:#f8fafc;font-size:15px;line-height:1;font-weight:950}.paper-position-card header span{color:#bbf7d0;font-size:10px;font-weight:900;text-align:right}.paper-position-watch header span{color:#fde68a}.paper-position-avoid header span{color:#fecaca}.paper-position-card div{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14);border-radius:6px;overflow:hidden;margin-top:7px}.paper-position-card b{background:#0b1220;color:#f8fafc;font-size:9px;line-height:1.05;padding:6px 5px}.paper-position-card p{margin:7px 0 0;color:#cbd5e1;font-size:10px;line-height:1.18;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.paper-position-card small{display:block;color:#94a3b8;font-size:9px;line-height:1.15;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.paper-position-empty{padding:10px 12px;color:#cbd5e1;font-size:11px;font-weight:850;background:#0b1220;border-top:1px solid rgba(148,163,184,.12)}
        .paper-strategy-panel{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.paper-strategy-panel>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.paper-strategy-panel>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.paper-strategy-panel>header span{color:#94a3b8;font-size:11px;text-align:right}.paper-strategy-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.paper-strategy-card{background:rgba(21,93,62,.18);border-top:2px solid #22c55e;padding:8px 9px;min-width:0}.paper-strategy-avoid{background:rgba(127,29,29,.20);border-top-color:#ef4444}.paper-strategy-card header{display:flex;justify-content:space-between;gap:8px}.paper-strategy-card header strong{color:#f8fafc;font-size:12px;line-height:1.08;font-weight:950}.paper-strategy-card header span{color:#bbf7d0;font-size:10px;font-weight:900;text-align:right}.paper-strategy-avoid header span{color:#fecaca}.paper-strategy-card div{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14);border-radius:6px;overflow:hidden;margin-top:7px}.paper-strategy-card b{background:#0b1220;color:#f8fafc;font-size:9px;line-height:1.05;padding:6px 5px}.paper-strategy-card p{margin:7px 0 0;color:#cbd5e1;font-size:10px;line-height:1.18;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.paper-strategy-empty{padding:10px 12px;color:#cbd5e1;font-size:11px;font-weight:850;background:#0b1220;border-top:1px solid rgba(148,163,184,.12)}
        .paper-exec-panel{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.paper-exec-panel>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.paper-exec-panel>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.paper-exec-panel>header span{color:#94a3b8;font-size:11px;text-align:right}.paper-exec-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.paper-exec-summary{grid-column:1/-1;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.16)}.paper-exec-summary b{display:block;background:#0b1220;padding:7px 8px}.paper-exec-summary span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.paper-exec-summary strong{display:block;color:#f8fafc;font-size:14px;line-height:1;margin-top:4px;font-weight:950}.paper-exec-card,.paper-gap-card{background:rgba(21,93,62,.18);border-top:2px solid #22c55e;padding:8px 9px;min-width:0}.paper-gap-card{background:rgba(120,74,15,.18);border-top-color:#f59e0b}.paper-exec-muted{border-color:rgba(245,158,11,.35)}.paper-exec-card header,.paper-gap-card header{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.paper-exec-card header strong,.paper-gap-card header strong{color:#f8fafc;font-size:15px;line-height:1;font-weight:950}.paper-exec-card header span,.paper-gap-card header span{color:#bbf7d0;font-size:10px;line-height:1.12;text-align:right;font-weight:900}.paper-gap-card header span{color:#fde68a}.paper-exec-card div,.paper-gap-card div{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14);border-radius:6px;overflow:hidden;margin-top:7px}.paper-gap-card div{grid-template-columns:repeat(3,minmax(0,1fr))}.paper-exec-card b,.paper-gap-card b{background:#0b1220;color:#f8fafc;font-size:10px;line-height:1.05;padding:6px 5px}        .paper-exec-panel{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.paper-exec-panel>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.paper-exec-panel>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.paper-exec-panel>header span{color:#94a3b8;font-size:11px;text-align:right}.paper-exec-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.paper-exec-summary{grid-column:1/-1;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.16)}.paper-exec-summary b{display:block;background:#0b1220;padding:7px 8px}.paper-exec-summary span{display:block;color:#94a3b8;font-size:9px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.paper-exec-summary strong{display:block;color:#f8fafc;font-size:14px;line-height:1;margin-top:4px;font-weight:950}.paper-exec-card,.paper-gap-card{background:rgba(21,93,62,.18);border-top:2px solid #22c55e;padding:8px 9px;min-width:0}.paper-gap-card{background:rgba(120,74,15,.18);border-top-color:#f59e0b}.paper-exec-muted{border-color:rgba(245,158,11,.35)}.paper-exec-card header,.paper-gap-card header{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.paper-exec-card header strong,.paper-gap-card header strong{color:#f8fafc;font-size:15px;line-height:1;font-weight:950}.paper-exec-card header span,.paper-gap-card header span{color:#bbf7d0;font-size:10px;line-height:1.12;text-align:right;font-weight:900}.paper-gap-card header span{color:#fde68a}.paper-exec-card div,.paper-gap-card div{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14);border-radius:6px;overflow:hidden;margin-top:7px}.paper-gap-card div{grid-template-columns:repeat(3,minmax(0,1fr))}.paper-exec-card b,.paper-gap-card b{background:#0b1220;color:#f8fafc;font-size:10px;line-height:1.05;padding:6px 5px}.paper-exec-card p,.paper-gap-card p{margin:7px 0 0;color:#cbd5e1;font-size:10px;line-height:1.18;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.paper-check-card{background:rgba(120,74,15,.18);border-top:2px solid #f59e0b;padding:8px 9px;min-width:0}.paper-check-avoid{background:rgba(127,29,29,.20);border-top-color:#ef4444}.paper-check-card header{display:flex;justify-content:space-between;gap:8px}.paper-check-card header strong{color:#f8fafc;font-size:15px;line-height:1;font-weight:950}.paper-check-card header span{color:#fde68a;font-size:10px;font-weight:900;text-align:right}.paper-check-avoid header span{color:#fecaca}.paper-check-card div{display:grid;grid-template-columns:48px 1fr;gap:1px;background:rgba(148,163,184,.14);border-radius:6px;overflow:hidden;margin-top:6px}.paper-check-card b{background:#0b1220;color:#94a3b8;font-size:9px;line-height:1.05;padding:6px 5px;text-transform:uppercase}.paper-check-card p{background:#0b1220;margin:0;color:#f8fafc;font-size:10px;line-height:1.05;padding:6px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.paper-check-card small{display:block;color:#cbd5e1;font-size:10px;line-height:1.15;font-weight:850;margin-top:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .provider-card{background:#0b1220;padding:8px 9px;border-top:2px solid rgba(148,163,184,.28);min-width:0}.provider-card header{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.provider-card header strong{color:#f8fafc;font-size:12px;font-weight:950;text-transform:uppercase}.provider-card header span{color:#e2e8f0;font-size:10px;line-height:1.1;text-align:right;font-weight:900}.provider-card div{display:flex;justify-content:space-between;gap:8px;margin-top:7px}.provider-card b{color:#f8fafc;font-size:13px;line-height:1;font-weight:950}.provider-card em{color:#94a3b8;font-size:10px;line-height:1;font-style:normal;text-align:right}.provider-card p{margin:6px 0 3px;color:#e2e8f0;font-size:11px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.provider-card small{display:block;color:#cbd5e1;font-size:10px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.provider-card i{display:block;color:#94a3b8;font-size:9px;line-height:1.15;font-style:normal;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.provider-card-buy{border-top-color:#22c55e;background:rgba(21,93,62,.22)}.provider-card-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.20)}.provider-card-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}.provider-card-neutral{border-top-color:#64748b}
        .exit-board{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#080d18;margin:4px 0 10px;overflow:hidden}.exit-board>header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.exit-board>header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.exit-board>header span{color:#94a3b8;font-size:11px;text-align:right}.exit-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .exit-card{background:#0b1220;padding:8px 9px;border-top:2px solid rgba(148,163,184,.28);min-width:0}.exit-card header{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.exit-card header strong{color:#f8fafc;font-size:14px;font-weight:950}.exit-card header span{color:#e2e8f0;font-size:10px;line-height:1.1;text-align:right;font-weight:900;text-transform:uppercase}.exit-levels{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;margin-top:7px;background:rgba(148,163,184,.12);border-radius:6px;overflow:hidden}.exit-levels div{background:#0f172a;padding:5px}.exit-levels span{display:block;color:#94a3b8;font-size:8px;font-weight:950;text-transform:uppercase}.exit-levels b{display:block;color:#f8fafc;font-size:11px;line-height:1.05;margin-top:3px}.exit-card p{margin:7px 0 3px;color:#e2e8f0;font-size:11px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.exit-card small{display:block;color:#cbd5e1;font-size:10px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.exit-card-buy{border-top-color:#22c55e;background:rgba(21,93,62,.22)}.exit-card-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.20)}.exit-card-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}
        .executive-cockpit{display:grid;grid-template-columns:minmax(260px,1.1fr) minmax(380px,1.35fr) minmax(300px,.95fr);gap:1px;border:1px solid rgba(148,163,184,.26);border-radius:8px;background:rgba(148,163,184,.14);margin:6px 0 10px;overflow:hidden;box-shadow:0 18px 48px rgba(0,0,0,.24)}
        .exec-main,.exec-kpis,.exec-tape{background:#070c16}.exec-main{padding:12px 14px;border-left:4px solid #f59e0b}.executive-cockpit-buy .exec-main{border-left-color:#22c55e}.executive-cockpit-avoid .exec-main{border-left-color:#ef4444}.exec-main span{display:block;color:#93c5fd;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.06em}.exec-main h2{margin:5px 0;color:#f8fafc;font-size:28px;line-height:1.02;font-weight:950;letter-spacing:-.02em}.exec-main p{margin:0;color:#cbd5e1;font-size:12px;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.exec-action-line{display:grid;grid-template-columns:1fr;gap:2px;border:1px solid rgba(148,163,184,.22);border-radius:7px;margin-top:9px;padding:7px 8px;background:rgba(15,23,42,.70)}.exec-action-line strong{color:#f8fafc;font-size:12px;line-height:1.1;font-weight:950}.exec-action-line small{color:#cbd5e1;font-size:10px;line-height:1.15;font-weight:800}.exec-action-buy{border-color:rgba(34,197,94,.34);background:rgba(21,93,62,.20)}.exec-action-watch{border-color:rgba(245,158,11,.34);background:rgba(120,74,15,.18)}.exec-action-avoid{border-color:rgba(239,68,68,.34);background:rgba(127,29,29,.18)}
        .exec-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.exec-kpis div{background:#0b1220;padding:9px 10px}.exec-kpis span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase}.exec-kpis strong{display:block;color:#f8fafc;font-size:20px;line-height:1.05;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.exec-kpis small{display:block;color:#cbd5e1;font-size:10px;line-height:1.18;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .exec-tape{display:grid;grid-template-columns:1fr;gap:1px;background:rgba(148,163,184,.14)}.exec-tape-item{display:grid;grid-template-columns:.58fr .85fr;gap:2px 8px;background:#0b1220;padding:6px 9px;border-left:3px solid rgba(148,163,184,.30)}.exec-tape-item strong{color:#f8fafc;font-size:13px;line-height:1;font-weight:950}.exec-tape-item span{color:#e2e8f0;font-size:11px;text-align:right;font-weight:900}.exec-tape-item small{grid-column:1/3;color:#94a3b8;font-size:10px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.exec-tape-buy{border-left-color:#22c55e}.exec-tape-watch{border-left-color:#f59e0b}.exec-tape-avoid{border-left-color:#ef4444}
        .opportunity-matrix{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#070c16;margin:0 0 12px;overflow:hidden;box-shadow:0 14px 38px rgba(0,0,0,.20)}
        .opportunity-matrix header{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:8px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.16)}
        .opportunity-matrix header strong{display:block;color:#f8fafc;font-size:12px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.opportunity-matrix header span{display:block;color:#94a3b8;font-size:11px;line-height:1.25;margin-top:2px}.opportunity-matrix aside{text-align:right}.opportunity-matrix aside b{display:block;color:#f8fafc;font-size:18px;line-height:1;font-weight:950}.opportunity-matrix aside small{display:block;color:#cbd5e1;font-size:11px;line-height:1.2;margin-top:4px}
        .matrix-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.matrix-summary div{background:#0b1220;padding:7px 10px}.matrix-summary span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase}.matrix-summary strong{display:block;color:#f8fafc;font-size:20px;line-height:1.05;margin-top:3px}
        .matrix-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .matrix-row{background:#0b1220;border-left:3px solid rgba(148,163,184,.32);padding:8px 9px;min-height:86px;display:grid;grid-template-columns:auto 1fr auto;gap:3px 8px;align-content:start}.matrix-row span{color:#94a3b8;font-size:10px;font-weight:950}.matrix-row strong{color:#f8fafc;font-size:15px;font-weight:950}.matrix-row em{color:#e2e8f0;font-size:11px;font-style:normal;text-align:right;font-weight:900}.matrix-row b{grid-column:1/2;color:#f8fafc;font-size:18px;line-height:1;font-weight:950}.matrix-row small{grid-column:2/4;color:#cbd5e1;font-size:10px;line-height:1.18;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.matrix-row i{grid-column:1/4;color:#94a3b8;font-size:10px;line-height:1.18;font-style:normal;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.matrix-row-buy{border-left-color:#22c55e;background:rgba(21,93,62,.30)}.matrix-row-watch{border-left-color:#f59e0b;background:rgba(120,74,15,.24)}.matrix-row-avoid{border-left-color:#ef4444;background:rgba(127,29,29,.24)}
        .validation-board{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0b1220;margin:0 0 12px;overflow:hidden}
        .validation-board header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.validation-board header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.validation-board header span{color:#94a3b8;font-size:11px;line-height:1.2;text-align:right}
        .validation-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .validation-row{background:#0b1220;border-top:2px solid rgba(148,163,184,.28);padding:8px 9px;min-height:96px}.validation-row strong{display:block;color:#f8fafc;font-size:15px;line-height:1;font-weight:950}.validation-row span{display:block;color:#e2e8f0;font-size:11px;font-weight:950;text-transform:uppercase;margin-top:5px}.validation-row small{display:block;color:#cbd5e1;font-size:10px;line-height:1.18;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.validation-row em{display:block;color:#f8fafc;font-size:10px;line-height:1.18;font-style:normal;margin-top:5px}.validation-row i{display:block;color:#94a3b8;font-size:10px;line-height:1.18;font-style:normal;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.validation-row-buy{border-top-color:#22c55e;background:rgba(21,93,62,.25)}.validation-row-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.22)}.validation-row-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}
        .breadth-strip{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0b1220;margin:0 0 12px;overflow:hidden}
        .breadth-strip header{padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14);color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}
        .breadth-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .breadth-card{background:#0b1220;padding:8px 10px}.breadth-card div:first-child{display:flex;justify-content:space-between;gap:8px;align-items:center}.breadth-card strong{color:#e2e8f0;font-size:11px;font-weight:950;text-transform:uppercase}.breadth-card span{color:#f8fafc;font-size:14px;font-weight:950}.breadth-card small{display:block;color:#94a3b8;font-size:10px;line-height:1.2;margin-top:5px}.breadth-bar{height:7px;border-radius:999px;background:#1f2937;overflow:hidden;margin-top:6px}.breadth-bar i{display:block;height:100%;border-radius:999px;background:#64748b}.breadth-card-buy .breadth-bar i{background:#22c55e}.breadth-card-watch .breadth-bar i{background:#f59e0b}.breadth-card-avoid .breadth-bar i{background:#ef4444}
        .index-strip{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0b1220;margin:0 0 12px;overflow:hidden}
        .index-strip header{padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14);color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}
        .regime-banner{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;border-bottom:1px solid rgba(148,163,184,.14);background:#0f172a}.regime-banner strong{font-size:13px;font-weight:950;text-transform:uppercase}.regime-banner span{color:#cbd5e1;font-size:11px;line-height:1.25;text-align:right}.regime-banner-buy strong{color:#86efac}.regime-banner-watch strong{color:#fde68a}.regime-banner-avoid strong{color:#fecaca}
        .index-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .index-card{background:#0b1220;padding:8px 9px;min-width:0;border-top:2px solid rgba(148,163,184,.28)}.index-card div{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.index-card span{color:#94a3b8;font-size:10px;font-weight:900;text-transform:uppercase}.index-card strong{color:#f8fafc;font-size:15px;font-weight:950}.index-card em{display:block;color:#e2e8f0;font-size:12px;font-weight:850;font-style:normal;margin-top:5px}.index-card small{display:block;color:#94a3b8;font-size:10px;line-height:1.2;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.index-card-buy{border-top-color:#22c55e}.index-card-watch{border-top-color:#f59e0b}.index-card-avoid{border-top-color:#ef4444}
        .technical-movers{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0b1220;margin:0 0 12px;overflow:hidden}
        .technical-movers>header{padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14);color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}
        .mover-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .mover-table{background:#0b1220;overflow:hidden}.mover-table header{padding:7px 9px;font-size:11px;font-weight:950;text-transform:uppercase;color:#f8fafc;border-bottom:1px solid rgba(148,163,184,.12)}.mover-table table{width:100%;border-collapse:collapse}.mover-table th,.mover-table td{padding:6px 8px;border-bottom:1px solid rgba(148,163,184,.10);font-size:11px;line-height:1.15;text-align:left;color:#cbd5e1}.mover-table th{color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase}.mover-table td:first-child{color:#f8fafc;font-weight:950}.mover-table td:nth-child(2),.mover-table td:nth-child(3),.mover-table td:nth-child(4){text-align:right}.mover-table-buy header{background:rgba(21,128,61,.25);color:#bbf7d0}.mover-table-watch header{background:rgba(180,83,9,.25);color:#fde68a}.mover-table-avoid header{background:rgba(153,27,27,.25);color:#fecaca}
        .buy-gap-panel{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#0b1220;margin:0 0 12px;overflow:hidden}
        .buy-gap-panel header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.buy-gap-panel header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.buy-gap-panel header span{color:#94a3b8;font-size:11px;line-height:1.2;text-align:right}
        .buy-gap-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}
        .buy-gap-strip{grid-column:1/-1;display:grid;grid-template-columns:1.08fr .92fr;gap:1px;background:rgba(148,163,184,.14);border-bottom:1px solid rgba(148,163,184,.14)}.buy-gap-strip section{background:#0f172a;padding:9px 11px;border-top:2px solid rgba(96,165,250,.55)}.buy-gap-strip span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.buy-gap-strip strong{display:block;color:#f8fafc;font-size:16px;line-height:1.08;font-weight:950;margin-top:3px}.buy-gap-strip em{display:block;color:#cbd5e1;font-size:10.5px;line-height:1.2;font-style:normal;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.buy-gap-strip-buy section{border-top-color:#22c55e;background:rgba(21,93,62,.26)}.buy-gap-strip-watch section{border-top-color:#f59e0b;background:rgba(120,74,15,.24)}.buy-gap-strip-avoid section{border-top-color:#ef4444;background:rgba(127,29,29,.24)}
        .confirmation-radar{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#080d18;margin:0 0 10px;overflow:hidden}.confirmation-radar header{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:7px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.confirmation-radar header strong{color:#f8fafc;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.04em}.confirmation-radar header span{color:#94a3b8;font-size:11px;line-height:1.2;text-align:right}.confirm-radar-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:1px;background:rgba(148,163,184,.14)}.confirm-radar-card{background:#0b1220;border-top:2px solid rgba(148,163,184,.30);padding:8px 9px;min-width:0}.confirm-radar-card header{display:flex;background:transparent;border:0;padding:0;align-items:flex-start}.confirm-radar-card header strong{color:#f8fafc;font-size:12px;line-height:1.08;text-transform:none;letter-spacing:0}.confirm-radar-card header span{color:#f8fafc;font-size:18px;line-height:1;font-weight:950;text-align:right}.confirm-radar-card p{margin:7px 0 4px;color:#e2e8f0;font-size:10.5px;line-height:1.15;font-weight:850}.confirm-radar-card small{display:block;color:#93c5fd;font-size:10px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.confirm-radar-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.20)}.confirm-radar-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.20)}.confirm-radar-neutral{border-top-color:#60a5fa}
        .buy-gap-card{background:#0b1220;border-top:2px solid rgba(148,163,184,.28);padding:8px 9px;min-height:132px}.buy-gap-card div{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.buy-gap-card strong{color:#f8fafc;font-size:15px;line-height:1;font-weight:950}.buy-gap-card span{color:#e2e8f0;font-size:10px;text-transform:uppercase;font-weight:950;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.buy-gap-card em{display:block;color:#f8fafc;font-size:10px;line-height:1.18;font-style:normal;margin-top:6px}.buy-gap-progress{display:block;height:7px;border-radius:999px;background:#1f2937;overflow:hidden;margin-top:6px}.buy-gap-progress u{display:block;height:100%;border-radius:999px;background:#f59e0b;text-decoration:none}.buy-gap-card small{display:block;color:#fecaca;font-size:10px;line-height:1.18;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.buy-gap-card i{display:block;color:#bbf7d0;font-size:10px;line-height:1.18;font-style:normal;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.buy-gap-buy{border-top-color:#22c55e;background:rgba(21,93,62,.25)}.buy-gap-buy .buy-gap-progress u{background:#22c55e}.buy-gap-watch{border-top-color:#f59e0b;background:rgba(120,74,15,.22)}.buy-gap-avoid{border-top-color:#ef4444;background:rgba(127,29,29,.22)}.buy-gap-avoid .buy-gap-progress u{background:#ef4444}
        .kpibox{display:inline-block;padding:8px 12px;background:#081023;border-radius:8px;margin-right:8px;color:var(--muted)}
        .metrics-row{display:flex;gap:12px;flex-wrap:wrap}
        .metric-card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));padding:10px;border-radius:8px;min-width:160px}
        .symbol-kpi{min-height:96px;padding:12px 14px;border:1px solid rgba(148,163,184,.24);border-radius:8px;background:#0f172a;box-shadow:0 1px 0 rgba(255,255,255,.04) inset;margin-bottom:10px;overflow-wrap:anywhere}
        .symbol-kpi-label{font-size:12px;line-height:1.25;color:#b7c1d0;font-weight:700;margin-bottom:8px}
        .symbol-kpi-value{font-size:20px;line-height:1.18;color:#f8fafc;font-weight:800;white-space:normal;letter-spacing:0}
        .symbol-kpi-detail{font-size:12px;line-height:1.25;color:#cbd5e1;margin-top:8px}
        .symbol-kpi-buy{border-color:rgba(34,197,94,.45);background:rgba(21,93,62,.46)}
        .symbol-kpi-watch{border-color:rgba(245,158,11,.45);background:rgba(120,74,15,.38)}
        .symbol-kpi-avoid{border-color:rgba(239,68,68,.45);background:rgba(127,29,29,.38)}
        .trade-plan{border:1px solid rgba(148,163,184,.28);border-radius:8px;padding:14px 16px;margin:6px 0 14px;background:#0b1220}
        .trade-plan-title{font-size:24px;line-height:1.18;font-weight:850;color:#f8fafc;margin-bottom:6px;letter-spacing:0}
        .trade-plan-line{font-size:15px;line-height:1.35;color:#cbd5e1}
        .trade-plan-buy{border-color:rgba(34,197,94,.55)}
        .trade-plan-watch{border-color:rgba(245,158,11,.55)}
        .trade-plan-avoid{border-color:rgba(239,68,68,.55)}
        .command-center{display:grid;grid-template-columns:minmax(0,1fr) minmax(230px,340px);gap:16px;align-items:stretch;border:1px solid rgba(148,163,184,.24);border-radius:8px;background:#0d1426;padding:16px 18px;margin:6px 0 12px}
        .command-center-buy{border-color:rgba(34,197,94,.48)}
        .command-center-watch{border-color:rgba(245,158,11,.48)}
        .command-center-avoid{border-color:rgba(239,68,68,.48)}
        .command-kicker{font-size:12px;text-transform:uppercase;color:#93c5fd;font-weight:900;letter-spacing:0}
        .command-main h2{margin:4px 0 8px;color:#f8fafc;font-size:32px;line-height:1.05;letter-spacing:0}
        .command-main p{margin:0;color:#cbd5e1;font-size:15px;line-height:1.35}
        .command-side{border:1px solid rgba(148,163,184,.20);border-radius:8px;background:#111827;padding:13px 14px;display:flex;flex-direction:column;justify-content:center;min-height:120px}
        .command-side span{font-size:12px;color:#94a3b8;font-weight:900;text-transform:uppercase;letter-spacing:0}
        .command-side strong{font-size:24px;line-height:1.1;color:#f8fafc;margin:6px 0;overflow-wrap:anywhere}
        .command-side small{font-size:13px;line-height:1.3;color:#cbd5e1}
        .command-checklist{display:grid;grid-template-columns:repeat(7,minmax(110px,1fr));gap:8px;margin:2px 0 12px}
        .command-check{border:1px solid rgba(148,163,184,.18);border-radius:8px;background:#0f172a;padding:9px 10px;min-height:86px}
        .command-check span{display:block;color:#94a3b8;font-size:11px;line-height:1.2;font-weight:900;text-transform:uppercase;letter-spacing:0}
        .command-check strong{display:block;color:#f8fafc;font-size:16px;line-height:1.15;margin-top:6px}
        .command-check small{display:block;color:#cbd5e1;font-size:12px;line-height:1.25;margin-top:5px;overflow-wrap:anywhere}
        .command-check-buy{border-color:rgba(34,197,94,.38)}
        .command-check-watch{border-color:rgba(245,158,11,.34)}
        .command-check-avoid{border-color:rgba(239,68,68,.38)}
        .study-hero{display:flex;align-items:center;justify-content:space-between;gap:16px;border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#0d1426;padding:16px;margin:6px 0 14px}
        .study-hero h2{margin:2px 0 6px;color:#f8fafc;font-size:26px;line-height:1.12;letter-spacing:0}
        .study-hero p{margin:0;color:#cbd5e1;line-height:1.35}
        .study-kicker{font-size:12px;text-transform:uppercase;color:#93c5fd;font-weight:900;letter-spacing:0}
        .study-status{min-width:150px;border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#111827;padding:10px 12px;text-align:left}
        .study-status span{display:block;color:#94a3b8;font-size:12px;font-weight:800}
        .study-status strong{display:block;color:#f8fafc;font-size:18px;line-height:1.2;margin-top:4px}
        .study-hero-buy{border-color:rgba(34,197,94,.44)}
        .study-hero-watch{border-color:rgba(245,158,11,.44)}
        .study-hero-avoid{border-color:rgba(239,68,68,.44)}
        .study-card{min-height:138px;border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#0b1220;padding:14px;margin-bottom:10px}
        .study-card-label{font-size:13px;color:#f8fafc;font-weight:900;margin-bottom:8px}
        .study-card-text{font-size:14px;line-height:1.36;color:#cbd5e1}
        .study-card-buy{border-color:rgba(34,197,94,.36)}
        .study-card-watch{border-color:rgba(245,158,11,.36)}
        .study-card-avoid{border-color:rgba(239,68,68,.36)}
        .chart-context{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,420px);gap:14px;align-items:center;border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#0b1220;padding:14px 16px;margin:8px 0 12px}
        .chart-context-kicker{font-size:12px;text-transform:uppercase;color:#93c5fd;font-weight:900;letter-spacing:0}
        .chart-context-title{font-size:22px;line-height:1.12;color:#f8fafc;font-weight:900;margin-top:3px}
        .chart-context-text{font-size:14px;line-height:1.35;color:#cbd5e1;margin-top:6px}
        .chart-context-grid{display:grid;grid-template-columns:1fr;gap:7px}
        .chart-context-grid span{display:flex;justify-content:space-between;gap:10px;border:1px solid rgba(148,163,184,.18);border-radius:8px;background:#111827;padding:8px 10px;color:#94a3b8;font-size:12px;font-weight:800}
        .chart-context-grid strong{color:#f8fafc;text-align:right}
        .chart-context-buy{border-color:rgba(34,197,94,.44)}
        .chart-context-watch{border-color:rgba(245,158,11,.44)}
        .chart-context-avoid{border-color:rgba(239,68,68,.44)}
        .company-profile-card{border:1px solid rgba(148,163,184,.22);border-radius:8px;background:#0b1220;margin:0 0 12px;overflow:hidden}
        .company-profile-card header{padding:9px 10px;background:#111827;border-bottom:1px solid rgba(148,163,184,.14)}.company-profile-card header strong{display:block;color:#f8fafc;font-size:15px;line-height:1.1;font-weight:950}.company-profile-card header span{display:block;color:#94a3b8;font-size:11px;line-height:1.2;margin-top:4px}
        .company-profile-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:rgba(148,163,184,.14)}.company-profile-grid div{background:#0b1220;padding:7px 9px}.company-profile-grid span{display:block;color:#94a3b8;font-size:10px;font-weight:950;text-transform:uppercase}.company-profile-grid strong{display:block;color:#f8fafc;font-size:12px;line-height:1.15;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.company-profile-card p{margin:0;padding:9px 10px;color:#cbd5e1;font-size:11px;line-height:1.32}
        [data-testid="stTabs"] button{font-weight:800;color:#cbd5e1}
        [data-testid="stTabs"] button[aria-selected="true"]{color:#a78bfa}
        [data-testid="stVegaLiteChart"]{border:1px solid rgba(148,163,184,.18);border-radius:8px;background:#0b1220;padding:10px}
        .stButton button{border-radius:8px;border:1px solid rgba(148,163,184,.30);background:#111827;color:#f8fafc;font-weight:800}
        .stButton button:hover{border-color:#a78bfa;color:#f8fafc}
        div[data-testid="stDataFrame"]{border:1px solid rgba(148,163,184,.18);border-radius:8px;overflow:hidden}
        @media (max-width:1100px){.command-checklist{grid-template-columns:repeat(3,minmax(0,1fr))}}
        @media (max-width:1100px){.ticker-intel,.alpaca-gate,.alpaca-paper-panel{grid-template-columns:1fr}.ticker-intel-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.paper-journal-summary,.paper-exec-summary,.trading-desk-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.trading-desk-queue>div{grid-template-columns:repeat(2,minmax(0,1fr))}.desk-opportunity-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.paper-position-grid,.paper-strategy-grid,.paper-journal-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.exit-grid,.provider-grid,.preset-grid,.research-grid,.paper-exec-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.confirm-radar-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.executive-cockpit{grid-template-columns:1fr}.scanner-tape,.scanner-compass{grid-template-columns:1fr}.scanner-tape div{border-right:0;border-bottom:1px solid rgba(148,163,184,.16);padding:0 0 8px}.scanner-tape div:last-child{border-bottom:0;padding-bottom:0}.scanner-compass em{text-align:left}.scanner-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.scanner-lane-grid{grid-template-columns:1fr}.wall-main{grid-template-columns:1fr}.wall-heatmap{grid-template-columns:repeat(4,minmax(0,1fr))}.market-mover-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.compare-grid-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.matrix-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.validation-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.buy-gap-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.breadth-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.index-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.mover-grid{grid-template-columns:1fr}}
        @media (max-width:900px){.roxy-hero{grid-template-columns:1fr}.platform-strip{grid-template-columns:1fr}.roxy-hero h1{font-size:26px}.brand-logo-img{width:150px;max-width:42vw}.roxy-hero-right{grid-template-columns:1fr 1fr}.dashboard-action-queue header{display:block}.dashboard-action-queue header span{display:block;text-align:left;margin-top:4px}.dashboard-action-queue>div{grid-template-columns:1fr}.chart-command-head{display:block}.chart-command-head aside{justify-content:flex-start;margin-top:8px}.chart-next-action{white-space:normal}.chart-check-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.chart-context{grid-template-columns:1fr}.command-center{grid-template-columns:1fr}.selected-asset-banner{display:block;padding:8px 9px}.selected-asset-banner strong{font-size:14px}.selected-asset-banner small{font-size:10px}.selected-asset-scope{text-align:left;min-width:0;margin-top:7px}}
        @media (max-width:600px){.metric-card{min-width:120px}.roxy-brand-row{align-items:flex-start}.brand-logo-img{width:132px;max-width:46vw}.roxy-hero-right{grid-template-columns:1fr}.study-hero{display:block}.study-status{margin-top:12px}.flow-step{width:100%}.chart-command-head strong{font-size:19px}.chart-check-strip{grid-template-columns:1fr}.chart-check-pill{padding:7px 8px}.command-checklist{grid-template-columns:1fr}.command-main h2{font-size:25px}.ticker-intel-kpis{grid-template-columns:1fr 1fr}.ticker-intel-main h3{font-size:23px}.company-research>header,.confirmation-radar>header,.exit-board>header,.paper-position-panel>header,.paper-strategy-panel>header,.paper-journal-panel>header,.paper-exec-panel>header,.provider-center>header,.screener-presets>header,.trading-desk-queue>header{display:block}.company-research>header span,.confirmation-radar>header span,.exit-board>header span,.paper-position-panel>header span,.paper-strategy-panel>header span,.paper-journal-panel>header span,.paper-exec-panel>header span,.provider-center>header span,.screener-presets>header span,.trading-desk-queue>header span{display:block;text-align:left;margin-top:4px}.trading-desk-focus{display:block}.trading-desk-focus p{margin-top:8px}.trading-desk-focus small{display:block;margin-top:5px;white-space:normal}.trading-desk-queue>div{grid-template-columns:1fr}.desk-opportunity-grid{grid-template-columns:1fr}.paper-position-grid,.paper-strategy-grid,.paper-journal-grid{grid-template-columns:1fr}.exit-grid,.provider-grid,.preset-grid,.research-grid,.confirm-radar-grid,.paper-exec-grid{grid-template-columns:1fr}.exec-kpis{grid-template-columns:1fr 1fr}.exec-main h2{font-size:23px}.roxy-radar-guide,.scanner-card-grid{grid-template-columns:1fr}.scanner-lane-row{grid-template-columns:1fr}.scanner-lane-row span,.scanner-lane-row em{text-align:left}.scanner-tape div{display:block}.scanner-tape span{text-align:left;display:block;margin-top:4px}.wall-ticker{grid-template-columns:1fr}.wall-ticker span{text-align:left}.wall-stats{grid-template-columns:1fr 1fr}.wall-heatmap{grid-template-columns:repeat(2,minmax(0,1fr))}.wall-tables{grid-template-columns:1fr}.top-opps-header{display:block}.top-opps-header span{display:block;text-align:left;margin-top:4px}.compare-board>header{display:block}.compare-board>header span{display:block;text-align:left;margin-top:4px}.compare-grid-cards{grid-template-columns:1fr}.opportunity-matrix header{display:block}.opportunity-matrix aside{text-align:left;margin-top:7px}.matrix-summary{grid-template-columns:1fr}.matrix-grid{grid-template-columns:1fr}.validation-board header{display:block}.validation-board header span{text-align:left;display:block;margin-top:4px}.validation-grid{grid-template-columns:1fr}.buy-gap-panel header{display:block}.buy-gap-panel header span{text-align:left;display:block;margin-top:4px}.buy-gap-grid{grid-template-columns:1fr}.buy-gap-strip{grid-template-columns:1fr}.buy-gap-strip em{white-space:normal}.breadth-grid{grid-template-columns:1fr}.index-grid{grid-template-columns:1fr}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    show_focused_roxy_app()
    return

    st.sidebar.header("Quick Links")
    st.sidebar.write("Data files in `output/` and `alerts/` are used to populate this dashboard.")

    st.sidebar.markdown("**Snapshot Service**")
    if st.sidebar.button("Run snapshot now (server)"):
        try:
            # if user signed in, snapshot their account; else snapshot all
            u = st.session_state.get("user")
            if u:
                val = storage.snapshot_account_point(u)
                st.sidebar.success(f"Snapshot for {u}: {val:.2f}")
            else:
                # run for all users
                import tools.account_snapshot_service as svc

                svc.snapshot_all(storage.DB_PATH)
                st.sidebar.success("Snapshot run for all users")
        except Exception as e:
            st.sidebar.error(f"Snapshot failed: {e}")

    st.sidebar.markdown("Run the background snapshot service with Docker:")
    st.sidebar.code("docker-compose up -d snapshot")

    # Local start/stop controls (development) with admin token
    st.sidebar.markdown("**Local snapshot process**")
    import tools.process_manager as pm

    interval = st.sidebar.number_input("Interval (minutes)", min_value=1, max_value=60, value=5)
    admin_token_input = st.sidebar.text_input("Admin token (for promotion)", type="password")
    # determine admin via stored role
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    # if user signed in, check role from storage
    user = st.session_state.get("user")
    try:
        if user and storage.is_admin(user):
            st.session_state.is_admin = True
    except Exception:
        pass

    # Allow bootstrap promotion via ADMIN_TOKEN env var: promotes current signed-in user to admin
    try:
        from config import ADMIN_TOKEN, ADMIN_ORGS

        if ADMIN_TOKEN and admin_token_input and admin_token_input == ADMIN_TOKEN:
            if user:
                try:
                    storage.set_user_role(user, "admin", actor=user)
                    st.session_state.is_admin = True
                    st.sidebar.success(f"User {user} promoted to admin")
                except Exception:
                    st.sidebar.error("Failed to promote user to admin in storage")
            else:
                st.sidebar.warning("Sign in first to use admin token promotion")
        # If ADMIN_ORGS configured, and user has an access token in session, auto-grant admin when signing in
        if (
            not st.session_state.is_admin
            and user
            and st.session_state.get("access_token")
            and 'ADMIN_ORGS' in globals()
        ):
            try:
                token = st.session_state.get("access_token")
                orgs = auth.get_user_orgs(token)
                cfg_orgs = [o.strip() for o in (ADMIN_ORGS or "").split(",") if o.strip()]
                if any(o in cfg_orgs for o in orgs):
                    storage.set_user_role(user, "admin", actor="oauth")
                    st.session_state.is_admin = True
                    st.sidebar.success(f"User {user} auto-promoted to admin via GitHub org membership")
            except Exception:
                pass
    except Exception:
        pass

    has_admin = bool(st.session_state.is_admin)

    # Snapshot history (user-level and global)
    st.sidebar.markdown("**Snapshot History**")
    if st.session_state.get("user"):
        try:
            user_pts = storage.get_equity_series(st.session_state.user)
            if user_pts:
                df_pts = pd.DataFrame(user_pts, columns=["ts", "equity"])  # type: ignore
                df_pts["ts"] = pd.to_datetime(df_pts["ts"])
                st.sidebar.write(f"Last {len(df_pts)} points for {st.session_state.user}")
                st.sidebar.table(df_pts.tail(5))
                st.sidebar.write("Latest:", str(df_pts["ts"].iloc[-1]))
            else:
                st.sidebar.write("No snapshots for your account yet.")
        except Exception:
            st.sidebar.write("No snapshot data available.")
    else:
        st.sidebar.write("Sign in to view your snapshot history.")

    # show all accounts summary
    st.sidebar.markdown("**All accounts**")
    try:
        acct_rows = storage.list_accounts()
        if acct_rows:
            for user, created_ts, equity in acct_rows[:10]:
                role = storage.get_user_role(user)
                st.sidebar.write(f"{user} ({role}): {equity:.2f} (created {created_ts})")
        else:
            st.sidebar.write("No accounts registered yet.")
    except Exception:
        st.sidebar.write("Unable to list accounts.")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Start snapshot"):
            if not has_admin:
                st.sidebar.error("Admin token required to start service")
            else:
                try:
                    pid = pm.start_snapshot_service(interval=int(interval), run_once=False)
                    st.sidebar.success(f"Started snapshot pid={pid}")
                except Exception as e:
                    st.sidebar.error(f"Failed to start: {e}")
    with col2:
        if st.button("Stop snapshot"):
            if not has_admin:
                st.sidebar.error("Admin token required to stop service")
            else:
                try:
                    ok = pm.stop_snapshot_service()
                    if ok:
                        st.sidebar.success("Stopped snapshot service")
                    else:
                        st.sidebar.info("No snapshot service running")
                except Exception as e:
                    st.sidebar.error(f"Failed to stop: {e}")

    # Small Grok model toggle (writes .grok_settings.json)
    st.sidebar.markdown("**Grok Code Fast 1**")
    enabled_local = grok_control.is_enabled() or ENABLE_GROK_CODE_FAST
    if enabled_local:
        st.sidebar.success("Grok Code Fast 1: ENABLED")
    else:
        st.sidebar.info("Grok Code Fast 1: disabled")

    if st.sidebar.button("Toggle Grok Code Fast 1"):
        # flip the on-disk setting and show confirmation
        new_state = not grok_control.is_enabled()
        grok_control.apply_enable_for_all(new_state)
        st.experimental_rerun()

    # Admin management panel: allow admins to change roles
    if has_admin:
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Admin: Manage Roles**")
        try:
            users = [r[0] for r in storage.list_accounts()]
        except Exception:
            users = []
        target = st.sidebar.selectbox("Select user to edit role", options=[""] + users)
        new_role = st.sidebar.selectbox("Role", options=["user", "admin"], index=0)
        if st.sidebar.button("Set role") and target:
            try:
                storage.set_user_role(target, new_role, actor=st.session_state.get("user"))
                st.sidebar.success(f"Set {target} -> {new_role}")
            except Exception as e:
                st.sidebar.error(f"Failed to set role: {e}")

        # show recent role audit entries
        st.sidebar.markdown("**Role change audit**")
        try:
            rows = storage.list_role_audit(limit=50)
            if rows:
                import pandas as _pd

                df_a = _pd.DataFrame(rows, columns=["id", "actor", "target_user", "old_role", "new_role", "ts"])  # type: ignore
                st.sidebar.dataframe(df_a.head(10))
                csv = df_a.to_csv(index=False)
                st.sidebar.download_button(
                    "Export role audit CSV", data=csv, file_name="role_audit.csv", mime="text/csv"
                )
            else:
                st.sidebar.write("No recent role changes.")
        except Exception:
            st.sidebar.write("Unable to read role audit.")
        # server-side export: write CSV to output/ so it can be served by a static server
        try:
            outp = Path("output")
            outp.mkdir(parents=True, exist_ok=True)
            if st.sidebar.button("Export audit CSV to server output"):
                fn = (
                    outp
                    / f"role_audit_export_{st.session_state.get('user','admin')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
                )
                df_a.to_csv(fn, index=False)
                st.sidebar.success(f"Wrote {fn}")
                st.sidebar.write("If you run a static file server for `output/`, download at:")
                st.sidebar.write(str(fn))
        except Exception:
            pass

        # Admin A/B Testing panel
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Admin: A/B Tests**")
        try:
            from tools import ab_test

            test_name = st.sidebar.text_input("Test name (create/update)", key="ab_test_name")
            variants_raw = st.sidebar.text_input(
                "Variants (name:weight,name2:weight)", value="control:1,canary:1", key="ab_variants"
            )
            if st.sidebar.button("Create/Update A/B test") and test_name:
                try:
                    pairs = [p.strip() for p in variants_raw.split(",") if p.strip()]
                    variants = {}
                    for p in pairs:
                        if ":" not in p:
                            raise ValueError("Variant format must be name:weight")
                        n, w = p.split(":", 1)
                        variants[n.strip()] = float(w)
                    ab_test.create_test(test_name, variants)
                    st.sidebar.success(f"Created/updated test '{test_name}'")
                except Exception as e:
                    st.sidebar.error(f"Failed to create test: {e}")

            tests = ab_test.list_tests()
            if tests:
                import pandas as _pd

                df_tests = _pd.DataFrame(tests, columns=["id", "name", "description", "ts"])  # type: ignore
                sel = st.sidebar.selectbox("Select test", options=[""] + df_tests["name"].tolist(), key="ab_select")
                st.sidebar.dataframe(df_tests[["id", "name", "ts"]])
                if sel:
                    conn = sqlite3.connect(storage.DB_PATH)
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT ab_variants.name, ab_variants.weight FROM ab_variants JOIN ab_tests ON ab_variants.test_id=ab_tests.id WHERE ab_tests.name = ?",
                        (sel,),
                    )
                    var_rows = cur.fetchall()
                    conn.close()
                    if var_rows:
                        st.sidebar.write("Variants:")
                        st.sidebar.table(_pd.DataFrame(var_rows, columns=["name", "weight"]))
                    if st.sidebar.button("Show recent results for selected test"):
                        conn = sqlite3.connect(storage.DB_PATH)
                        cur = conn.cursor()
                        cur.execute(
                            """
                            SELECT r.id, a.key, a.actor, a.variant, r.action, r.symbol, r.qty, r.price, r.side, r.result_type, r.result_value, r.ts
                            FROM ab_results r
                            JOIN ab_assignments a ON r.assignment_id = a.id
                            JOIN ab_tests t ON a.test_id = t.id
                            WHERE t.name = ?
                            ORDER BY r.id DESC LIMIT 200
                            """,
                            (sel,),
                        )
                        res = cur.fetchall()
                        conn.close()
                        if res:
                            df_res = _pd.DataFrame(res, columns=["id", "key", "actor", "variant", "action", "symbol", "qty", "price", "side", "result_type", "result_value", "ts"])  # type: ignore
                            st.subheader(f"A/B Results for {sel}")
                            st.dataframe(df_res)
                        else:
                            st.info("No results yet for this test")
                # Admin auto-exec controls
                st.sidebar.markdown("---")
                st.sidebar.markdown("**Admin: Auto-Exec (LLM)**")
                try:
                    from tools.auto_exec import run_llm_auto_pipeline

                    ae_symbols = st.sidebar.text_input("Symbols (comma-separated)", value="AAPL,MSFT", key="ae_symbols")
                    ae_horizon = st.sidebar.text_input("Horizon", value="1d", key="ae_horizon")
                    ae_dry = st.sidebar.checkbox("Dry run (no executes)", value=True, key="ae_dry")
                    ae_execute = st.sidebar.checkbox("Auto execute if allowed", value=False, key="ae_execute")
                    if st.sidebar.button("Run Auto-Exec (LLM)"):
                        if not st.session_state.get("is_admin"):
                            st.sidebar.error("Admin required to run auto-exec")
                        else:
                            syms = [s.strip().upper() for s in ae_symbols.split(",") if s.strip()]
                            with st.spinner("Running LLM auto pipeline..."):
                                try:
                                    res = run_llm_auto_pipeline(
                                        user=st.session_state.get("user") or "admin",
                                        symbols=syms,
                                        horizon=ae_horizon,
                                        dry_run=ae_dry,
                                        auto_execute=ae_execute,
                                    )
                                    st.sidebar.success("Pipeline run completed")
                                    st.sidebar.json(res)
                                except Exception as e:
                                    st.sidebar.error(f"Auto pipeline failed: {e}")
                except Exception:
                    st.sidebar.write("Auto-exec module not available")
        except Exception:
            st.sidebar.write("A/B testing module not available")

    # --- Login-like sidebar
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        with st.sidebar.form("login_form"):
            st.markdown("## Sign in")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
            if submitted:
                # Basic local auth simulation: accept any non-empty username
                if username.strip():
                    st.session_state.user = username.strip()
                    st.experimental_rerun()
                else:
                    st.sidebar.error("Enter a username to sign in.")
        # GitHub device-flow sign-in (requires GITHUB_CLIENT_ID env var)
        if st.sidebar.button("Sign in with GitHub (device code)"):
            try:
                with st.spinner("Starting GitHub device flow — follow instructions shown below"):
                    import requests

                    api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                    r = requests.post(f"{api_root}/api/auth/device/start", timeout=10)
                    r.raise_for_status()
                    df = r.json()
                # store device flow state in session to allow polling
                st.session_state._gh_device = df
                st.sidebar.success("Device flow started — follow instructions below")
            except Exception as e:
                st.sidebar.error(f"GitHub sign-in failed: {e}")

        # If device flow started, show user_code and verification URI and allow polling
        if st.session_state.get("_gh_device"):
            gh = st.session_state.get("_gh_device")
            ver = gh.get("verification_uri_complete") or gh.get("verification_uri")
            st.sidebar.markdown("**Complete GitHub sign-in**")
            st.sidebar.write("Open the verification URL and enter the code below:")
            if ver:
                st.sidebar.markdown(f"{ver}")
            st.sidebar.info(f"Code: {gh.get('user_code')}")
            if st.sidebar.button("Poll GitHub for completion"):
                try:
                    with st.spinner("Waiting for GitHub authorization..."):
                        import requests

                        api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                        r = requests.post(
                            f"{api_root}/api/auth/device/poll",
                            json={"device_code": gh.get("device_code")},
                            timeout=10,
                        )
                        r.raise_for_status()
                        res = r.json()
                    st.session_state.user = res.get("username")
                    st.session_state.access_token = res.get("session_token")
                    try:
                        storage.create_account_if_missing(res.get("username"))
                    except Exception:
                        pass
                    # clear device flow state
                    st.session_state.pop("_gh_device", None)
                    st.success(f"Signed in as {res.get('username')}")
                    st.experimental_rerun()
                except Exception as e:
                    st.sidebar.error(f"GitHub sign-in polling failed: {e}")

        # Redirect-based OAuth helper (requires running tools/oauth_server.py)
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Sign in with GitHub (redirect)**")
        if st.sidebar.button("Start redirect OAuth (open local server)"):
            try:
                import requests
                import time

                port = 5000
                redirect_uri = f"http://127.0.0.1:{port}/callback"
                api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                r = requests.get(f"{api_root}/api/auth/start", params={"redirect_uri": redirect_uri}, timeout=10)
                r.raise_for_status()
                jd = r.json()
                url = jd.get("url")
                st.session_state._gh_redirect_url = url
                st.session_state._gh_state = jd.get("state")
                st.sidebar.success("Redirect flow started — open the authorize URL in your browser")
                # Automatically poll for the resulting session token for up to 120 seconds
                if st.session_state.get("_gh_state"):
                    state = st.session_state.get("_gh_state")
                    with st.spinner("Waiting for authorization to complete..."):
                        api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                        token = None
                        username = None
                        deadline = time.time() + 120
                        while time.time() < deadline:
                            try:
                                rr = requests.get(
                                    f"{api_root}/api/auth/check_state", params={"state": state}, timeout=5
                                )
                                if rr.status_code == 200:
                                    jd2 = rr.json()
                                    username = jd2.get("username")
                                    token = jd2.get("session_token")
                                    break
                            except Exception:
                                pass
                            time.sleep(2)
                        if token:
                            st.session_state.user = username
                            st.session_state.access_token = token
                            try:
                                storage.create_account_if_missing(username)
                            except Exception:
                                pass
                            st.success(f"Signed in as {username}")
                            # clear redirect state
                            st.session_state.pop("_gh_redirect_url", None)
                            st.session_state.pop("_gh_state", None)
                            st.experimental_rerun()
                        else:
                            st.info(
                                "Authorization not completed yet — try again or check the authorize URL in your browser"
                            )
            except Exception as e:
                st.sidebar.error(f"Redirect flow failed: {e}")

        if st.session_state.get("_gh_redirect_url"):
            st.sidebar.markdown("Open this URL to authorize:")
            st.sidebar.write(st.session_state.get("_gh_redirect_url"))
            if st.sidebar.button("Check for callback result"):
                try:
                    import requests

                    api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                    # the oauth callback writes run/oauth_callback.json; check for it

                    p = Path("run/oauth_callback.json")
                    if p.exists():
                        j = json.loads(p.read_text())
                        st.session_state.user = j.get("login")
                        st.session_state.access_token = j.get("access_token")
                        try:
                            storage.create_account_if_missing(st.session_state.user)
                        except Exception:
                            pass
                        p.unlink()
                        st.success(f"Signed in as {st.session_state.user}")
                        st.experimental_rerun()
                    else:
                        st.info("No callback found yet. Complete authorization in the browser and try again.")
                except Exception as e:
                    st.sidebar.error(f"Failed to read callback: {e}")
    else:
        st.sidebar.markdown(f"**Signed in as:** {st.session_state.user}")
        try:
            storage.create_account_if_missing(st.session_state.user)
        except Exception:
            pass
        if st.sidebar.button("Sign out"):
            st.session_state.user = None
            st.experimental_rerun()

    # --- Secrets & API keys management (admin only)
    try:
        if st.session_state.is_admin:
            st.sidebar.markdown("---")
            st.sidebar.markdown("**Secrets Manager (admin)**")
            from tools import secrets_service as ss

            with st.sidebar.expander("Create Secret"):
                sname = st.text_input("Secret name", key="s_name")
                svalue = st.text_input("Secret value", key="s_value")
                sprov = st.text_input("Provider (optional)", key="s_prov")
                smeta = st.text_area("Metadata (JSON, optional)", key="s_meta")
                if st.button("Create secret"):
                    try:
                        meta_obj = json.loads(smeta) if smeta else {}
                    except Exception:
                        st.error("Invalid metadata JSON")
                        meta_obj = None
                    try:
                        import requests, os

                        api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                        token = st.session_state.get("access_token") or os.getenv("ADMIN_TOKEN")
                        headers = {"Authorization": f"Bearer {token}"} if token else {}
                        payload = {"name": sname, "value": svalue, "provider": sprov or None, "metadata": meta_obj}
                        r = requests.post(f"{api_root}/api/secrets", headers=headers, json=payload, timeout=10)
                        r.raise_for_status()
                        jd = r.json()
                        st.success(f"Created secret {jd.get('name')} v{jd.get('version')}")
                    except Exception as e:
                        st.error(f"Create failed: {e}")

            with st.sidebar.expander("Secrets List"):
                try:
                    import requests, os

                    api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                    token = st.session_state.get("access_token") or os.getenv("ADMIN_TOKEN")
                    headers = {"Authorization": f"Bearer {token}"} if token else {}
                    r = requests.get(f"{api_root}/api/secrets", headers=headers, timeout=10)
                    r.raise_for_status()
                    rows = r.json()
                    if rows:
                        for r in rows:
                            st.write(f"{r.get('name')} (provider={r.get('provider')}) v{r.get('version')}")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"Reveal {r.get('name')}", key=f"reveal_{r.get('name')}"):
                                    try:
                                        rr = requests.get(
                                            f"{api_root}/api/secrets/{r.get('name')}/reveal",
                                            headers=headers,
                                            timeout=10,
                                        )
                                        rr.raise_for_status()
                                        jd = rr.json()
                                        st.code(jd.get("value"))
                                    except Exception as e:
                                        st.error(f"Reveal failed: {e}")
                            with col2:
                                if st.button(f"Rotate {r.get('name')}", key=f"rotate_{r.get('name')}"):
                                    try:
                                        rr = requests.post(
                                            f"{api_root}/api/secrets/{r.get('name')}/rotate",
                                            headers=headers,
                                            json={"reason": "rotated via UI"},
                                            timeout=10,
                                        )
                                        rr.raise_for_status()
                                        res = rr.json()
                                        st.success(f"Rotated {res.get('name')} -> v{res.get('version')}")
                                    except Exception as e:
                                        st.error(f"Rotate failed: {e}")
                    else:
                        st.write("No secrets found")
                except Exception as e:
                    st.error(f"Failed to list secrets: {e}")

            with st.sidebar.expander("API Keys"):
                if st.button("Create API key"):
                    try:
                        import requests, os

                        api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                        token = st.session_state.get("access_token") or os.getenv("ADMIN_TOKEN")
                        headers = {"Authorization": f"Bearer {token}"} if token else {}
                        payload = {
                            "name": f"ui-{st.session_state.get('user')}",
                            "owner": st.session_state.get('user'),
                            "scopes": ["secrets:reveal"],
                        }
                        r = requests.post(f"{api_root}/api/api-keys", headers=headers, json=payload, timeout=10)
                        r.raise_for_status()
                        st.code(json.dumps(r.json()))
                    except Exception as e:
                        st.error(f"Create API key failed: {e}")
                try:
                    import requests, os

                    api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                    token = st.session_state.get("access_token") or os.getenv("ADMIN_TOKEN")
                    headers = {"Authorization": f"Bearer {token}"} if token else {}
                    r = requests.get(f"{api_root}/api/api-keys", headers=headers, timeout=10)
                    r.raise_for_status()
                    keys = r.json()
                    if keys:
                        for k in keys:
                            st.write(
                                f"id={k['id']} name={k.get('name')} owner={k.get('owner')} revoked={k.get('revoked')}"
                            )
                            if st.button(f"Revoke {k['id']}", key=f"revoke_{k['id']}"):
                                try:
                                    rr = requests.post(
                                        f"{api_root}/api/api-keys/{k['id']}/revoke", headers=headers, timeout=10
                                    )
                                    rr.raise_for_status()
                                    st.success("Revoked")
                                except Exception as e:
                                    st.error(f"Revoke failed: {e}")
                    else:
                        st.write("No API keys")
                except Exception as e:
                    st.error(f"Failed to list API keys: {e}")
    except Exception:
        pass

    tabs = st.tabs(
        [
            "Cryptocurrencies",
            "Stocks",
            "Real Estate",
            "News",
            "Top Picks",
            "Execution",
            "SMA Strategy",
            "Snapshots",
        ]
    )  # type: ignore

    with tabs[0]:
        show_market_tab("crypto")
    with tabs[1]:
        show_market_tab("stocks")
    with tabs[2]:
        st.write("Real Estate — placeholder list")
        # For now list weekly report files as real-estate-like suggestions
        files = sorted(glob("alerts/weekly_report_*.txt"), reverse=True)
        if files:
            for f in files[:5]:
                st.write(f)
        else:
            st.write("No weekly reports found in alerts/.")
    with tabs[3]:
        show_news_tab()
    with tabs[4]:
        st.header("Top Picks")
        p = Path(TOP_PICKS_FILE)
        if p.exists():
            st.text(p.read_text())
        else:
            st.info("No top picks yet.")
        # AI Signals quick panel
        with st.expander("AI Signals (prototype)"):
            symbols_input = st.text_input("Symbols (comma separated)", value="AAPL,MSFT")
            horizon = st.selectbox("Horizon", options=["1d", "5m", "15m"], index=0)
            if st.button("Generate AI Signals"):
                api_root = st.session_state.get("api_root") or "http://127.0.0.1:8000"
                try:
                    import requests

                    payload = {
                        "symbols": [s.strip().upper() for s in symbols_input.split(",") if s.strip()],
                        "horizon": horizon,
                    }
                    r = requests.post(f"{api_root}/api/ai/signal", json=payload, timeout=20)
                    r.raise_for_status()
                    sigs = r.json()
                    if sigs:
                        st.write("Generated signals:")
                        st.json(sigs)
                        # quick backtest placeholder: run simple paper trade on first signal
                        try:
                            from adapters.paper_trader import SimplePaperTrader

                            user = st.session_state.get("user") or "ai-bot"
                            pt = SimplePaperTrader(user)
                            for s in sigs:
                                st.write(f"{s.get('action')} {s.get('symbol')} size_pct={s.get('size_pct')}")
                        except Exception:
                            pass
                    else:
                        st.info("No signals returned")
                except Exception as e:
                    st.error(f"AI signal generation failed: {e}")
    # Execution tab (paper trading adapter)
    with tabs[5]:
        st.header("Execution — Paper Trading")
        st.write(
            "Place orders via the simple paper trader adapter. Trades are persisted in `db/roxy.db` as simulated trades and positions."
        )
        user = st.session_state.get("user") or st.text_input("Execution user (will create account)")
        if user:
            try:
                storage.create_account_if_missing(user)
            except Exception:
                pass

            from adapters.paper_trader import SimplePaperTrader

            st.subheader("Execution realism")
            slippage = st.slider("Slippage %", min_value=0.0, max_value=5.0, value=0.0, step=0.1)
            fill_rate = st.slider("Fill rate %", min_value=0, max_value=100, value=100, step=5)
            # create paper trader with user-specified realism
            pt = SimplePaperTrader(user, slippage_pct=(slippage / 100.0), fill_rate=(fill_rate / 100.0))
            st.subheader("Account")
            try:
                eq = storage.get_account_equity(user)
            except Exception:
                eq = 0.0
            st.write(f"User: {user} — equity: {eq:.2f}")

            st.subheader("Place Order")
            symbol = st.text_input("Symbol", value="AAPL")
            qty = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.1)
            price = st.number_input("Price", min_value=0.0, value=0.0, step=0.01)
            colb, cols = st.columns(2)
            with colb:
                if st.button("Buy (paper)"):
                    try:
                        if price <= 0:
                            st.error("Set a positive price for this simple paper execution")
                        else:
                            pid = pt.buy(symbol, qty, price)
                            st.success(f"Opened paper position #{pid} for {symbol} @ {price}")
                    except Exception as e:
                        st.error(f"Buy failed: {e}")
            with cols:
                if st.button("Sell (paper)"):
                    try:
                        if price <= 0:
                            st.error("Set a positive price for this simple paper execution")
                        else:
                            pnl = pt.sell(symbol, qty, price)
                            st.success(f"Sold {qty} {symbol}, realized P&L {pnl:.2f}")
                    except Exception as e:
                        st.error(f"Sell failed: {e}")

            st.subheader("Open Positions")
            open_pos = storage.get_open_positions(user)
            if open_pos:
                df_open = pd.DataFrame(open_pos, columns=["id", "ts_open", "user", "symbol", "qty", "entry_price", "note"])  # type: ignore
                st.table(df_open)
            else:
                st.write("No open positions for this user.")
    with tabs[6]:
        show_sma_strategy_tab()
    with tabs[-1]:
        st.header("Snapshots — account equity history")
        try:
            users = ["All"] + [r[0] for r in storage.list_accounts()]
        except Exception:
            users = ["All"]
        sel_user = st.selectbox("User", users)
        limit = st.number_input("Max rows", min_value=10, max_value=10000, value=1000)
        start = st.date_input("From", value=None)
        end = st.date_input("To", value=None)

        if st.button("Load snapshots"):
            try:
                if sel_user == "All":
                    rows = storage.get_snapshot_points(limit=int(limit))
                else:
                    # restrict viewing other users unless admin
                    if sel_user != "All" and sel_user != st.session_state.get("user") and not has_admin:
                        st.error("Permission denied: admin required to view other users' snapshots")
                        rows = []
                    else:
                        rows = storage.get_snapshot_points(user=sel_user, limit=int(limit))
                import io

                if not rows:
                    st.info("No snapshot points found")
                else:
                    # normalize rows to DataFrame
                    df = pd.DataFrame(rows, columns=["user", "ts", "equity"])  # type: ignore
                    df["ts"] = pd.to_datetime(df["ts"])
                    if start:
                        df = df[df["ts"] >= pd.to_datetime(start)]
                    if end:
                        df = df[df["ts"] <= pd.to_datetime(end)]
                    st.write(f"Showing {len(df)} rows")
                    st.dataframe(df.sort_values(["user", "ts"]))

                    # CSV export
                    csv = df.to_csv(index=False)
                    st.download_button("Export CSV", data=csv, file_name="snapshots.csv", mime="text/csv")
                    # JSON export
                    js = df.to_dict(orient="records")
                    st.download_button(
                        "Export JSON", data=json.dumps(js), file_name="snapshots.json", mime="application/json"
                    )

                    # interactive chart
                    try:
                        chart_df = df.copy()
                        if "user" not in chart_df.columns:
                            chart_df["user"] = sel_user
                        chart = (
                            alt.Chart(chart_df)
                            .mark_line()
                            .encode(x=alt.X("ts:T", title="Time"), y=alt.Y("equity:Q", title="Equity"), color="user:N")
                        )
                        st.altair_chart(chart.interactive(), width="stretch")
                    except Exception:
                        pass
                    # admin exports to server `output/`
                    if has_admin:
                        if st.button("Export visible to server output"):
                            outp = Path("output")
                            outp.mkdir(parents=True, exist_ok=True)
                            fn = (
                                outp
                                / f"snapshots_export_{st.session_state.get('user','admin')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
                            )
                            df.to_csv(fn, index=False)
                            st.success(f"Wrote {fn}")
            except Exception as e:
                st.error(f"Failed to load snapshots: {e}")


if __name__ == "__main__":
    main()
