import pandas as pd
import pytest
from datetime import datetime, timezone
from pathlib import Path

import streamlit_app
from streamlit_app import clean_roxy_operational_chart_df, roxy_actions_pro_chart_payload


SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")
LIVING_SOURCE = Path("living_market.py").read_text(encoding="utf-8")
LIVE_CHART_TEMPLATE = Path("assets/runtime/roxy_live_candle_chart.html").read_text(encoding="utf-8")
STOCK_LIVE_RUNTIME_TEMPLATE = Path("assets/runtime/roxy_stock_live_runtime.js.html").read_text(encoding="utf-8")
STOCK_SERVER_REFRESH_TEMPLATE = Path("assets/runtime/roxy_stock_server_refresh.js.html").read_text(encoding="utf-8")
ACTIONS_PRO_CHART_TEMPLATE = Path("assets/runtime/roxy_actions_pro_chart.html").read_text(encoding="utf-8")
ACTIONS_REFERENCE_TERMINAL_TEMPLATE = Path(
    "assets/runtime/roxy_actions_reference_terminal.html"
).read_text(encoding="utf-8")
FRONTEND_RUNTIME_SOURCE = SOURCE + STOCK_LIVE_RUNTIME_TEMPLATE


def _sample_chart_frame() -> pd.DataFrame:
    rows = []
    base = pd.Timestamp("2026-07-01 09:30", tz="UTC")
    price = 100.0
    for index in range(44):
        open_price = price + (index % 4) * 0.05
        close_price = open_price + (0.25 if index % 3 else -0.12)
        rows.append(
            {
                "ts": base + pd.to_timedelta(15 * index, unit="m"),
                "open": open_price,
                "high": max(open_price, close_price) + 0.45,
                "low": min(open_price, close_price) - 0.35,
                "close": close_price,
                "volume": 1000 + index * 20,
                "ema9": close_price - 0.2,
                "ema21": close_price - 0.5,
                "sma20": close_price - 0.4,
                "sma40": close_price - 0.8,
                "bb_upper": close_price + 2.0,
                "bb_lower": close_price - 2.0,
            }
        )
        price = close_price
    rows.insert(
        22,
        {
            "ts": base + pd.to_timedelta(15 * 22 * 60 + 1, unit="s"),
            "open": 100.0,
            "high": 165.0,
            "low": 40.0,
            "close": 161.0,
            "volume": 999999,
            "ema9": 100.0,
            "ema21": 100.0,
            "sma20": 100.0,
            "sma40": 100.0,
            "bb_upper": 103.0,
            "bb_lower": 97.0,
        },
    )
    return pd.DataFrame(rows)


def _strategy_chart_frame(periods: int, freq: str, start: float = 100.0) -> pd.DataFrame:
    rows = []
    for index, ts in enumerate(pd.date_range("2026-06-01", periods=periods, freq=freq, tz="UTC")):
        base = start + index * 0.18
        close = base + (0.14 if index % 4 else -0.04)
        rows.append(
            {
                "ts": ts,
                "open": base,
                "high": max(base, close) + 0.22,
                "low": min(base, close) - 0.18,
                "close": close,
                "volume": 1000 + index * 11,
            }
        )
    return pd.DataFrame(rows)


def test_crypto_horizon_enrichment_is_bounded_and_reuses_embedded_signals(monkeypatch):
    calls = []

    def fake_signal(symbol, horizon):
        calls.append((symbol, horizon))
        return {
            "price": 100.0,
            "entry_price": 100.0,
            "target_price": 102.0,
            "virtual_stop": 99.0,
            "action": "Vigilar",
            "decision_state": "ESPERAR CONFIRMACION",
            "decision_class": "watch",
            "strength": 60,
            "source": "exchange-test",
        }

    monkeypatch.setattr(streamlit_app, "roxy_crypto_horizon_signal", fake_signal)
    rows = [{"symbol": symbol, "market": "crypto"} for symbol in ("BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD")]

    enriched = streamlit_app.roxy_enrich_crypto_rows_for_horizon(rows, horizon="20m", limit=3)

    assert len(enriched) == 3
    assert len(calls) == 3
    assert all(row["roxy_signal"]["source"] == "exchange-test" for row in enriched)
    assert all(row["roxy_plan_source"] == "exchange-test" for row in enriched)


def test_crypto_horizon_enrichment_uses_provider_fail_fast_without_threads():
    source = SOURCE[
        SOURCE.index("def roxy_enrich_crypto_rows_for_horizon") : SOURCE.index("def roxy_crypto_module_detail_panel_html")
    ]

    assert "provider_unavailable = False" in source
    assert 'text_display(signal.get("source")) == "sin_velas_crypto"' in source
    assert "ThreadPoolExecutor" not in source


def test_crypto_horizon_enrichment_stops_repeating_provider_timeout(monkeypatch):
    calls = []

    def unavailable(symbol, horizon):
        calls.append((symbol, horizon))
        return {"symbol": symbol, "source": "sin_velas_crypto", "action": "Sin datos live"}

    monkeypatch.setattr(streamlit_app, "roxy_crypto_horizon_signal", unavailable)
    rows = [{"symbol": symbol, "market": "crypto"} for symbol in ("BTC/USD", "ETH/USD", "SOL/USD")]

    enriched = streamlit_app.roxy_enrich_crypto_rows_for_horizon(rows, horizon="daily-provider-down", limit=3)

    assert len(calls) == 1
    assert len(enriched) == 3
    assert all(row["roxy_plan_source"] == "sin_velas_crypto" for row in enriched)
    assert all(row["decision_class"] == "avoid" for row in enriched)


def test_crypto_chart_surfaces_use_exchange_only_data_and_explicit_empty_state():
    helper = SOURCE[
        SOURCE.index("def cached_roxy_crypto_chart_df") : SOURCE.index("def render_roxy_crypto20_operational_charts")
    ]
    surfaces = SOURCE[
        SOURCE.index("def render_roxy_crypto20_operational_charts") : SOURCE.index("def render_roxy_folder_trade_chart")
    ]
    folders = SOURCE[
        SOURCE.index("def render_roxy_crypto20_folder") : SOURCE.index("def roxy_actions_pro_chart_payload")
    ]

    assert "roxy_crypto_history_for_signal" in helper
    assert "fetch_direct_yfinance_ohlcv" not in helper
    assert surfaces.count("cached_roxy_crypto_chart_df(symbol, pane_tf)") == 3
    assert 'render_roxy_folder_trade_chart(rows, market="crypto"' not in folders
    assert folders.count("Roxy no usa un fallback simulado") == 3


