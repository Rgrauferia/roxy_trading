import json

import pandas as pd

import streamlit_app
from ma_backtester import MovingAverageBacktestConfig
from roxy_trader.backtests import BacktestStore, run_moving_average_backtest


def candles(count=260):
    closes = [100 + index * 0.25 for index in range(count)]
    return pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=count, freq="h", tz="UTC"),
            "open": closes,
            "high": [value * 1.01 for value in closes],
            "low": [value * 0.99 for value in closes],
            "close": closes,
            "volume": [1000] * count,
        }
    )


def test_real_backtest_record_preserves_provenance_and_versions():
    record = run_moving_average_backtest(
        candles(),
        symbol="AAPL",
        market="stock",
        timeframe="1h",
        source_metadata={"provider": "Alpaca", "source": "alpaca_bars", "mode": "BROKER_DATA"},
        backtest_config=MovingAverageBacktestConfig(warmup=200),
    )

    assert record["status"] in {"COMPLETED", "NO_TRADES"}
    assert record["row_count"] == 260
    assert record["source"]["provider"] == "Alpaca"
    assert record["first_candle"] < record["last_candle"]
    assert record["engine_version"].startswith("roxy-ma-backtest/")
    assert record["strategy_version"].startswith("sma-")
    assert len(record["input_contract_hash"]) == 64
    assert record["validation"]["status"] == "DATA_INSUFFICIENT"


def test_backtest_rejects_invalid_or_insufficient_candles_without_simulation():
    record = run_moving_average_backtest(
        candles(50),
        symbol="AAPL",
        market="stock",
        timeframe="15m",
        source_metadata={"provider": "yfinance", "fallback": True},
    )

    assert record["status"] == "DATA_INSUFFICIENT"
    assert record["metrics"] == {}
    assert "Se requieren" in record["reason"]
    assert record["source"]["is_delayed"] is True


def test_store_is_user_scoped_atomic_json_and_bounded(tmp_path):
    store = BacktestStore(tmp_path / "backtests.json", max_runs_per_user=2)
    for index in range(3):
        store.save(
            "Roberto",
            {
                "id": str(index),
                "symbol": "AAPL" if index != 1 else "MSFT",
                "market": "stock",
                "timeframe": "1h",
                "run_at": f"2026-01-0{index + 1}T00:00:00Z",
                "metric": float("inf"),
            },
        )

    assert [run["id"] for run in store.list_runs("Roberto")] == ["2", "1"]
    assert store.latest("Roberto", symbol="AAPL", market="stock")["id"] == "2"
    assert store.list_runs("Another user") == []
    payload = json.loads((tmp_path / "backtests.json").read_text())
    assert payload["users"]["roberto"]["runs"][0]["metric"] is None


def test_input_contract_hash_is_deterministic_and_sensitive_to_contract():
    frame = candles(500)
    kwargs = {
        "symbol": "AAPL",
        "market": "stock",
        "timeframe": "1h",
        "source_metadata": {"provider": "Alpaca"},
    }

    first = run_moving_average_backtest(frame, **kwargs)
    repeated = run_moving_average_backtest(frame.copy(), **kwargs)
    changed_timeframe = run_moving_average_backtest(frame, **{**kwargs, "timeframe": "15m"})
    changed_frame = frame.copy()
    changed_frame.loc[499, "close"] += 1.0
    changed_data = run_moving_average_backtest(changed_frame, **kwargs)

    assert first["id"] != repeated["id"]
    assert first["input_contract_hash"] == repeated["input_contract_hash"]
    assert changed_timeframe["input_contract_hash"] != first["input_contract_hash"]
    assert changed_data["input_contract_hash"] != first["input_contract_hash"]


def test_long_run_exposes_anchored_out_of_sample_validation():
    record = run_moving_average_backtest(
        candles(500),
        symbol="BTC/USD",
        market="crypto",
        timeframe="15m",
        source_metadata={"provider": "BinanceUS", "is_realtime": True},
    )

    validation = record["validation"]
    assert validation["status"] == "AVAILABLE"
    assert validation["method"] == "anchored_time_split_no_refit"
    assert validation["split_ratio"] == 0.70
    assert validation["split_index"] == 350
    assert validation["in_sample"]["bars"] >= 30
    assert validation["out_of_sample"]["bars"] >= 30
    assert "generalization_gap_return_pct" in validation
    assert validation["cross_boundary_trades_excluded"] >= 0


