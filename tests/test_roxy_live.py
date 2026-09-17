"""Offline fixtures only; synthetic quotes never reach the production UI."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roxy_live as live


def moment(hour, minute=0):
    return datetime(2026, 9, 17, hour, minute, tzinfo=live.ET)


def session(close=16):
    return {"status": "OPEN", "open": moment(9, 30), "close": moment(close)}


@pytest.mark.parametrize("hour,minute,expected", [
    (9, 14, None), (9, 15, "prep"), (9, 30, "open"), (10, 30, "analysis"),
    (12, 0, "school"), (13, 30, "follow"), (15, 0, "power"),
    (15, 55, "recap"), (16, 0, "recap"), (16, 5, None),
])
def test_programme_boundaries(hour, minute, expected):
    result = live.programme(moment(hour, minute), session())
    assert (result["current"] or {}).get("id") == expected
    for first, second in zip(result["rows"], result["rows"][1:]):
        assert first["end"] <= second["start"]


def test_early_close():
    result = live.programme(moment(12, 55), session(13))
    assert result["current"]["id"] == "recap"
    assert result["rows"][-1]["end"] == moment(13, 5)
    assert not any(r["id"] == "power" for r in result["rows"])


@pytest.mark.parametrize("status", ["CLOSED", "UNKNOWN"])
def test_no_false_market_open(status):
    result = live.programme(moment(10), {"status": status})
    assert result["current"] is None and not result["rows"]
    assert result["state"] != "Mercado abierto"


@pytest.mark.parametrize("month,utc_hour", [(7, 13), (12, 14)])
def test_daylight_saving_time(month, utc_hour):
    start = datetime(2026, month, 17, 9, 30, tzinfo=live.ET)
    market = {"status": "OPEN", "open": start, "close": start.replace(hour=16, minute=0)}
    now = datetime(2026, month, 17, utc_hour, 30, tzinfo=timezone.utc)
    assert live.programme(now, market)["current"]["id"] == "open"


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        live.programme(datetime(2026, 9, 17, 10), session())


def fixture_bars(n=25):
    start = moment(9, 30) - timedelta(days=1)
    return [{"t": (start + timedelta(minutes=i * 15)).isoformat(),
             "o": 100 + i * .1, "h": 102 + i * .1,
             "l": 99 + i * .1, "c": 101 + i * .1, "v": 1000} for i in range(n)]


def test_bar_validation_and_deduplication():
    raw = fixture_bars(3)
    raw += [raw[0], {**raw[1], "o": float("nan")}, {**raw[1], "l": 999},
            {**raw[1], "v": -1}, {**raw[1], "t": moment(17).isoformat()}, {}]
    clean = live.normalize_bars(raw[::-1], moment(16))
    assert len(clean) == 3
    assert clean[0]["t"] < clean[-1]["t"]


def test_incomplete_bar_not_used_and_baseline_excludes_last_close():
    raw = fixture_bars(21)
    raw[-1].update(o=105, h=112, l=103, c=110)
    raw.append({"t": moment(15, 45).isoformat(), "o": 500, "h": 1000, "l": 400, "c": 800})
    bars = live.normalize_bars(raw, moment(15, 50))
    levels = live.scenario_levels(bars)
    assert not bars[-1]["complete"]
    assert levels["resistance"] < 110
    assert levels["state"] == "Último cierre por encima del rango"
    assert levels["baseline_end"] < levels["asof"]
    assert levels["up"][1] > levels["up"][0] > levels["resistance"]


def test_no_invented_levels():
    assert live.scenario_levels([]) is None
    assert live.scenario_levels(live.normalize_bars(fixture_bars(20), moment(16))) is None


def test_news_validation_and_deduplication():
    good = {"headline": "Company update", "source": "Company", "url": "https://example.com/a",
            "created_at": moment(14).isoformat()}
    raw = [good, dict(good), {**good, "headline": "old", "created_at": moment(14) - timedelta(days=3)},
           {**good, "headline": "javascript", "url": "javascript:alert(1)"},
           {**good, "headline": "missing", "source": ""},
           {**good, "headline": "future", "created_at": moment(18).isoformat()},
           {**good, "headline": "bad URL", "url": "https://["},
           {**good, "headline": "credentials", "url": "https://user:pass@example.com"}]
    assert len(live.news_items(raw, moment(16))) == 1


def test_request_is_get_only_and_fixed_host():
    calls = []
    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"bars": {}})
    env = {"ALPACA_API_KEY": "test-key", "ALPACA_API_SECRET": "test-secret"}
    live.alpaca_get("/v2/stocks/bars", {}, env=env, get=fake_get)
    assert calls[0][0].startswith("https://data.alpaca.markets/")
    assert calls[0][1]["timeout"] == (3.05, 10)
    assert calls[0][1]["allow_redirects"] is False
    with pytest.raises(ValueError):
        live.alpaca_get("/v2/orders", {}, env=env, get=fake_get)
    with pytest.raises(ValueError):
        live.alpaca_get("/v2/calendar", {}, calendar=True, env={**env, "ALPACA_BASE_URL": "https://example.com"}, get=fake_get)
    assert len(calls) == 1


def test_credentials_and_errors_do_not_leak_secrets():
    with pytest.raises(ValueError):
        live.credentials({})
    with pytest.raises(ValueError):
        live.credentials({"ALPACA_API_KEY": "TU_KEY_PAPER", "ALPACA_API_SECRET": "secret"})
    env = {"ALPACA_API_KEY": "private-key", "ALPACA_API_SECRET": "private-secret"}
    with pytest.raises(ValueError) as error:
        live.alpaca_get("/v2/stocks/bars", {}, env=env,
            get=lambda *a, **k: SimpleNamespace(status_code=403, json=lambda: {"secret": "private-secret"}))
    assert "private" not in str(error.value)
    assert "403" in str(error.value)


def test_loaders_use_verified_contracts(monkeypatch):
    calls = []
    def fake_api(path, params, **kwargs):
        calls.append((path, params))
        if "calendar" in path:
            return [{"date": "2026-09-17", "open": "09:30", "close": "13:00"}]
        return {"bars": {"NVDA": fixture_bars()}}
    monkeypatch.setattr(live, "alpaca_get", fake_api)
    assert live.load_session(moment(10).date())["close"] == moment(13)
    assert len(live.load_bars("NVDA", "iex", moment(16))["raw"]) == 25
    assert calls[-1][1]["sort"] == "desc" and calls[-1][1]["limit"] == 200
    with pytest.raises(ValueError):
        live.load_bars("SPX", "iex")


def test_chart_has_actual_candles_and_conditional_traces():
    bars = live.normalize_bars(fixture_bars(), moment(16))
    fig = live.chart_figure(bars, "NVDA", live.scenario_levels(bars))
    assert len(fig.data) == 3
    assert list(fig.data[0].close) == [bar["c"] for bar in bars]
    assert fig.data[1].line.dash == "dash"
    assert "NVDA" in fig.layout.title.text
    assert not live.chart_figure([], "NVDA", None).data


class StreamlitStub:
    def __init__(self):
        self.messages = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def columns(self, spec):
        return [self] * len(spec)
    def selectbox(self, name, options):
        return options[0]
    def checkbox(self, *args, **kwargs):
        return False
    def cache_data(self, *args, **kwargs):
        return lambda fn: fn
    fragment = cache_data
    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.messages.append((name, args, kwargs))
        return record


@pytest.mark.parametrize("with_data", [False, True])
def test_render_smoke_and_escape(monkeypatch, with_data):
    st = StreamlitStub()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(live, "load_session", lambda day: {"status": "UNKNOWN"})
    now = datetime.now(live.ET)
    raw = [{**row, "t": (now - timedelta(minutes=(25-i)*15)).isoformat()} for i, row in enumerate(fixture_bars())]
    monkeypatch.setattr(live, "load_bars", lambda *args: {"raw": raw if with_data else []})
    monkeypatch.setattr(live, "load_news", lambda: {"raw": [{"headline": "<script>bad</script>",
         "source": "Example", "url": "https://example.com/", "created_at": now.isoformat()}]})
    live.render_live()
    messages = " ".join(str(args) for _, args, _ in st.messages)
    assert "&lt;script&gt;" in messages and "<script>bad</script>" not in messages
    assert any(name == "plotly_chart" for name, _, _ in st.messages) == with_data