def test_deriv_contract_lookup_is_deferred_until_requested():
    lazy = SOURCE[
        SOURCE.index("def roxy_deriv_lazy_panel_html") : SOURCE.index("def render_roxy_crypto_live_runtime")
    ]

    assert 'first_query_param_value(st.query_params, "deriv")' in lazy
    assert "Contratos Deriv bajo demanda" in lazy
    assert "roxy_deriv_comparison_panel_html(" in lazy


def test_crypto_live_price_invalidates_stale_trade_plan():
    row = SOURCE[
        SOURCE.index("def roxy_crypto_opportunity_row_html") : SOURCE.index("def roxy_deriv_symbol_for_crypto")
    ]
    runtime = SOURCE[
        SOURCE.index("def render_roxy_crypto_live_runtime") : SOURCE.index("def roxy_actions_change_pct")
    ]
    folders = SOURCE[
        SOURCE.index("def render_roxy_crypto20_folder") : SOURCE.index("def roxy_actions_pro_chart_payload")
    ]

    assert "data-roxy-plan-anchor" in row
    assert "drift > 0.02" in runtime
    assert "ESPERAR RECÁLCULO" in runtime
    assert "Plan bloqueado" in runtime
    assert "data-roxy-protected-plan-value" in folders
    assert "data-roxy-plan-freshness" in folders


def test_crypto_operational_surfaces_do_not_use_decorative_universe_or_fake_deriv_label():
    folders = SOURCE[
        SOURCE.index("def render_roxy_crypto20_folder") : SOURCE.index("def roxy_actions_pro_chart_payload")
    ]
    row = SOURCE[
        SOURCE.index("def roxy_crypto_opportunity_row_html") : SOURCE.index("def roxy_deriv_symbol_for_crypto")
    ]

    assert 'class="roxy-universe"' not in folders
    assert folders.count("<b>Direccion</b>") == 3
    assert "<b>Deriv</b>" not in folders
    assert "Direccion Roxy" in row
    assert 'html.escape(plan["direction"])' in row
    assert "<small>Deriv<br>" not in row
    assert 'identity_name = cached_asset_identity(symbol, "crypto").name' in row
    assert "html.escape(identity_name)" in row
    assert folders.count('selected_identity_name = cached_asset_identity(selected_symbol, "crypto").name') == 3
    assert folders.count("html.escape(selected_identity_name)") == 3


def test_clean_roxy_operational_chart_df_removes_provider_spike():
    cleaned = clean_roxy_operational_chart_df(_sample_chart_frame(), timeframe="15m", max_points=80)

    assert not cleaned.empty
    assert cleaned["high"].max() < 120
    assert cleaned["low"].min() > 80
    assert cleaned.attrs["roxy_removed_anomalies"] >= 1


def test_clean_roxy_operational_chart_df_anchors_to_current_trade_plan_price():
    frame = _sample_chart_frame()
    bad_tail = frame.tail(12).copy()
    for column in ("open", "high", "low", "close", "ema9", "ema21", "sma20", "sma40", "bb_upper", "bb_lower"):
        if column in bad_tail.columns:
            bad_tail[column] = bad_tail[column] * 2.8
    mixed = pd.concat([frame, bad_tail], ignore_index=True)

    cleaned = clean_roxy_operational_chart_df(mixed, timeframe="15m", max_points=80, anchor_price=105.0)

    assert not cleaned.empty
    assert cleaned["close"].max() < 145
    assert cleaned["close"].min() > 65


def test_roxy_actions_pro_chart_payload_uses_cleaned_candles():
    payload = roxy_actions_pro_chart_payload(
        _sample_chart_frame(),
        symbol="TEST",
        market="stock",
        timeframe="15m",
        trade_plan={"entry": 101.0, "stop": 99.0, "target_2": 106.0},
        panel_label="Entrada",
    )

    highs = [item["high"] for item in payload["candles"]]
    lows = [item["low"] for item in payload["candles"]]
    assert max(highs) < 120
    assert min(lows) > 80
    assert {level["key"] for level in payload["levels"]} == {"entry", "stop", "target"}
    assert payload["displayRange"]["minValue"] > 80
    assert payload["displayRange"]["maxValue"] < 130


def test_dual_chart_strategy_is_evaluated_and_drawn_from_real_candles():
    m15 = _strategy_chart_frame(90, "15min")
    h1 = _strategy_chart_frame(90, "h")

    plan = streamlit_app.roxy_dual_chart_strategy_plan(
        {},
        [("15m", "Entrada 15m", m15), ("1h", "Tendencia 1h", h1)],
        symbol="TEST",
        market="stock",
        provider="fixture-provider",
    )
    payload = streamlit_app.roxy_actions_pro_chart_payload(
        m15,
        symbol="TEST",
        market="stock",
        timeframe="15m",
        trade_plan=plan,
        panel_label="Entrada 15m",
    )

    assert plan["strategy_name"] == "Uptrend Pullback to EMA21"
    assert plan["strategy_status"] != "DATA_INSUFFICIENT"
    assert any(item["type"] == "ENTRY_ZONE" for item in plan["strategy_annotations"])
    assert payload["strategySummary"]["name"] == "Uptrend Pullback to EMA21"
    assert all(item.get("timeframe") == "15m" for item in payload["strategyAnnotations"])
    assert any(item["type"] == "CONFIRMATION" for item in payload["strategyAnnotations"])
    assert payload["suggestedVisibleCandles"] == 48


def test_dual_chart_strategy_detects_and_draws_crypto_volume_structure():
    m15 = _strategy_chart_frame(90, "15min")
    h1 = _strategy_chart_frame(90, "h")
    m15.loc[m15.index[-1], "volume"] = float(m15["volume"].iloc[-20:-1].mean()) * 3.0

    plan = streamlit_app.roxy_dual_chart_strategy_plan(
        {},
        [("15m", "Entrada 15m", m15), ("1h", "Tendencia 1h", h1)],
        symbol="LINK/USD",
        market="crypto",
        provider="BinanceUS API",
    )
    payload = streamlit_app.live_candle_chart_payload(
        m15,
        symbol="LINK/USD",
        market="crypto",
        timeframe="15m",
        trade_plan=plan,
    )

    assert plan["strategy_signal"]["provider"] == "BinanceUS API"
    assert any(item["setupType"] == "VOLUME_SURGE" for item in plan["visual_structures"])
    assert any(item["type"] == "PRICE_MARKER" for item in plan["strategy_annotations"])
    assert any(item["setupType"] == "VOLUME_SURGE" for item in payload["strategySummary"]["structures"])


