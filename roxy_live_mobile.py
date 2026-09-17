"""Additive, read-only mobile renderer; the existing terminal is never imported.

Public preview is opt-in. A future terminal integration must pass its real
server-side authorization callback, which is checked on every fragment rerun.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from html import escape
import os
from typing import Callable, Mapping

import roxy_live as live

PREVIEW_FLAG = "ROXY_LIVE_PUBLIC_PREVIEW"
SYMBOLS = ("NVDA", "SPY", "QQQ", "TSLA", "AAPL", "MSFT", "AMZN")
CSS = """<style>
.rlm-card{box-sizing:border-box;max-width:100%;padding:16px;margin:8px 0;
 border:1px solid #31516c;border-radius:14px;background:#091a2b;color:#edf6ff;
 overflow-wrap:anywhere;font-family:system-ui,sans-serif}
.rlm-kicker{color:#8ed8ff;font-size:12px;letter-spacing:.08em;font-weight:700}
.rlm-card h2,.rlm-card h3{color:#edf6ff;margin:.35em 0;font-size:1.2rem}
.rlm-card p{color:#c0d1e0;margin:.5em 0;line-height:1.5}
.rlm-card a{display:block;color:#8ed8ff;padding:12px 0;min-height:24px}
.rlm-current{border-left:4px solid #39d3ae}
@media(max-width:600px){.rlm-card{padding:12px}.rlm-card h2{font-size:1.1rem}}
</style>"""


def access_allowed(env: Mapping[str, str], authorize: Callable[[], bool] | None = None) -> bool:
    """Never infer login from a query string or a client-provided profile."""
    if authorize is not None:
        try:
            return authorize() is True
        except Exception:
            return False
    return env.get(PREVIEW_FLAG) == "1"


def safe_snapshot(loader: Callable, *args) -> dict:
    """Keep provider exceptions, response bodies and secrets out of the UI."""
    try:
        payload = loader(*args)
        if not isinstance(payload, dict):
            raise ValueError("Invalid snapshot")
        return payload
    except Exception:
        return {"status": "UNKNOWN", "raw": [],
                "error": "Datos no disponibles. Revisa la configuración y los permisos del proveedor en el servidor."}


def card(kicker: str, title: str, detail: str = "", *, active: bool = False) -> str:
    css_class = "rlm-card rlm-current" if active else "rlm-card"
    return (f'<section class="{css_class}"><div class="rlm-kicker">{escape(kicker)}</div>'
            f'<h2>{escape(title)}</h2><p>{escape(detail)}</p></section>')


def countdown(seconds: int | None) -> str:
    if seconds is None:
        return "Sin bloque activo"
    minutes, remaining = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{remaining:02d} restantes"


def news_windows(session: dict) -> list[tuple[datetime, str]]:
    """Editorial windows, not evidence that a news broadcast actually ran."""
    if session.get("status") != "OPEN":
        return []
    try:
        start, end = live.aware(session["open"]), live.aware(session["close"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return []
    if start.date() != end.date() or start >= end:
        return []
    candidates = [(start - timedelta(minutes=15), "Pre-Market News"),
                  (datetime.combine(start.date(), time(12), live.ET), "Midday News"),
                  (end - timedelta(minutes=30), "Closing News")]
    return sorted((stamp, title) for stamp, title in candidates
                  if start - timedelta(minutes=15) <= stamp < end)


def compact_figure(figure):
    """Copy before adapting: desktop figures and their prices stay untouched."""
    import plotly.graph_objects as go
    result = go.Figure(figure)
    result.update_layout(height=420, autosize=True, showlegend=False,
                         margin={"l": 5, "r": 58, "t": 40, "b": 45},
                         title={"text": "Velas 15m · escenarios condicionales", "font": {"size": 14}})
    result.update_annotations(visible=False)
    if result.data and result.data[0].type == "candlestick":
        candle = result.data[0]
        count = len(candle.x)
        start = max(0, count - 45)
        ticks = sorted(set([start, (start + count - 1) // 2, count - 1]))
        result.update_xaxes(range=[max(-1, count - 45), count + 16], tickvals=ticks,
                            ticktext=[str(candle.text[i]).removesuffix(" ET") for i in ticks],
                            tickfont={"size": 10}, fixedrange=True)
        result.update_yaxes(fixedrange=True, tickfont={"size": 11}, automargin=True)
    return result


def render_mobile_live(*, authorize: Callable[[], bool] | None = None) -> None:
    import streamlit as st
    st.set_page_config(page_title="Roxy Live", page_icon="📡", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(card("ROXY TRADING · DESARROLLO", "Roxy Live", "Mercado · Programación · Noticias"),
                unsafe_allow_html=True)
    if not access_allowed(os.environ, authorize):
        st.info("Vista de desarrollo desactivada. El terminal existente no ha sido modificado. "
                "Falta conectar esta vista a su acceso autenticado o autorizar expresamente un preview público en el servidor.")
        return
    if authorize is None:
        st.caption("Preview público habilitado por configuración. No hereda el login del terminal.")
    symbol = st.selectbox("Activo", SYMBOLS, key="rlm_symbol")
    section = st.radio("Panel", ("Mercado", "Programación", "Noticias"), horizontal=True, key="rlm_section")
    compact = st.checkbox("Vista compacta para teléfono", value=True, key="rlm_compact")
    refresh = st.checkbox("Actualización automática", value=True, key="rlm_refresh")
    st.button("Actualizar vista", key="rlm_manual")
    st.caption("La actualización respeta la caché: velas 60 s, noticias 5 min y calendario 15 min.")
    feed = os.getenv("ALPACA_DATA_FEED", "iex").strip().lower()

    @st.cache_data(ttl=60, show_spinner=False)
    def bars_cache(ticker, source):
        return safe_snapshot(live.load_bars, ticker, source)

    @st.cache_data(ttl=300, show_spinner=False)
    def news_cache():
        return safe_snapshot(live.load_news)

    @st.cache_data(ttl=900, show_spinner=False)
    def session_cache(day):
        return safe_snapshot(live.load_session, day)

    def panel():
        # Fragment timers must not keep serving data after authorization fails.
        if not access_allowed(os.environ, authorize):
            st.warning("Acceso no autorizado. Vuelve al terminal para iniciar sesión.")
            return
        now = datetime.now(live.ET)
        session = session_cache(now.date())
        schedule = live.programme(now, session)
        current = schedule["current"]
        st.caption(f"{now:%d/%m/%Y · %H:%M:%S} ET · {schedule['state']}")
        st.markdown(card("BLOQUE ACTUAL", current["title"] if current else "Fuera de programación",
                         countdown(schedule["remaining"]), active=bool(current)), unsafe_allow_html=True)
        if schedule["next"]:
            nxt = schedule["next"]
            st.caption(f"Siguiente: {nxt['start']:%H:%M} ET · {nxt['title']}")
        if session.get("error"):
            st.warning(session["error"])
        if section == "Mercado":
            snapshot = bars_cache(symbol, feed)
            if snapshot.get("error"):
                st.warning(snapshot["error"])
            bars = live.normalize_bars(snapshot.get("raw", []), now)
            levels = live.scenario_levels(bars)
            if not bars:
                st.info("Sin velas disponibles. No se muestran precios ficticios.")
            else:
                figure = live.chart_figure(bars, symbol, levels)
                st.plotly_chart(compact_figure(figure) if compact else figure,
                                use_container_width=True, key="rlm_chart",
                                config={"displaylogo": False, "responsive": True, "scrollZoom": False,
                                        "displayModeBar": not compact})
                stamp = bars[-1]["t"]
                age = max(0, int((now - stamp).total_seconds() // 60))
                st.caption(f"{symbol} · Alpaca {feed.upper()} · Última vela inicia {stamp:%d/%m %H:%M} ET · hace {age} min.")
                if schedule["state"] == "Mercado abierto" and age > 30:
                    st.warning("Datos atrasados: esta gráfica no debe interpretarse como cotización actual.")
                if levels:
                    st.markdown(card("MAPA DE OBSERVACIÓN", levels["state"],
                                     f"Soporte {levels['support']:.2f} · Resistencia {levels['resistance']:.2f}"),
                                unsafe_allow_html=True)
                    st.caption("Línea verde: escenario alcista. Roja: bajista. Flechas hipotéticas, sin probabilidades ni rendimiento garantizado.")
                else:
                    st.info("Se necesitan 21 velas cerradas válidas para calcular los escenarios.")
            if feed == "iex":
                st.caption("IEX: cobertura parcial; el volumen no es el consolidado de todo el mercado.")
        elif section == "Programación":
            for row in schedule["rows"]:
                st.markdown(card(f"{row['start']:%H:%M}–{row['end']:%H:%M} ET", row["title"],
                                 row["detail"], active=row == current), unsafe_allow_html=True)
            if not schedule["rows"]:
                st.info(schedule["state"])
            st.subheader("Ventanas de noticias")
            for stamp, title in news_windows(session):
                st.write(f"{stamp:%H:%M} ET · {title}")
            st.caption("Agenda editorial prevista. No cambia escenas de OBS ni activa narración. El cierre se ajusta al calendario confirmado.")
        else:
            snapshot = news_cache()
            if snapshot.get("error"):
                st.warning(snapshot["error"])
            items = live.news_items(snapshot.get("raw", []), now)
            if not items:
                st.info("Sin noticias recientes con fuente y fecha disponibles.")
            for item in items:
                st.markdown(f'<article class="rlm-card"><div class="rlm-kicker">{escape(item["source"])} · '
                            f'{item["published"]:%d/%m %H:%M} ET</div><a href="{escape(item["url"], quote=True)}" '
                            f'target="_blank" rel="noopener noreferrer">{escape(item["title"])}</a></article>',
                            unsafe_allow_html=True)
        st.caption("Solo lectura. Sin órdenes, saldos o posiciones. Esta página no inicia transmisiones, voz ni publicaciones en redes.")

    fragment = getattr(st, "fragment", None)
    if callable(fragment):
        fragment(run_every=30 if refresh else None)(panel)()
    else:
        st.info("Actualización manual en esta versión de Streamlit.")
        panel()
