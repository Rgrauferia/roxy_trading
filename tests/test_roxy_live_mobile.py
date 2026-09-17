"""Offline unit/renderer tests; no network, real account or orders."""
from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roxy_live as live
import roxy_live_mobile as mobile


@pytest.mark.parametrize("value", [None, "0", "true", "yes", " 1", "1 ", ""])
def test_public_preview_is_off_unless_explicit(value):
    env = {} if value is None else {mobile.PREVIEW_FLAG: value}
    assert mobile.access_allowed(env) is False


def test_host_authorization_takes_precedence_and_fails_closed():
    public = {mobile.PREVIEW_FLAG: "1"}
    assert mobile.access_allowed(public)
    assert not mobile.access_allowed(public, lambda: False)
    assert not mobile.access_allowed(public, lambda: "true")
    assert mobile.access_allowed({}, lambda: True)
    def broken():
        raise RuntimeError("private-token")
    assert not mobile.access_allowed(public, broken)


def test_error_details_do_not_reach_ui():
    def broken():
        raise RuntimeError("key=TOP_SECRET, server response body")
    result = mobile.safe_snapshot(broken)
    assert "TOP_SECRET" not in str(result)
    assert result["raw"] == [] and result["status"] == "UNKNOWN"
    assert mobile.safe_snapshot(lambda: []) == result
    assert mobile.safe_snapshot(lambda: {"raw": []}) == {"raw": []}


@pytest.mark.parametrize("value,expected", [(None, "Sin bloque activo"), (61, "01:01 restantes"),
                                           (-5, "00:00 restantes"), (3600, "60:00 restantes")])
def test_countdown(value, expected):
    assert mobile.countdown(value) == expected


def market(close=16):
    start = datetime(2026, 9, 17, 9, 30, tzinfo=live.ET)
    return {"status": "OPEN", "open": start, "close": start.replace(hour=close, minute=0)}


@pytest.mark.parametrize("close,expected", [(16, ["09:15", "12:00", "15:30"]),
                                           (13, ["09:15", "12:00", "12:30"])])
def test_news_windows_follow_confirmed_close(close, expected):
    assert [t.strftime("%H:%M") for t, _ in mobile.news_windows(market(close))] == expected


@pytest.mark.parametrize("session", [{}, {"status": "CLOSED"}, {"status": "UNKNOWN"},
                                      {"status": "OPEN", "open": "bad", "close": None}])
def test_news_windows_do_not_invent_a_session(session):
    assert mobile.news_windows(session) == []


def test_cards_escape_content_and_have_scoped_mobile_css():
    html = mobile.card("<script>", '<img src=x onerror="alert(1)">', "A & B", active=True)
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and "A &amp; B" in html
    assert "rlm-current" in html
    assert "max-width:600px" in mobile.CSS
    assert ".stApp" not in mobile.CSS and ".block-container" not in mobile.CSS


def bars():
    now = datetime.now(live.ET)
    return [{"t": (now - timedelta(minutes=(30-i)*15)).isoformat(),
             "o": 100, "h": 102, "l": 99, "c": 101, "v": 200} for i in range(25)]


def test_compact_chart_does_not_mutate_desktop_or_prices():
    clean = live.normalize_bars(bars(), datetime.now(live.ET))
    original = live.chart_figure(clean, "TEST", live.scenario_levels(clean))
    before = original.to_json()
    compact = mobile.compact_figure(original)
    assert original.to_json() == before
    assert list(compact.data[0].close) == list(original.data[0].close)
    assert compact.layout.height == 420
    assert compact.layout.showlegend is False
    assert compact.layout.xaxis.fixedrange is True
    assert compact.layout.yaxis.fixedrange is True
    assert len(compact.layout.xaxis.tickvals) <= 3


class UIStub:
    def __init__(self, section="Mercado", *, timed=True):
        self.section, self.messages, self.callbacks, self.intervals = section, [], [], []
        if not timed:
            self.fragment = None
    def selectbox(self, label, options, **kwargs):
        return options[0]
    def radio(self, *args, **kwargs):
        return self.section
    def checkbox(self, *args, **kwargs):
        return kwargs.get("value", False)
    def cache_data(self, **kwargs):
        return lambda fn: fn
    def fragment(self, **kwargs):
        self.intervals.append(kwargs["run_every"])
        def decorate(fn):
            self.callbacks.append(fn)
            return fn
        return decorate
    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.messages.append((name, args, kwargs))
        return record


def install(monkeypatch, section="Mercado", *, timed=True, with_data=True):
    st = UIStub(section, timed=timed)
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setenv(mobile.PREVIEW_FLAG, "1")
    calls = []
    def load_session(day):
        calls.append("session")
        return {"status": "UNKNOWN"}
    def load_bars(*args):
        calls.append("bars")
        return {"raw": bars() if with_data else []}
    def load_news():
        calls.append("news")
        return {"raw": [{"headline": "<script>TEST</script>", "source": "Test fixture",
                         "url": "https://example.com", "created_at": datetime.now(live.ET).isoformat()}]}
    monkeypatch.setattr(live, "load_session", load_session)
    monkeypatch.setattr(live, "load_bars", load_bars)
    monkeypatch.setattr(live, "load_news", load_news)
    return st, calls


@pytest.mark.parametrize("section,expected", [("Mercado", ["session", "bars"]),
                                              ("Programación", ["session"]),
                                              ("Noticias", ["session", "news"])])
def test_only_selected_panel_fetches_data(monkeypatch, section, expected):
    st, calls = install(monkeypatch, section)
    mobile.render_mobile_live()
    assert calls == expected
    assert st.intervals == [30]
    text = str(st.messages)
    assert "<script>TEST</script>" not in text
    if section == "Noticias":
        assert "&lt;script&gt;TEST&lt;/script&gt;" in text
    if section == "Mercado":
        chart = next(kwargs for name, _, kwargs in st.messages if name == "plotly_chart")
        assert chart["config"]["scrollZoom"] is False


def test_disabled_preview_does_not_call_any_provider(monkeypatch):
    st, calls = install(monkeypatch)
    monkeypatch.delenv(mobile.PREVIEW_FLAG)
    mobile.render_mobile_live()
    assert calls == [] and not st.callbacks


def test_revoked_auth_blocks_timer_and_cached_data(monkeypatch):
    st, calls = install(monkeypatch)
    auth = {"allowed": True}
    mobile.render_mobile_live(authorize=lambda: auth["allowed"])
    calls.clear()
    auth["allowed"] = False
    st.callbacks[0]()
    assert calls == []
    assert any(name == "warning" and "Acceso no autorizado" in args[0]
               for name, args, _ in st.messages)


def test_no_data_and_manual_fallback(monkeypatch):
    st, _ = install(monkeypatch, timed=False, with_data=False)
    mobile.render_mobile_live()
    assert not any(name == "plotly_chart" for name, _, _ in st.messages)
    assert "No se muestran precios ficticios" in str(st.messages)
    assert "Actualización manual" in str(st.messages)


def test_entrypoint_uses_additive_renderer_not_terminal():
    source = (Path(__file__).resolve().parents[1] / "pages/1_Roxy_Live.py").read_text()
    assert "from roxy_live_mobile import render_mobile_live" in source
    assert "import streamlit_app" not in source
    assert "render_mobile_live()" in source