def test_roxy_actions_pro_chart_payload_preserves_entry_zone_for_visual_bands():
    payload = roxy_actions_pro_chart_payload(
        _sample_chart_frame(),
        symbol="TEST",
        market="stock",
        timeframe="15m",
        trade_plan={"entry": 101.0, "entry_zone_low": 100.4, "entry_zone_high": 101.3, "stop": 99.0, "target_2": 106.0},
        panel_label="Entrada",
    )

    assert payload["roxySummary"]["entryZoneLow"] == 100.4
    assert payload["roxySummary"]["entryZoneHigh"] == 101.3


def test_roxy_actions_pro_chart_payload_does_not_publish_zero_or_missing_trade_levels():
    payload = roxy_actions_pro_chart_payload(
        _sample_chart_frame(),
        symbol="TEST",
        market="stock",
        timeframe="15m",
        trade_plan={"entry": None, "stop": 0, "target_2": None, "rr_to_2": 0},
        panel_label="Entrada",
    )

    assert payload["levels"] == []
    assert payload["roxySummary"]["entry"] is None
    assert payload["roxySummary"]["stop"] is None
    assert payload["roxySummary"]["target"] is None


def test_professional_actions_chart_treats_null_and_zero_levels_as_pending():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ] + ACTIONS_PRO_CHART_TEMPLATE

    assert "const positivePrice = (value) =>" in pro_panel
    assert 'value === null || value === undefined || value === ""' in pro_panel
    assert 'let state = hasCompletePlan ? "Esperar confirmacion" : "Plan pendiente"' in pro_panel
    assert "Sin entrada, stop y objetivo verificables; Roxy no emite una decision." in pro_panel
    assert 'planComplete ? (plan.action || "Esperar confirmacion") : "Pendiente de niveles"' in pro_panel


def test_roxy_actions_pro_chart_payload_recomputes_corrupt_indicator_with_central_engine():
    frame = _sample_chart_frame()
    frame["ema9"] = 999.0

    payload = roxy_actions_pro_chart_payload(
        frame,
        symbol="TEST",
        market="stock",
        timeframe="15m",
        trade_plan={"entry": 101.0, "stop": 99.0, "target_2": 106.0},
        panel_label="Entrada",
    )

    assert payload["lines"]["EMA9"]
    assert max(item["value"] for item in payload["lines"]["EMA9"]) < 130
    assert min(item["value"] for item in payload["lines"]["EMA9"]) > 90
    assert payload["chartQuality"]["lineDomainHigh"] < 130


def test_operational_charts_load_lightweight_charts_from_local_vendor():
    assert Path("assets/vendor/lightweight-charts.4.2.3.min.js").exists()
    assert 'roxy_vendor_js_source("lightweight-charts.4.2.3.min.js")' in SOURCE

    browser_panel = SOURCE[
        SOURCE.index("def render_browser_live_candle_chart_panel") : SOURCE.index("def render_operational_chart_first")
    ] + LIVE_CHART_TEMPLATE
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ] + ACTIONS_PRO_CHART_TEMPLATE

    assert "__LIGHTWEIGHT_INLINE__" in browser_panel
    assert "__LIGHTWEIGHT_INLINE__" in pro_panel
    assert 'type="module"' not in browser_panel
    assert 'type="module"' not in pro_panel


def test_live_chart_runtime_template_escapes_payload_and_vendor_script_breakouts():
    markup = streamlit_app.roxy_live_chart_runtime_markup(
        payload={"symbol": "</script><script>alert('chart')</script>", "source": "A&B\u2028C"},
        lightweight_inline_source="window.safe=true;</script><script>alert('vendor')",
    )

    assert "__ROXY_PAYLOAD__" not in markup
    assert "__LIGHTWEIGHT_INLINE__" not in markup
    assert "</script><script>alert('chart')</script>" not in markup
    assert "</script><script>alert('vendor')" not in markup
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert('chart')" in markup
    assert "A\\u0026B\\u2028C" in markup
    assert "LightweightCharts.createChart" in markup


def test_actions_pro_chart_runtime_escapes_payload_and_vendor_script_breakouts():
    markup = streamlit_app.roxy_actions_pro_chart_runtime_markup(
        payload={"symbol": "</script><script>alert('payload')</script>", "source": "A&B\u2028C"},
        lightweight_inline_source="window.safe=true;</script><script>alert('vendor')",
        chart_id="roxy-pro-safe_chart-1",
    )

    assert "__PAYLOAD__" not in markup
    assert "__LIGHTWEIGHT_INLINE__" not in markup
    assert "__CHART_ID__" not in markup
    assert "</script><script>alert('payload')</script>" not in markup
    assert "</script><script>alert('vendor')" not in markup
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert('payload')" in markup
    assert "A\\u0026B\\u2028C" in markup
    assert markup.count("roxy-pro-safe_chart-1") == 2


def test_actions_pro_chart_runtime_rejects_invalid_dom_id():
    with pytest.raises(ValueError, match="chart id is invalid"):
        streamlit_app.roxy_actions_pro_chart_runtime_markup(
            payload={"candles": []},
            lightweight_inline_source="window.LightweightCharts={};",
            chart_id='bad-id"><script>alert(1)</script>',
        )


def test_actions_pro_chart_runtime_preserves_template_for_safe_values():
    payload = {"symbol": "AAPL", "candles": [{"time": 1, "open": 1, "high": 2, "low": 1, "close": 2}]}
    vendor = "window.LightweightCharts={};"
    chart_id = "roxy-pro-abc123"
    expected = ACTIONS_PRO_CHART_TEMPLATE.replace(
        "__PAYLOAD__", streamlit_app.roxy_json_for_inline_script(payload)
    ).replace(
        "__LIGHTWEIGHT_INLINE__", streamlit_app.roxy_json_for_inline_script(vendor)
    ).replace("__CHART_ID__", chart_id)

    assert streamlit_app.roxy_actions_pro_chart_runtime_markup(
        payload=payload,
        lightweight_inline_source=vendor,
        chart_id=chart_id,
    ) == expected


