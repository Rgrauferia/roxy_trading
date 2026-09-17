"""Read-only Roxy Live view. No orders, LLM calls or fabricated market data.

The domain helpers are intentionally independent of Streamlit so they can be
used by the existing terminal or tested without a running web server.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from html import escape
from math import isfinite
import os
import re
from typing import Any, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
SLOTS = (
    ("prep", 555, 570, "Roxy Market Prep", "Noticias, niveles importantes y watchlist."),
    ("open", 570, 630, "Apertura", "Seguimiento del inicio de la sesión."),
    ("analysis", 630, 720, "Análisis en vivo", "Explicar las condiciones de los escenarios."),
    ("school", 720, 810, "Educación y chat", "Preguntas, conceptos y desarrollo de Roxy."),
    ("follow", 810, 900, "Seguimiento", "Revisar señales y nuevas oportunidades."),
    ("power", 900, 960, "Power Hour", "Seguimiento de la última hora de mercado."),
)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La hora debe incluir zona horaria.")
    return value.astimezone(ET)


def parse_timestamp(value: Any) -> datetime | None:
    try:
        if isinstance(value, datetime):
            return aware(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value, UTC).astimezone(ET)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return aware(parsed)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def programme(now: datetime, session: Mapping[str, Any]) -> dict[str, Any]:
    """Use a verified trading session; never infer holidays from weekdays.

    session.status is OPEN, CLOSED or UNKNOWN; open/close are aware datetimes.
    The recap owns the overlap with Power Hour and follows early closes.
    """
    now = aware(now)
    status = session.get("status", "UNKNOWN")
    empty = {"rows": [], "current": None, "next": None, "remaining": None}
    if status == "CLOSED":
        return {**empty, "state": "Sin sesión de mercado hoy"}
    start, end = session.get("open"), session.get("close")
    if status != "OPEN" or not isinstance(start, datetime) or not isinstance(end, datetime):
        return {**empty, "state": "Calendario no confirmado"}
    start, end = aware(start), aware(end)
    if start.date() != now.date() or end.date() != now.date() or start >= end:
        return {**empty, "state": "Calendario no confirmado"}
    midnight = datetime.combine(now.date(), time(), ET)
    recap = end - timedelta(minutes=5)
    # Standard segments are shortened, not extended, on early-close days.
    rows = []
    for key, begin, finish, title, detail in SLOTS:
        a, b = midnight + timedelta(minutes=begin), midnight + timedelta(minutes=finish)
        if key == "prep":
            a, b = start - timedelta(minutes=15), start
        else:
            a, b = max(a, start), min(b, recap)
        if a < b:
            rows.append({"id": key, "start": a, "end": b, "title": title, "detail": detail})
    rows.append({"id": "recap", "start": recap, "end": end + timedelta(minutes=5),
                 "title": "Resumen del día", "detail": "Qué pasó y qué vigilar en la próxima sesión."})
    current = next((r for r in rows if r["start"] <= now < r["end"]), None)
    upcoming = next((r for r in rows if r["start"] > now), None)
    state = "Mercado abierto" if start <= now < end else "Fuera de la sesión regular"
    remaining = max(0, int((current["end"] - now).total_seconds())) if current else None
    return {"rows": rows, "current": current, "next": upcoming, "remaining": remaining, "state": state}


def normalize_bars(raw: list[dict], now: datetime, minutes: int = 15) -> list[dict]:
    """Validate OHLCV, reject future/non-finite prices, deduplicate and sort."""
    now = aware(now)
    by_time = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        stamp = parse_timestamp(row.get("t"))
        if stamp is None or stamp > now:
            continue
        try:
            values = {k: float(row[k]) for k in ("o", "h", "l", "c")}
            volume = float(row.get("v", 0))
        except (ValueError, TypeError, KeyError):
            continue
        if not all(isfinite(v) and v > 0 for v in values.values()):
            continue
        if not isfinite(volume) or volume < 0:
            continue
        if values["l"] > min(values["o"], values["c"]) or values["h"] < max(values["o"], values["c"]):
            continue
        by_time[stamp] = {**values, "v": volume, "t": stamp,
                          "complete": stamp + timedelta(minutes=minutes) <= now}
    return [by_time[t] for t in sorted(by_time)]


def scenario_levels(bars: list[dict]) -> dict | None:
    """Observation range from 20 bars BEFORE the latest completed bar.

    Distances use mean true range of the last 14 baseline bars, not a claim
    of predictive accuracy. No targets or probabilities are invented by AI.
    """
    closed = [b for b in bars if b.get("complete")]
    if len(closed) < 21:
        return None
    baseline = closed[-21:-1]
    support, resistance = min(b["l"] for b in baseline), max(b["h"] for b in baseline)
    ranges = []
    for previous, bar in zip(baseline, baseline[1:]):
        ranges.append(max(bar["h"] - bar["l"], abs(bar["h"] - previous["c"]), abs(bar["l"] - previous["c"])))
    atr = sum(ranges[-14:]) / 14
    if not (resistance > support > 0 and atr > 0 and support > 2 * atr):
        return None
    width = min(atr * 0.15, (resistance - support) * 0.15)
    last = closed[-1]
    state = "Dentro del rango"
    if last["c"] > resistance:
        state = "Último cierre por encima del rango"
    elif last["c"] < support:
        state = "Último cierre por debajo del rango"
    return {"support": support, "resistance": resistance, "width": width, "atr": atr,
            "up": [resistance + atr, resistance + 2 * atr],
            "down": [support - atr, support - 2 * atr], "state": state,
            "asof": last["t"], "baseline_end": baseline[-1]["t"]}


def news_items(raw: list[dict], now: datetime) -> list[dict]:
    """Only timestamped, sourced recent headlines; no HTML/news synthesis."""
    now = aware(now)
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("headline") or item.get("title") or "").strip()
        source = str(item.get("source") or "").strip()
        url = str(item.get("url") or item.get("link") or "").strip()
        stamp = parse_timestamp(item.get("created_at") or item.get("published"))
        try:
            parsed = urlsplit(url)
            valid_url = parsed.scheme in ("https", "http") and bool(parsed.hostname) and not parsed.username and not parsed.password
        except ValueError:
            valid_url = False
        key = re.sub(r"\s+", " ", title).casefold()
        if not title or not source or not valid_url or stamp is None or key in seen:
            continue
        if stamp > now + timedelta(minutes=2) or now - stamp > timedelta(hours=24):
            continue
        seen.add(key)
        out.append({"title": title[:300], "source": source[:100], "url": url, "published": stamp})
    return sorted(out, key=lambda i: i["published"], reverse=True)[:8]


def credentials(env: Mapping[str, str]) -> tuple[str, str]:
    key = env.get("ALPACA_API_KEY") or env.get("APCA_API_KEY_ID") or ""
    secret = env.get("ALPACA_API_SECRET") or env.get("ALPACA_SECRET_KEY") or env.get("APCA_API_SECRET_KEY") or ""
    if not key or not secret or any(v.startswith(("TU_", "YOUR_")) for v in (key, secret)):
        raise ValueError("Configura las credenciales Alpaca en el servidor; no se solicitan en esta pantalla.")
    return key, secret


def alpaca_get(path: str, params: dict, *, calendar: bool = False, env=None, get=None) -> Any:
    """Bounded GET-only adapter. Never forward credentials to arbitrary hosts."""
    import requests
    env = os.environ if env is None else env
    key, secret = credentials(env)
    host = "https://data.alpaca.markets"
    if calendar:
        host = (env.get("ALPACA_BASE_URL") or "https://paper-api.alpaca.markets").rstrip("/")
        if host not in ("https://paper-api.alpaca.markets", "https://api.alpaca.markets"):
            raise ValueError("ALPACA_BASE_URL debe ser un servidor oficial de Alpaca.")
    if path not in ("/v2/stocks/bars", "/v1beta1/news", "/v2/calendar"):
        raise ValueError("Endpoint no permitido en la vista de solo lectura.")
    call = requests.get if get is None else get
    try:
        response = call(host + path, params=params, headers={"APCA-API-KEY-ID": key,
                        "APCA-API-SECRET-KEY": secret}, timeout=(3.05, 10), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError(f"Alpaca respondió HTTP {response.status_code}. Revisa permisos y feed del servidor.")
        return response.json()
    except (requests.RequestException, ValueError) as error:
        if isinstance(error, ValueError) and str(error).startswith("Alpaca respondió"):
            raise
        # Never expose request objects, authorization headers or response bodies.
        raise ValueError("No fue posible leer la respuesta de Alpaca.") from None


def load_session(day: date) -> dict:
    payload = alpaca_get("/v2/calendar", {"start": day.isoformat(), "end": day.isoformat()}, calendar=True)
    if not isinstance(payload, list):
        raise ValueError("Calendario de mercado inválido.")
    if not payload:
        return {"status": "CLOSED"}
    for row in payload:
        if not isinstance(row, dict):
            continue
        if row.get("date") == day.isoformat():
            try:
                start = datetime.combine(day, time.fromisoformat(row["open"]), ET)
                end = datetime.combine(day, time.fromisoformat(row["close"]), ET)
                if start >= end:
                    break
                return {"status": "OPEN", "open": start, "close": end}
            except (KeyError, ValueError, TypeError):
                break
    raise ValueError("No se pudo validar la sesión solicitada.")


def load_bars(symbol: str, feed: str, now: datetime | None = None) -> dict:
    now = datetime.now(UTC) if now is None else now
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol) or symbol in ("SPX", "VIX"):
        raise ValueError("Usa un ticker de acción o ETF compatible. SPX no es SPY y no se sustituye automáticamente.")
    if feed not in ("iex", "sip"):
        raise ValueError("ALPACA_DATA_FEED debe ser iex o sip; se respetan los permisos de tu plan.")
    payload = alpaca_get("/v2/stocks/bars", {"symbols": symbol, "timeframe": "15Min",
        "start": (now - timedelta(days=10)).isoformat(), "sort": "desc",
        "limit": 200, "feed": feed, "adjustment": "raw"})
    if not isinstance(payload, dict) or not isinstance(payload.get("bars"), dict):
        raise ValueError("Respuesta de velas inválida.")
    # Intentionally the most recent 200 bars, not a claim of complete history.
    raw = payload["bars"].get(symbol) or []
    if not isinstance(raw, list):
        raise ValueError("Respuesta de velas inválida.")
    return {"raw": raw, "fetched_at": now, "feed": feed}


def load_news() -> dict:
    now = datetime.now(UTC)
    payload = alpaca_get("/v1beta1/news", {"start": (now - timedelta(hours=24)).isoformat(),
        "limit": 40, "sort": "desc", "include_content": "false"})
    if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
        raise ValueError("Respuesta de noticias inválida.")
    return {"raw": payload["news"], "fetched_at": now}


def chart_figure(bars: list[dict], symbol: str, levels: dict | None):
    import plotly.graph_objects as go
    fig = go.Figure()
    if not bars:
        return fig
    count = len(bars)
    fig.add_trace(go.Candlestick(x=list(range(count)), open=[b["o"] for b in bars],
        high=[b["h"] for b in bars], low=[b["l"] for b in bars], close=[b["c"] for b in bars],
        text=[b["t"].strftime("%d/%m %H:%M ET") for b in bars], name=f"{symbol} · 15m",
        increasing_line_color="#36d9a0", decreasing_line_color="#ef6375"))
    if levels:
        s, r, w = levels["support"], levels["resistance"], levels["width"]
        fig.add_hrect(y0=s, y1=s + w, fillcolor="#429aff", opacity=0.20, line_width=0)
        fig.add_hrect(y0=r - w, y1=r, fillcolor="#eec465", opacity=0.20, line_width=0)
        fig.add_hline(y=s, line_dash="dash", line_color="#429aff", annotation_text=f"Soporte {s:.2f}")
        fig.add_hline(y=r, line_dash="dash", line_color="#eec465", annotation_text=f"Resistencia {r:.2f}")
        xs = [count, count + 4, count + 6, count + 12]
        for label, ys, color in (
            ("Alcista · si recupera y sostiene", [r, levels["up"][0], r + levels["atr"] * .65, levels["up"][1]], "#36d9a0"),
            ("Bajista · si pierde y confirma", [s, levels["down"][0], s - levels["atr"] * .65, levels["down"][1]], "#ef6375"),
        ):
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=label,
                line={"color": color, "dash": "dash", "width": 2},
                hovertemplate="Trayectoria hipotética, no una predicción<extra></extra>"))
            fig.add_annotation(x=xs[-1], y=ys[-1], text="Escenario condicional", showarrow=True,
                arrowhead=2, ax=-65, ay=35 if color == "#36d9a0" else -35, font={"color": color, "size": 11})
        fig.add_annotation(x=count + 4, y=(s + r) / 2, text="NEUTRAL<br>Dentro del rango", showarrow=False,
                           font={"color": "#eec465", "size": 11})
    ticks = list(range(0, count, max(1, count // 7)))
    fig.update_layout(template="plotly_dark", paper_bgcolor="#071421", plot_bgcolor="#071421",
        height=520, margin={"l": 15, "r": 25, "t": 35, "b": 35},
        title={"text": f"{escape(symbol)} | ESCENARIOS DEL DÍA", "font": {"size": 19}},
        xaxis={"rangeslider": {"visible": False}, "range": [max(-1, count - 85), count + 16],
               "tickvals": ticks, "ticktext": [bars[i]["t"].strftime("%d/%m %H:%M") for i in ticks]},
        yaxis={"side": "right", "fixedrange": False},
        legend={"orientation": "h", "y": -0.13}, uirevision=f"roxy-live-{symbol}")
    return fig


def render_live() -> None:
    """Streamlit integration; imported only when the new page is selected."""
    import streamlit as st
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    st.set_page_config(page_title="Roxy Trading Live", page_icon="📡", layout="wide")
    st.markdown("""<style>
    .stApp {background:#030b15;color:#ecf5ff}
    .block-container {padding-top:1.4rem;max-width:1800px}
    .rl-card {background:#091a2b;border:1px solid #164362;border-radius:12px;padding:16px;margin:8px 0}
    .rl-kicker {color:#69caff;font-size:12px;letter-spacing:1.5px;font-weight:700}
    .rl-muted {color:#9cafc3;font-size:13px}
    .rl-current {border-left:3px solid #39d3ae;background:#103329}
    .rl-row {padding:9px;border-bottom:1px solid #173149;font-size:13px}
    .rl-row b {color:#eaf4ff}.rl-time {color:#74caff;margin-right:12px}
    a {color:#74caff}
    </style>""", unsafe_allow_html=True)
    st.markdown('<div class="rl-kicker">ROXY TRADING · MARKET OPEN TO CLOSE</div>', unsafe_allow_html=True)
    st.title("Roxy Live")
    controls = st.columns([2, 2, 3])
    with controls[0]:
        symbol = st.selectbox("Gráfica principal", ["NVDA", "SPY", "QQQ", "TSLA", "AAPL", "MSFT", "AMZN"])
    with controls[1]:
        refresh = st.checkbox("Actualizar automáticamente", value=True)
    with controls[2]:
        st.caption("Solo lectura · No envía órdenes · Vista pública sin datos de tu cuenta")
    feed = os.getenv("ALPACA_DATA_FEED", "iex").lower().strip()

    # Separate TTLs bound the request budget. No provider request on a timer
    # faster than its cache; failures also become visible cached snapshots.
    @st.cache_data(ttl=60, show_spinner=False)
    def bars_cache(ticker, source):
        try:
            return load_bars(ticker, source)
        except ValueError as error:
            return {"raw": [], "error": str(error)}

    @st.cache_data(ttl=300, show_spinner=False)
    def news_cache():
        try:
            return load_news()
        except ValueError as error:
            return {"raw": [], "error": str(error)}

    @st.cache_data(ttl=900, show_spinner=False)
    def session_cache(day):
        try:
            return load_session(day)
        except ValueError as error:
            return {"status": "UNKNOWN", "error": str(error)}

    def panel():
        now = datetime.now(ET)
        session = session_cache(now.date())
        schedule = programme(now, session)
        st.caption(f"{now:%d/%m/%Y · %H:%M:%S} ET · {schedule['state']}")
        left, center, right = st.columns([1, 4, 1.4])
        with left:
            st.markdown('<div class="rl-card"><div class="rl-kicker">ROXY</div><h2>Observar.<br>Explicar.<br>Esperar.</h2><p class="rl-muted">Escenarios condicionales; no promesas de rendimiento.</p></div>', unsafe_allow_html=True)
            st.caption("Voz y chat: conserva tus controles del terminal actual. No se han conectado a esta vista todavía.")
            st.caption("Contexto de la gráfica: velas 15m. No se afirma confirmación 1H/1m.")
        snapshot = bars_cache(symbol, feed)
        bars = normalize_bars(snapshot.get("raw", []), now)
        levels = scenario_levels(bars)
        with center:
            if snapshot.get("error"):
                st.warning(snapshot["error"])
            if bars:
                st.plotly_chart(chart_figure(bars, symbol, levels), use_container_width=True,
                                config={"displaylogo": False}, key="roxy_live_main_chart")
                latest = bars[-1]
                age = max(0, int((now - latest["t"]).total_seconds() // 60))
                st.caption(f"Alpaca · {feed.upper()} · Última vela inicia {latest['t']:%d/%m %H:%M} ET · hace {age} min. Incluye horario extendido disponible.")
                if feed == "iex":
                    st.caption("IEX: cobertura parcial, no representa el volumen consolidado del mercado.")
                if schedule["state"] == "Mercado abierto" and age > 30:
                    st.warning("Datos atrasados: no interpretar esta gráfica como cotización actual.")
                if not levels:
                    st.info("Se requieren al menos 21 velas cerradas válidas para calcular los escenarios.")
            else:
                st.info("Sin velas disponibles. No se dibujan precios de ejemplo.")
        with right:
            current = schedule["current"]
            title = current["title"] if current else "Fuera de programación"
            st.markdown(f'<div class="rl-card"><div class="rl-kicker">BLOQUE ACTUAL</div><h3>{escape(title)}</h3></div>', unsafe_allow_html=True)
            if current:
                seconds = schedule["remaining"]
                st.caption(f"Termina en {seconds // 60:02d}:{seconds % 60:02d}")
            if schedule["next"]:
                nxt = schedule["next"]
                st.caption(f"Siguiente: {nxt['start']:%H:%M} · {nxt['title']}")
            st.markdown("**Mapa de observación**")
            if levels:
                st.write(levels["state"])
                st.caption(f"Soporte: {levels['support']:.2f} · Resistencia: {levels['resistance']:.2f}")
                st.caption("Niveles de las 20 velas anteriores. Flechas: distancias de 1×/2× rango verdadero medio, no objetivos garantizados.")
            else:
                st.caption("A la espera de datos suficientes.")
        agenda, news = st.columns([1.15, 1])
        with agenda:
            st.subheader("Programación del live")
            if session.get("error"):
                st.warning(session["error"])
            if not schedule["rows"]:
                st.info(schedule["state"])
            for row in schedule["rows"]:
                active = " rl-current" if schedule["current"] == row else ""
                st.markdown(f'<div class="rl-row{active}"><span class="rl-time">{row["start"]:%H:%M}–{row["end"]:%H:%M}</span><b>{escape(row["title"])}</b><br><span class="rl-muted">{escape(row["detail"])}</span></div>', unsafe_allow_html=True)
            st.caption("Hora de Nueva York. El resumen tiene prioridad desde cinco minutos antes del cierre; el calendario contempla cierres anticipados.")
        with news:
            st.subheader("Roxy Market News")
            headlines = news_cache()
            if headlines.get("error"):
                st.warning(headlines["error"])
            items = news_items(headlines.get("raw", []), now)
            if not items:
                st.info("Sin titulares recientes con fuente y fecha disponibles.")
            for item in items[:5]:
                st.markdown(f'<div class="rl-row"><a href="{escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{escape(item["title"])}</a><br><span class="rl-muted">{escape(item["source"])} · {item["published"]:%d/%m %H:%M} ET</span></div>', unsafe_allow_html=True)
            st.caption("Titulares del proveedor, sin reescribir ni atribuir causalidad. Se descartan duplicados y noticias sin fecha/fuente.")
        st.caption("Vista para transmisión; no certifica que OBS esté emitiendo. Verifica tus derechos de redistribución de datos y noticias antes de emitirlos públicamente.")

    fragment = getattr(st, "fragment", None)
    if fragment is not None:
        fragment(run_every=15 if refresh else None)(panel)()
    else:
        st.info("Esta versión de Streamlit usa actualización manual.")
        st.button("Actualizar vista")
        panel()
