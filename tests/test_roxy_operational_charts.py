import pandas as pd
from pathlib import Path

from streamlit_app import clean_roxy_operational_chart_df, roxy_actions_pro_chart_payload


SOURCE = Path("streamlit_app.py").read_text(encoding="utf-8")


def _sample_chart_frame() -> pd.DataFrame:
    rows = []
    base = pd.Timestamp("2026-07-01 09:30", tz="UTC")
    price = 100.0
    for index in range(44):
        open_price = price + (index % 4) * 0.05
        close_price = open_price + (0.25 if index % 3 else -0.12)
        rows.append(
            {
                "ts": base + pd.Timedelta(minutes=15 * index),
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
            "ts": base + pd.Timedelta(minutes=15 * 22, seconds=1),
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
    assert payload["suggestedVisibleCandles"] == 56


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


def test_roxy_actions_pro_chart_payload_filters_indicator_values_outside_price_regime():
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

    assert payload["lines"]["EMA9"] == []
    assert payload["chartQuality"]["lineDomainHigh"] < 130


def test_operational_charts_load_lightweight_charts_from_local_vendor():
    assert Path("assets/vendor/lightweight-charts.4.2.3.min.js").exists()
    assert 'roxy_vendor_js_source("lightweight-charts.4.2.3.min.js")' in SOURCE

    browser_panel = SOURCE[
        SOURCE.index("def render_browser_live_candle_chart_panel") : SOURCE.index("def render_operational_chart_first")
    ]
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ]

    assert "__LIGHTWEIGHT_INLINE__" in browser_panel
    assert "__LIGHTWEIGHT_INLINE__" in pro_panel
    assert 'type="module"' not in browser_panel
    assert 'type="module"' not in pro_panel


def test_professional_actions_chart_renders_operational_level_bands():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ]

    assert "data-rpc-level-bands" in pro_panel
    assert "const updateLevelBands = () =>" in pro_panel
    assert "Zona entrada" in pro_panel
    assert "Stop invalida" in pro_panel
    assert "candleSeries.priceToCoordinate" in pro_panel


def test_actions_folder_prioritizes_professional_charts_before_plotly_fallback():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert folder_source.index("render_roxy_actions_dual_pro_charts") < folder_source.index(
        "render_roxy_actions_dual_plotly_charts"
    )


def test_actions_folder_pushes_server_side_live_stock_quotes():
    refresh_source = SOURCE[
        SOURCE.index("def render_roxy_stock_server_refresh") : SOURCE.index("def roxy_secret_value")
    ]
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
    assert "render_roxy_stock_server_refresh(interval_ms=1500, symbols=live_stock_symbols)" in folder_source


def test_actions_folder_exposes_visible_stock_live_tape():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert "roxy-stock-live-tape" in folder_source
    assert 'aria-label="Precios live de acciones"' in folder_source
    assert "live_tape_items" in folder_source
    assert "data-roxy-stock-live-price" in folder_source
    assert "data-roxy-stock-tick-arrow" in folder_source


def test_stock_live_runtime_can_consume_secure_stream_bridge():
    runtime_source = SOURCE[
        SOURCE.index("def render_roxy_stock_live_runtime") : SOURCE.index("def render_roxy_stock_server_refresh")
    ]

    assert "ROXY_STOCK_STREAM_URL" in runtime_source
    assert "ROXY_STOCK_SNAPSHOT_URL" in runtime_source
    assert "EventSource" in runtime_source
    assert "fetchBridgeSnapshot" in runtime_source
    assert "Snapshot real" in runtime_source
    assert "data-roxy-stock-live-price" in runtime_source
    assert "node.dataset.roxySource = source" in runtime_source
    assert "node.dataset.roxyMarketOpen = marketOpenText" in runtime_source
    assert "node.dataset.roxyFreshness = rawFreshness" in runtime_source
    assert "node.dataset.roxyRefreshCount" in runtime_source
    assert "Bridge stock no disponible · ${detail}" in runtime_source
    assert "Stream real" in runtime_source
    assert "markBridgeDegraded" in runtime_source
    assert "Bridge stock no disponible" in runtime_source
    assert "respuesta no JSON" in runtime_source
    assert "ALPACA_API_KEY" not in runtime_source
    assert "ALPACA_API_SECRET" not in runtime_source


def test_actions_folder_exposes_visible_live_feed_status_per_stock_row():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert 'class="live-source"' in folder_source
    assert "data-roxy-stock-live-status" in folder_source
    assert "data-roxy-stock-refresh-count" in folder_source
    assert "data-roxy-stock-market-state" in folder_source
    assert "feed live..." in folder_source
    assert "validando mercado" in folder_source
    assert "stock live inicializando" in folder_source


def test_stock_live_runtime_updates_refresh_count_and_market_state_badges():
    runtime_source = SOURCE[
        SOURCE.index("def render_roxy_stock_live_runtime") : SOURCE.index("def render_roxy_stock_server_refresh")
    ]
    refresh_source = SOURCE[
        SOURCE.index("def render_roxy_stock_server_refresh") : SOURCE.index("def roxy_secret_value")
    ]

    assert "const setRefreshMeta = (symbol, direction, quote = {}) =>" in runtime_source
    assert "data-roxy-stock-refresh-count" in runtime_source
    assert "data-roxy-stock-market-state" in runtime_source
    assert "Mercado cerrado · ultimo precio real" in runtime_source
    assert "const setRefreshMeta = (symbol, direction, quote) =>" in refresh_source
    assert "setRefreshMeta(symbol, firstDirection, quote)" in refresh_source
    assert "server quote" in refresh_source