def test_stock_live_runtime_template_escapes_bridge_url_script_breakouts():
    markup = streamlit_app.roxy_stock_live_runtime_markup(
        stream_url="https://stream.invalid/</script><script>alert('stream')",
        snapshot_url="https://snapshot.invalid/?x=A&B\u2028C</script>",
    )

    assert "__ROXY_STOCK_STREAM_URL__" not in markup
    assert "__ROXY_STOCK_SNAPSHOT_URL__" not in markup
    assert "</script><script>alert('stream')" not in markup
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert('stream')" in markup
    assert "A\\u0026B\\u2028C\\u003c/script\\u003e" in markup
    assert "new EventSource" in markup


def test_stock_live_runtime_template_preserves_original_markup_for_normal_urls():
    stream_url = "https://bridge.example/v1/market/stock-stream"
    snapshot_url = "https://bridge.example/v1/market/stock-snapshot"
    expected = STOCK_LIVE_RUNTIME_TEMPLATE.replace(
        "__ROXY_STOCK_STREAM_URL__", streamlit_app.roxy_json_for_inline_script(stream_url)
    ).replace(
        "__ROXY_STOCK_SNAPSHOT_URL__", streamlit_app.roxy_json_for_inline_script(snapshot_url)
    )

    assert streamlit_app.roxy_stock_live_runtime_markup(
        stream_url=stream_url,
        snapshot_url=snapshot_url,
    ) == expected


def test_stock_server_refresh_runtime_escapes_quote_payload_from_script_breakout():
    markup = streamlit_app.roxy_stock_server_refresh_runtime_markup(
        {
            "AAPL": {
                "price": 123.45,
                "source": "feed</script><script>alert('quote')</script>&\u2028",
                "marketOpen": False,
            }
        }
    )

    assert "__ROXY_STOCK_QUOTES__" not in markup
    assert "</script><script>alert('quote')" not in markup
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert('quote')" in markup
    assert "\\u0026\\u2028" in markup
    assert "data-roxy-stock-provider-state" in markup


def test_stock_server_refresh_runtime_preserves_template_for_normal_payload():
    payload = {"AAPL": {"price": 123.45, "source": "server_quote", "marketOpen": False}}
    expected = STOCK_SERVER_REFRESH_TEMPLATE.replace(
        "__ROXY_STOCK_QUOTES__", streamlit_app.roxy_json_for_inline_script(payload)
    )

    assert streamlit_app.roxy_stock_server_refresh_runtime_markup(payload) == expected


def test_actions_reference_terminal_template_has_complete_slot_contract():
    markers = streamlit_app.ROXY_ACTIONS_REFERENCE_TERMINAL_MARKERS

    assert len(markers) == 33
    assert len(set(markers)) == 33
    assert all(ACTIONS_REFERENCE_TERMINAL_TEMPLATE.count(marker) == 1 for marker in markers)
    assert streamlit_app.roxy_actions_reference_terminal_template() == ACTIONS_REFERENCE_TERMINAL_TEMPLATE


def test_actions_reference_terminal_markup_replaces_every_slot_once():
    markers = streamlit_app.ROXY_ACTIONS_REFERENCE_TERMINAL_MARKERS
    slots = {marker: f"slot-value-{index}" for index, marker in enumerate(markers)}

    markup = streamlit_app.roxy_actions_reference_terminal_markup(slots)

    assert "__ROXY_ACTIONS_" not in markup
    assert all(f"slot-value-{index}" in markup for index in range(len(markers)))
    with pytest.raises(ValueError, match="missing"):
        streamlit_app.roxy_actions_reference_terminal_markup({})


def test_stock_sparkline_declares_missing_history_instead_of_synthesizing_prices(monkeypatch):
    monkeypatch.setattr(streamlit_app, "cached_trade_desk_chart_df", lambda *args, **kwargs: pd.DataFrame())

    markup = streamlit_app.roxy_actions_sparkline_svg("TEST", "stock")

    assert "SIN DATOS" in markup
    assert "Sin historial suficiente" in markup
    assert "polyline" not in markup


def test_actions_overview_removes_active_demo_market_and_portfolio_values():
    reference = SOURCE[
        SOURCE.index("def render_roxy_actions_reference_market_terminal") : SOURCE.index("def render_roxy_actions_folder")
    ] + ACTIONS_REFERENCE_TERMINAL_TEMPLATE

    for fake_value in ("315.32", "$125,430.50", "+$1,230.45", "sobre 320.00", "Crude Oil\", \"72.22"):
        assert fake_value not in reference
    assert "Vista previa desactivada" in reference
    assert "Roxy no muestra reglas ni niveles de demostracion" in reference
    assert "durable_store.alerts_snapshot" in reference
    assert "durable_snapshot" in reference
    assert 'st.session_state.get("watchlist")' not in reference


def test_actions_terminal_avoids_false_vendor_identity_and_empty_macro_cards():
    reference = SOURCE[
        SOURCE.index("def render_roxy_actions_reference_market_terminal") : SOURCE.index("def render_roxy_actions_folder")
    ] + ACTIONS_REFERENCE_TERMINAL_TEMPLATE

    assert "TradingView integrado" not in reference
    assert "ROXY OS 2.0" not in reference
    assert "¡Buenos días, Roberto!" not in reference
    assert "Lightweight Charts local" in reference
    assert "Contexto operativo compartido" in reference
    assert "if futures_items" in reference
    assert "if forex_items" in reference
    assert '"__ROXY_ACTIONS_MACRO_CARDS__": macro_cards_html' in reference
    assert "__ROXY_ACTIONS_MACRO_CARDS__" in ACTIONS_REFERENCE_TERMINAL_TEMPLATE


def test_professional_actions_chart_renders_operational_level_bands():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ] + ACTIONS_PRO_CHART_TEMPLATE

    assert "data-rpc-level-bands" in pro_panel
    assert "const updateLevelBands = () =>" in pro_panel
    assert "Zona entrada" in pro_panel
    assert "Stop invalida" in pro_panel
    assert "candleSeries.priceToCoordinate" in pro_panel


def test_actions_folder_prioritizes_drawing_charts_before_professional_and_plotly_fallbacks():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert folder_source.index("render_roxy_actions_dual_tool_charts") < folder_source.index(
        "render_roxy_actions_dual_pro_charts"
    ) < folder_source.index("render_roxy_actions_dual_plotly_charts")


