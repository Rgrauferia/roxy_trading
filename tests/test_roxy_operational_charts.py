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
    assert "setTickArrow(symbol, firstDirection, quote)" in refresh_source
    assert "sessionLabel(quote)" in refresh_source
    assert "streamlit_autorefresh" not in refresh_source
    assert "st_autorefresh" not in refresh_source
    assert "live_stock_symbols" in folder_source
    assert "render_roxy_stock_server_refresh(interval_ms=3000, symbols=live_stock_symbols)" in folder_source


def test_stock_live_runtime_can_consume_secure_stream_bridge():
    runtime_source = SOURCE[
        SOURCE.index("def render_roxy_stock_live_runtime") : SOURCE.index("def render_roxy_stock_server_refresh")
    ]

    assert "ROXY_STOCK_STREAM_URL" in runtime_source
    assert "EventSource" in runtime_source
    assert "data-roxy-stock-live-price" in runtime_source
    assert "Stream real" in runtime_source
    assert "ALPACA_API_KEY" not in runtime_source
    assert "ALPACA_API_SECRET" not in runtime_source


def test_actions_folder_exposes_visible_live_feed_status_per_stock_row():
    folder_source = SOURCE[
        SOURCE.index("def render_roxy_actions_folder") : SOURCE.index("def render_roxy_crypto20_folder")
    ]

    assert 'class="live-source"' in folder_source
    assert "data-roxy-stock-live-status" in folder_source
    assert "feed live..." in folder_source
    assert "stock live inicializando" in folder_source


def test_professional_actions_chart_syncs_from_parent_live_stock_quote():
    pro_panel = SOURCE[
        SOURCE.index("def render_roxy_actions_pro_chart_panel") : SOURCE.index("def render_roxy_actions_dual_pro_charts")
    ]

    assert 'class="rpc-tradebar"' in pro_panel
    assert "const renderTradebar = (price, source = \"historial\") =>" in pro_panel
    assert "const applySmartScale = (livePrice = null) =>" in pro_panel
    assert "const smartRangeFor = (livePrice = null) =>" in pro_panel
    assert "const parentQuote = () =>" in pro_panel
    assert 'parentDoc.querySelectorAll("[data-roxy-stock-live-price]")' in pro_panel
    assert "node.dataset.roxyServerPrice || node.dataset.roxyPrice" in pro_panel
    assert "node.dataset.roxyMarketOpen" in pro_panel
    assert "const isClosed =" in pro_panel
    assert "LAST ${fmt(price)}" in pro_panel
    assert "parentQuote() || await yahooQuote(payload.symbol)" in pro_panel
    assert "renderTradebar(price, feedLabel)" in pro_panel
    assert "applySmartScale(price)" in pro_panel
    assert "Precio sincronizado sobre la vela actual sin salir de la pagina" in pro_panel