def test_backtest_route_avoids_unrelated_full_market_context_and_live_fragment():
    source = open("streamlit_app.py", encoding="utf-8").read()
    app_source = source[source.index("def show_focused_roxy_app") : source.index("def main()")]
    lightweight = app_source.index('if selected_page == "Backtest":')
    full_context = app_source.index("context = load_focused_live_context()")

    assert lightweight < full_context
    route_block = app_source[lightweight:full_context]
    assert 'read_summary_json("alerts/roxy_ai_brief.json")' in route_block
    assert "render_focused_page_content(minimal_context, selected_page)" in route_block
    assert route_block.rstrip().endswith("return")


def test_backtest_surfaces_use_plotly_without_empty_vega_extent_contracts():
    source = open("streamlit_app.py", encoding="utf-8").read()
    legacy = source[
        source.index("def render_backtest_plotly_figure") : source.index("def roxy_backtest_store")
    ]
    durable = source[
        source.index("def render_backtest_run") : source.index("def show_backtest_screen")
    ]

    assert "go.Figure" in legacy
    assert "render_backtest_plotly_figure" in legacy
    assert "render_backtest_equity_chart" in durable
    assert "alt.Chart" not in legacy
    assert "alt.Chart" not in durable
    assert "st.dataframe" in legacy
    assert "st.dataframe" in durable


def test_backtest_legacy_charts_are_deferred_until_explicitly_requested():
    source = open("streamlit_app.py", encoding="utf-8").read()
    screen = source[source.index("def show_backtest_screen") : source.index("def cached_paper_result_closer_run")]

    toggle = screen.index('st.toggle(\n            "Cargar comparación histórica legacy"')
    conditional = screen.index("if load_legacy_backtest_charts:")
    strategy = screen.index("render_backtest_strategy_visual()")
    serious = screen.index("render_serious_backtest_performance()")

    assert toggle < conditional < strategy < serious
    assert 'value=False' in screen[toggle:conditional]
    assert "No cargado" in screen


def test_backtest_equity_runtime_escapes_payload_and_vendor_breakouts():
    markup = streamlit_app.roxy_backtest_equity_runtime_markup(
        payload={"symbol": "</script><script>alert('equity')</script>", "source": "A&B\u2028C"},
        lightweight_inline_source="window.safe=true;</script><script>alert('vendor')",
    )

    assert "__ROXY_BACKTEST_EQUITY_PAYLOAD__" not in markup
    assert "__LIGHTWEIGHT_INLINE__" not in markup
    assert "</script><script>alert('equity')</script>" not in markup
    assert "</script><script>alert('vendor')" not in markup
    assert "A\\u0026B\\u2028C" in markup
    assert "LightweightCharts.createChart" in markup


def test_backtest_equity_chart_normalizes_and_bounds_browser_payload(monkeypatch):
    captured = {}
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=1_500, freq="h", tz="UTC"),
            "equity": [10_000 + index for index in range(1_500)],
        }
    )

    def fake_markup(*, payload, lightweight_inline_source):
        captured["payload"] = payload
        captured["vendor"] = lightweight_inline_source
        return "<div>equity</div>"

    monkeypatch.setattr(streamlit_app, "roxy_backtest_equity_runtime_markup", fake_markup)
    monkeypatch.setattr(streamlit_app, "roxy_vendor_js_source", lambda filename: "vendor")
    monkeypatch.setattr(streamlit_app.components, "html", lambda markup, **kwargs: captured.update({"html": markup, **kwargs}))

    rendered = streamlit_app.render_backtest_equity_chart(
        frame,
        {
            "symbol": "BTC/USD",
            "timeframe": "1h",
            "engine_version": "engine-test",
            "source": {"provider": "BinanceUS"},
        },
    )

    points = captured["payload"]["points"]
    assert rendered is True
    assert len(points) <= 1_201
    assert points[0]["value"] == 10_000
    assert points[-1]["value"] == 11_499
    assert captured["payload"]["source"] == "BinanceUS"
    assert captured["vendor"] == "vendor"
    assert captured["height"] == 310