def test_primary_dual_chart_shows_verified_structure_status_strip():
    tool_source = SOURCE[
        SOURCE.index("def render_roxy_actions_dual_tool_charts") : SOURCE.index("def render_roxy_actions_dual_plotly_charts")
    ]

    assert "visual_structures" in tool_source
    assert "ESTRUCTURAS REALES" in tool_source
    assert "item.get('strategy')" in tool_source
    assert "item.get('timeframe')" in tool_source
    assert "item.get('status')" in tool_source
    assert "item.get('confidence')" in tool_source


def test_live_chart_payload_carries_timeframe_scoped_strategy_annotations():
    payload = streamlit_app.live_candle_chart_payload(
        _sample_chart_frame(),
        symbol="TEST",
        market="stock",
        timeframe="15m",
        trade_plan={
            "strategy_name": "Triangle",
            "strategy_status": "WAITING_CONFIRMATION",
            "strategy_annotations": [
                {"type": "TREND_LINE", "timeframe": "15m", "startTime": 1, "endTime": 2, "startValue": 100, "endValue": 101},
                {"type": "TARGET", "timeframe": "1h", "value": 110},
            ],
        },
    )

    assert payload["strategySummary"]["name"] == "Triangle"
    assert payload["strategySummary"]["status"] == "WAITING_CONFIRMATION"
    assert [item["type"] for item in payload["strategyAnnotations"]] == ["TREND_LINE"]


def test_chart_session_contract_distinguishes_extended_schedule_from_regular_feed_state():
    premarket = streamlit_app.chart_market_session_contract(
        market="stock",
        timeframe="15m",
        candles=[{"time": int(datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc).timestamp())}],
        live_price={"market_open": False},
        now=datetime(2026, 7, 20, 12, 10, tzinfo=timezone.utc),
    )
    regular_closed = streamlit_app.chart_market_session_contract(
        market="stock",
        timeframe="15m",
        candles=[{"time": int(datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc).timestamp())}],
        live_price={"market_open": False},
        now=datetime(2026, 7, 20, 15, 10, tzinfo=timezone.utc),
    )

    assert premarket["scheduledSession"] == "Premarket"
    assert premarket["operationalStatus"] == "EXTENDED_SCHEDULE"
    assert premarket["lastCandleSession"] == "Premarket"
    assert premarket["extendedHoursIncluded"] is True
    assert regular_closed["scheduledSession"] == "Mercado abierto"
    assert regular_closed["operationalStatus"] == "PROVIDER_MARKET_CLOSED"
    assert regular_closed["countdownEligible"] is False


def test_live_crypto_chart_exposes_24h_candle_countdown_contract():
    payload = streamlit_app.live_candle_chart_payload(
        _sample_chart_frame(), symbol="BTC/USD", market="crypto", timeframe="15m"
    )

    assert payload["session"]["scheduledSession"] == "24h"
    assert payload["session"]["operationalStatus"] == "OPEN_24H"
    assert payload["session"]["countdownEligible"] is True
    profile_payload = streamlit_app.live_candle_chart_payload(
        _sample_chart_frame(),
        symbol="BTC/USD",
        market="crypto",
        timeframe="15m",
        strategy_profile="acciones_15m_1h",
    )
    assert profile_payload["strategy"]["title"] == "Crypto 15m/1h"
    runtime = LIVE_CHART_TEMPLATE
    assert 'id="rlc-candle-countdown"' in runtime
    assert "renderCandleCountdown" in runtime
    assert "vela finalizada · esperando proveedor" in runtime


def test_stock_chart_payload_classifies_each_extended_hours_candle_for_visual_borders():
    frame = pd.DataFrame(
        [
            {"ts": "2026-07-20T12:00:00Z", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000},
            {"ts": "2026-07-20T14:00:00Z", "open": 101, "high": 102, "low": 100, "close": 101.5, "volume": 1100},
            {"ts": "2026-07-20T20:30:00Z", "open": 102, "high": 103, "low": 101, "close": 102.5, "volume": 900},
        ]
    )
    payload = streamlit_app.live_candle_chart_payload(
        frame, symbol="AAPL", market="stock", timeframe="15m"
    )

    assert [row["sessionPhase"] for row in payload["candles"]] == [
        "PREMARKET", "REGULAR", "AFTER_HOURS"
    ]
    assert payload["sessionVisual"]["enabled"] is True
    assert payload["sessionVisual"]["regularBorder"] == "directional"
    assert "decorateSessionCandle" in LIVE_CHART_TEMPLATE
    assert "PRE borde azul" in LIVE_CHART_TEMPLATE


def test_live_chart_payload_carries_server_chart_state_for_cross_session_restore():
    payload = streamlit_app.live_candle_chart_payload(
        _sample_chart_frame(),
        symbol="TEST",
        market="stock",
        timeframe="15m",
        persisted_chart_state={
            "status": "READY",
            "drawings": [{"tool": "horizontal", "price1": 101, "version": 2}],
            "settings": {"EMA9": False, "Plan": True},
            "viewport": {"from": 1_700_000_000, "to": 1_700_086_400},
            "updated_at": "2026-07-18T00:00:00+00:00",
        },
    )

    assert payload["persistedChartState"]["status"] == "READY"
    assert payload["persistedChartState"]["drawings"][0]["price1"] == 101
    assert payload["persistedChartState"]["settings"]["EMA9"] is False
    assert payload["persistedChartState"]["viewport"] == {"from": 1_700_000_000, "to": 1_700_086_400}


def test_live_chart_runtime_persists_viewport_and_exposes_real_auto_manual_scale_modes():
    runtime = LIVE_CHART_TEMPLATE

    assert "roxy-chart-viewport:v1" in runtime
    assert "const restoreViewport = () =>" in runtime
    assert 'localStorage.setItem(viewportKey, JSON.stringify(cleanRange))' in runtime
    assert "viewport: normalizeViewport(chart.timeScale().getVisibleRange" in runtime
    assert 'applyOptions({ autoScale: Boolean(indicatorSettings.Scale) })' in runtime
    assert 'root.dataset.priceScaleMode = indicatorSettings.Scale ? "auto-visible" : "manual-axis"' in runtime
    assert "Escala auto" in runtime