def test_actions_folder_updates_trade_state_from_live_stock_prices():
    runtime_source = SOURCE[
        SOURCE.index("def render_roxy_stock_live_runtime") : SOURCE.index("def render_roxy_stock_server_refresh")
    ]
    refresh_source = SOURCE[
        SOURCE.index("def render_roxy_stock_server_refresh") : SOURCE.index("def roxy_secret_value")
    ]
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert "data-roxy-trade-state" in folder_source
    assert "data-entry=" in folder_source
    assert "En zona entrada" in runtime_source
    assert "Target en juego" in runtime_source
    assert "Cerca del stop" in refresh_source
    assert "setTradeState(symbol, quote)" in refresh_source


def test_professional_actions_chart_syncs_from_parent_live_stock_quote():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ]

    assert 'class="rpc-tradebar"' in pro_panel
    assert "const renderTradebar = (price, source = \"historial\") =>" in pro_panel
    assert "const applySmartScale = (livePrice = null) =>" in pro_panel
    assert "const smartRangeFor = (livePrice = null) =>" in pro_panel
    assert "const recent = candles.slice(-96)" in pro_panel
    assert "const parentQuote = () =>" in pro_panel
    assert 'parentDoc.querySelectorAll("[data-roxy-stock-live-price]")' in pro_panel
    assert "node.dataset.roxyServerPrice || node.dataset.roxyPrice" in pro_panel
    assert "node.dataset.roxyMarketOpen" in pro_panel
    assert "const isClosed =" in pro_panel
    assert "LAST ${fmt(price)}" in pro_panel
    assert "parentQuote() || await yahooQuote(payload.symbol)" in pro_panel
    assert "renderTradebar(price, feedLabel)" in pro_panel
    assert "renderReading(price, feedLabel)" in pro_panel
    assert "applySmartScale(price)" in pro_panel
    assert "payload.displayRange" in pro_panel
    assert "rpc-closed" in pro_panel
    assert "rpc-degraded" in pro_panel
    assert "Bridge stock caido" in pro_panel
    assert "Roxy conserva la ultima vela/precio real y no simula movimiento" in pro_panel
    assert "Mercado cerrado: Roxy no simula ticks" in pro_panel
    assert "lastEl.classList.add(\"rpc-closed\")" in pro_panel
    assert "lastEl.classList.add(\"rpc-degraded\")" in pro_panel
    assert "Precio sincronizado sobre la vela actual sin salir de la pagina" in pro_panel


def test_professional_actions_chart_explains_roxy_entry_stop_target_reading():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ]

    assert 'class="rpc-reading"' in pro_panel
    assert "const renderReading = (price, source = \"historial\") =>" in pro_panel
    assert "Lectura Roxy" in pro_panel
    assert "Entrada exacta" in pro_panel
    assert "Invalidacion" in pro_panel
    assert "Stop no se negocia" in pro_panel
    assert 'button data-range="56" class="active"' in pro_panel
    assert "Zoom operativo" in pro_panel
    assert "setVisible(window.innerWidth < 720 ? 38 : (payload.suggestedVisibleCandles || 56))" in pro_panel


def test_professional_actions_chart_has_operational_layer_controls():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ]

    assert 'button data-layer="clean"' in pro_panel
    assert 'button data-layer="strategy" class="layer-active"' in pro_panel
    assert 'button data-layer="all"' in pro_panel
    assert "const applyLayerMode = (mode) =>" in pro_panel
    assert "const emaSeries = []" in pro_panel
    assert "const trendSeries = []" in pro_panel
    assert "emaSeries.forEach((series) => series.applyOptions({ visible: !clean }))" in pro_panel
    assert "trendSeries.forEach((series) => series.applyOptions({ visible: all }))" in pro_panel
    assert "bollingerSeries.forEach((series) => series.applyOptions({ visible: all }))" in pro_panel
    assert "volume.applyOptions({ visible: all })" in pro_panel
    assert 'applyLayerMode("strategy")' in pro_panel


def test_actions_folder_shows_real_quote_mode_badges():
    folder = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert "data-roxy-stock-quote-mode" in folder
    assert 'class="quote-mode mode-quote"' in folder
    assert 'class="chart-mode mode-quote"' in folder
    assert ".mode-live" in folder
    assert ".mode-last" in folder
    assert ".mode-degraded" in folder
    assert "BRIDGE CAIDO" in SOURCE
    assert "respuesta no JSON" in SOURCE
    assert "HTTP ${res.status}" in SOURCE


def test_professional_actions_chart_keeps_operational_space_clear():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ]

    assert ".rpc-stage{position:relative;flex:1 1 auto;min-height:560px" in pro_panel
    assert ".rpc-chart{position:absolute;inset:6px 7px 56px 7px}" in pro_panel
    assert ".rpc-level-bands{position:absolute;inset:6px 7px 56px" in pro_panel
    assert "barSpacing: window.innerWidth < 720 ? 12 : 18" in pro_panel
    assert 'chart.priceScale("volume").applyOptions({ scaleMargins: { top: .84, bottom: 0 }, visible: false' in pro_panel


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