def test_dual_live_charts_link_crosshair_by_symbol_without_reload():
    runtime = LIVE_CHART_TEMPLATE

    assert 'id="rlc-crosshair-link"' in runtime
    assert "new BroadcastChannel(crosshairLinkName)" in runtime
    assert "roxy-chart-crosshair:v1:${payload.market}:${payload.symbol}" in runtime
    assert "nearestCandleByTime" in runtime
    assert "chart.setCrosshairPosition" in runtime
    assert "chart.clearCrosshairPosition" in runtime
    assert "message.source === crosshairInstanceId" in runtime
    assert "lastLinkedCrosshairTime" in runtime
    assert "repeatsLinkedEvent" in runtime
    assert "suppressLinkedClear" in runtime
    assert 'root.dataset.linkedTimeframe = String(message.timeframe || "")' in runtime
    assert 'window.addEventListener("pagehide", () => crosshairChannel.close()' in runtime


def test_actions_folder_pushes_server_side_live_stock_quotes():
    refresh_source = SOURCE[
        SOURCE.index("def render_roxy_stock_server_refresh") : SOURCE.index("def roxy_secret_value")
    ] + STOCK_SERVER_REFRESH_TEMPLATE
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert 'getattr(st, "fragment", None)' in refresh_source
    assert "roxy_stock_quote_snapshot(symbol)" in refresh_source
    assert "data-roxy-stock-live-price" in refresh_source
    assert "Feed real" in refresh_source
    assert "data-roxy-stock-tick-arrow" in refresh_source
    assert "node.dataset.roxySource" in refresh_source
    assert "node.dataset.roxyMarketOpen" in refresh_source
    assert "node.dataset.roxyRefreshCount" in refresh_source
    assert "refrescado sin cambio" in refresh_source
    assert "setTickArrow(symbol, firstDirection, quote)" in refresh_source
    assert "sessionLabel(quote)" in refresh_source
    assert "streamlit_autorefresh" not in refresh_source
    assert "st_autorefresh" not in refresh_source
    assert "live_stock_symbols" in folder_source
    assert "render_roxy_stock_server_refresh(interval_ms=1500, symbols=live_stock_symbols[:10])" in folder_source


def test_actions_folder_uses_single_visible_quote_surface_and_server_refresh():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]
    terminal_source = SOURCE[
        SOURCE.index("def render_roxy_actions_reference_market_terminal") : SOURCE.index("def render_roxy_alerts_panel")
    ] + ACTIONS_REFERENCE_TERMINAL_TEMPLATE

    assert "roxy-stock-live-tape" not in folder_source
    assert "live_tape_items" not in folder_source
    assert "render_roxy_stock_server_refresh(interval_ms=1500, symbols=live_stock_symbols[:10])" in folder_source
    assert "data-roxy-stock-live-price" in terminal_source
    assert "quote_source_label" in terminal_source
    assert "quote_session_label" in terminal_source
    assert "Validando cotizaciones" in terminal_source


def test_stock_live_runtime_can_consume_secure_stream_bridge():
    runtime_source = SOURCE[
        SOURCE.index("def render_roxy_stock_live_runtime") : SOURCE.index("def render_roxy_stock_server_refresh")
    ] + STOCK_LIVE_RUNTIME_TEMPLATE

    assert "ROXY_STOCK_STREAM_URL" in runtime_source
    assert "ROXY_STOCK_SNAPSHOT_URL" in runtime_source
    assert "EventSource" in runtime_source
    assert "fetchBridgeSnapshot" in runtime_source
    assert "Snapshot real" in runtime_source
    assert "data-roxy-stock-live-price" in runtime_source
    assert "data-roxy-stock-provider-state" in runtime_source
    assert "node.dataset.roxySource = source" in runtime_source
    assert "node.dataset.roxyMarketOpen = marketOpenText" in runtime_source
    assert "node.dataset.roxyFreshness = rawFreshness" in runtime_source
    assert "node.dataset.roxyRefreshCount" in runtime_source
    assert "Bridge stock no disponible · ${detail}" in runtime_source
    assert "Stream real" in runtime_source
    assert "markBridgeDegraded" in runtime_source
    assert "Bridge stock no disponible" in runtime_source
    assert "hasRecentServerQuote" in runtime_source
    assert "node.dataset.roxyServerOkAt" in runtime_source
    assert "RESPALDO" in runtime_source
    assert "respuesta no JSON" in runtime_source
    assert "ALPACA_API_KEY" not in runtime_source
    assert "ALPACA_API_SECRET" not in runtime_source


def test_actions_terminal_exposes_visible_data_status_without_phantom_ticks():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]
    terminal_source = SOURCE[
        SOURCE.index("def render_roxy_actions_reference_market_terminal") : SOURCE.index("def render_roxy_alerts_panel")
    ] + ACTIONS_REFERENCE_TERMINAL_TEMPLATE

    assert "Estado de datos" in terminal_source
    assert "Fuente, retraso y conexión visibles" in terminal_source
    assert "quote_source_label" in terminal_source
    assert "quote_session_label" in terminal_source
    assert "market_session_status()" in terminal_source
    assert "quote_context_rows" in terminal_source
    assert "data-roxy-stock-provider-state" in terminal_source
    assert "data-roxy-stock-market-state" in terminal_source
    assert "Esperando primera cotizacion" in terminal_source
    assert "feed live..." not in folder_source
    assert "stock live inicializando" not in folder_source


def test_actions_folder_does_not_show_fake_stock_change_percentages():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert 'else "live quote"' not in folder_source
    assert '"+0.04%"' not in folder_source
    assert "4.0 - idx * .45" not in folder_source
    assert "94 - idx * 5" not in folder_source
    assert "1.5 + idx * .22" not in folder_source


def test_live_stock_snapshot_keeps_previous_close_and_change_context():
    quote_source = SOURCE[
        SOURCE.index("def roxy_stock_quote_snapshot") : SOURCE.index("def roxy_stock_live_plan_seed")
    ]

    assert "alpaca_context = roxy_alpaca_stock_latest_snapshot(clean_symbol)" in quote_source
    assert "context_previous = safe_float(alpaca_context.get(\"previous_close\"))" in quote_source
    assert "context_change = safe_float(alpaca_context.get(\"change_pct\"))" in quote_source
    assert "source_label = f\"{source_label} + {context_source}\"" in quote_source
    assert "\"previous_close\": previous" in quote_source
    assert "\"change_pct\": change_pct" in quote_source


def test_living_market_stock_quote_exports_previous_close_and_change_pct():
    yf_source = LIVING_SOURCE[
        LIVING_SOURCE.index("def fetch_yfinance_quote_price") : LIVING_SOURCE.index("def build_live_price_snapshot")
    ]
    snapshot_source = LIVING_SOURCE[
        LIVING_SOURCE.index("def build_live_price_snapshot") : LIVING_SOURCE.index("def fetch_asset_history")
    ]

    assert "previous_close = safe_float(" in yf_source
    assert "\"previous_close\": previous_close" in yf_source
    assert "\"change_pct\": ((price - previous_close) / previous_close)" in yf_source
    assert "quote_context = fetch_yfinance_quote_price(normalized_symbol)" not in snapshot_source
    assert 'previous_close = safe_float(alpaca_snapshot.get("previous_close"))' in snapshot_source
    assert "\"previous_close\": locals().get(\"previous_close\", None)" in snapshot_source
    assert "\"change_pct\": locals().get(\"change_pct\", None)" in snapshot_source


def test_stock_live_runtime_updates_refresh_count_and_market_state_badges():
    runtime_source = SOURCE[
        SOURCE.index("def render_roxy_stock_live_runtime") : SOURCE.index("def render_roxy_stock_server_refresh")
    ] + STOCK_LIVE_RUNTIME_TEMPLATE
    refresh_source = SOURCE[
        SOURCE.index("def render_roxy_stock_server_refresh") : SOURCE.index("def roxy_secret_value")
    ] + STOCK_SERVER_REFRESH_TEMPLATE

    assert "const setRefreshMeta = (symbol, direction, quote = {}) =>" in runtime_source
    assert "data-roxy-stock-refresh-count" in runtime_source
    assert "data-roxy-stock-market-state" in runtime_source
    assert "data-roxy-stock-feed-diagnostic" in runtime_source
    assert "Mercado cerrado · ultimo precio real" in runtime_source
    assert "Mercado cerrado: Roxy muestra ultimo precio real y no simula ticks" in runtime_source
    assert "const setRefreshMeta = (symbol, direction, quote) =>" in refresh_source
    assert "setRefreshMeta(symbol, firstDirection, quote)" in refresh_source
    assert "server quote" in refresh_source


def test_actions_folder_exposes_verified_plan_state_to_operational_charts():
    runtime_source = SOURCE[
        SOURCE.index("def render_roxy_stock_live_runtime") : SOURCE.index("def render_roxy_stock_server_refresh")
    ] + STOCK_LIVE_RUNTIME_TEMPLATE
    refresh_source = SOURCE[
        SOURCE.index("def render_roxy_stock_server_refresh") : SOURCE.index("def roxy_secret_value")
    ] + STOCK_SERVER_REFRESH_TEMPLATE
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert "plan_ready = bool(trade_plan.get(\"plan_ready\"))" in folder_source
    assert "Plan pendiente: faltan niveles verificables" in folder_source
    assert "verified_entry" in folder_source
    assert "verified_stop" in folder_source
    assert "verified_target" in folder_source
    assert "En zona entrada" in runtime_source
    assert "Target en juego" in runtime_source
    assert "Cerca del stop" in refresh_source
    assert "setTradeState(symbol, quote)" in refresh_source


def test_professional_actions_chart_syncs_from_parent_live_stock_quote():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ] + ACTIONS_PRO_CHART_TEMPLATE

    assert 'class="rpc-tradebar"' in pro_panel
    assert "const renderTradebar = (price, source = \"historial\") =>" in pro_panel
    assert "const applySmartScale = (livePrice = null) =>" in pro_panel
    assert "const smartRangeFor = (livePrice = null) =>" in pro_panel
    assert "const recent = candles.slice(-Math.max(34, Math.min(96, visibleHint + 22)))" in pro_panel
    assert "const parentQuote = () =>" in pro_panel
    assert 'parentDoc.querySelectorAll("[data-roxy-stock-live-price]")' in pro_panel
    assert "node.dataset.roxyServerPrice || node.dataset.roxyPrice" in pro_panel
    assert "node.dataset.roxyMarketOpen" in pro_panel
    assert "const isClosed =" in pro_panel
    assert "LAST ${fmt(price)}" in pro_panel
    assert "RESPALDO ${fmt(price)}" in pro_panel
    assert "const isBackupQuote = hasRealQuote" in pro_panel
    assert "const syncLiveQuote = async (overrideQuote = null) =>" in pro_panel
    assert "const quote = overrideQuote || parentQuote();" in pro_panel
    assert "esperando quote del servidor" in pro_panel
    assert "parentDoc.addEventListener(\"roxy-stock-quote\"" in pro_panel
    assert "syncLiveQuote(detail.quote || detail)" in pro_panel
    assert "renderTradebar(price, feedLabel)" in pro_panel
    assert "renderReading(price, feedLabel)" in pro_panel
    assert "applySmartScale(price)" in pro_panel
    assert "payload.displayRange" in pro_panel
    assert "rpc-closed" in pro_panel
    assert "rpc-degraded" in pro_panel
    assert "Feed respaldo" in pro_panel
    assert "Feed respaldo real" in pro_panel
    assert "Roxy usa un quote real de respaldo" in pro_panel
    assert "Roxy conserva la ultima vela/precio real y espera un quote nuevo" in pro_panel
    assert "Mercado cerrado: Roxy no simula ticks" in pro_panel
    assert "lastEl.classList.add(\"rpc-closed\")" in pro_panel
    assert "lastEl.classList.add(\"rpc-degraded\")" in pro_panel
    assert "Precio sincronizado sobre la vela actual sin salir de la pagina" in pro_panel


def test_professional_actions_charts_render_full_width_operational_stack():
    dual_source = SOURCE[
        SOURCE.index("def render_roxy_actions_dual_pro_charts") : SOURCE.index("def render_roxy_actions_dual_plotly_charts")
    ]
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert "height: int = 760" in dual_source
    assert "roxy-actions-pro-chart-stack" in dual_source
    assert "roxy-actions-pro-chart-title" in dual_source
    assert "ancho completo operativo" in dual_source
    assert "st.columns([1, 1]" not in dual_source
    assert "height=760" in folder_source


def test_plotly_actions_fallback_also_renders_full_width_stack():
    plotly_source = SOURCE[
        SOURCE.index("def render_roxy_actions_dual_plotly_charts") : SOURCE.index("def render_roxy_actions_dual_static_charts")
    ]

    assert "roxy-actions-plotly-stack" in plotly_source
    assert "roxy-actions-plotly-title" in plotly_source
    assert "fallback ancho completo" in plotly_source
    assert "height=max(height, 680)" in plotly_source
    assert "st.columns([1, 1]" not in plotly_source


def test_professional_actions_chart_explains_roxy_entry_stop_target_reading():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ] + ACTIONS_PRO_CHART_TEMPLATE

    assert 'class="rpc-reading"' in pro_panel
    assert "const renderReading = (price, source = \"historial\") =>" in pro_panel
    assert "Lectura Roxy" in pro_panel
    assert "Entrada exacta" in pro_panel
    assert "Invalidacion" in pro_panel
    assert "Stop no se negocia" in pro_panel
    assert 'button data-range="32" class="active"' in pro_panel
    assert "Zoom operativo" in pro_panel
    assert "setVisible(window.innerWidth < 720 ? 32 : (payload.suggestedVisibleCandles || 48))" in pro_panel


def test_professional_actions_chart_has_operational_layer_controls():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ] + ACTIONS_PRO_CHART_TEMPLATE

    assert 'button data-layer="clean"' in pro_panel
    assert 'button data-layer="strategy" class="layer-active"' in pro_panel
    assert 'button data-layer="all"' in pro_panel
    assert "const applyLayerMode = (mode) =>" in pro_panel
    assert "const emaSeries = []" in pro_panel
    assert "const trendSeries = []" in pro_panel
    assert "emaSeries.forEach((series) => series.applyOptions({ visible: !clean }))" in pro_panel
    assert "trendSeries.forEach((series) => series.applyOptions({ visible: all }))" in pro_panel
    assert 'const strategy = mode === "strategy";' in pro_panel
    assert "bollingerSeries.forEach((series) => series.applyOptions({ visible: all || strategy }))" in pro_panel
    assert "volume.applyOptions({ visible: all || strategy })" in pro_panel
    assert "const strategyAnnotations = (payload.strategyAnnotations || [])" in pro_panel
    assert "const visiblePlanLevels = strategyAnnotations.length ? [] : (payload.levels || [])" in pro_panel
    assert 'const key = value.toFixed(precision)' in pro_panel
    assert "strategyPriceLines.forEach((line) => line.applyOptions({ lineVisible: !clean" in pro_panel
    assert 'type === "ENTRY_ZONE"' in pro_panel
    assert 'if (type === "TREND_LINE")' in pro_panel
    assert 'strategyLineSeries.forEach((series) => series.applyOptions({ visible: !clean }))' in pro_panel
    assert 'strategyReady ? "arrowUp" : "arrowDown"' in pro_panel
    assert "if (stageEl) stageEl.dataset.layerMode = mode;" in pro_panel
    assert 'applyLayerMode("strategy")' in pro_panel


def test_actions_folder_shows_real_source_and_plan_state():
    folder = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert "plan_source" in folder
    assert "Fuente no informada" in folder
    assert "Plan operativo verificado" in folder
    assert 'roxy_primary_navigation_html(\n            "trading.charts",' in folder
    assert "strategy_panes" in folder
    assert "roxy_dual_chart_strategy_plan(" in folder
    assert 'trade_plan.get("strategy_name")' in folder
    assert "RESPALDO" in FRONTEND_RUNTIME_SOURCE
    assert "respuesta no JSON" in FRONTEND_RUNTIME_SOURCE
    assert "HTTP ${res.status}" in FRONTEND_RUNTIME_SOURCE


def test_professional_actions_chart_keeps_operational_space_clear():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ] + ACTIONS_PRO_CHART_TEMPLATE

    assert ".rpc-stage{position:relative;flex:1 1 auto;min-height:560px" in pro_panel
    assert 'data-rpc-stage data-layer-mode="strategy"' in pro_panel
    assert ".rpc-chart{position:absolute;inset:6px 7px 56px 7px}" in pro_panel
    assert ".rpc-level-bands{position:absolute;inset:6px 7px 56px" in pro_panel
    assert "barSpacing: window.innerWidth < 720 ? 15 : 20" in pro_panel
    assert 'chart.priceScale("volume").applyOptions({ scaleMargins: { top: .84, bottom: 0 }, visible: false' in pro_panel
    assert "Lectura Roxy · modo trading limpio" in pro_panel
    assert "Objetivo · distancia" in pro_panel


def test_professional_actions_chart_uses_operational_body_range_not_extreme_wicks():
    frame = _sample_chart_frame().tail(36).copy()
    frame.loc[frame.index[-1], "high"] = frame["close"].iloc[-1] * 1.35
    frame.loc[frame.index[-1], "low"] = frame["close"].iloc[-1] * 0.65

    payload = roxy_actions_pro_chart_payload(
        frame,
        symbol="TEST",
        market="stock",
        timeframe="15m",
        trade_plan={"entry": 103.0, "stop": 101.0, "target_2": 107.0},
        panel_label="Entrada",
    )

    assert payload["displayRange"]["minValue"] > 85
    assert payload["displayRange"]["maxValue"] < 125


def test_generic_trade_plan_does_not_synthesize_levels_from_price_only():
    plan = streamlit_app.roxy_trade_plan_from_row(
        {"symbol": "AAPL", "current_price": 200.0},
        symbol="AAPL",
        market="stock",
        timeframe="15m",
        action="Vigilar",
    )

    assert plan["entry"] == 200.0
    assert plan["stop"] is None
    assert plan["target_2"] is None
    assert plan["target_5"] is None
    assert plan["risk_pct"] is None
    assert plan["plan_ready"] is False
    assert plan["plan_status"] == "Plan pendiente: faltan niveles verificables"


def test_generic_trade_plan_preserves_explicit_verified_levels():
    plan = streamlit_app.roxy_trade_plan_from_row(
        {"entry": 200.0, "stop": 195.0, "target_price": 210.0, "data_source": "Alpaca IEX"},
        symbol="AAPL",
        market="stock",
        timeframe="15m",
        action="Comprar",
    )

    assert plan["plan_ready"] is True
    assert plan["stop"] == 195.0
    assert plan["target_2"] == 210.0
    assert plan["rr_to_2"] == 2.0
    assert plan["plan_source"] == "Alpaca IEX"
