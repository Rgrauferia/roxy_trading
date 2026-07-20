import json
import base64

import streamlit_app

from roxy_trader.chart_state import (
    ChartStateStore,
    normalize_chart_drawing,
    normalize_chart_drawings,
    normalize_chart_settings,
    normalize_chart_viewport,
)


def test_chart_state_round_trip_is_scoped_by_user_symbol_and_timeframe(tmp_path):
    store = ChartStateStore(tmp_path / "chart_state.json")
    saved = store.save(
        "Trader@Example.com",
        symbol="aapl",
        market="stock",
        timeframe="15m",
        drawings=[
            {"tool": "trend", "time1": 1, "time2": 2, "price1": 100.5, "price2": 102.0, "version": 99},
        ],
        settings={"EMA9": True, "SMA200": False},
        viewport={"from": 1_700_000_000, "to": 1_700_086_400},
    )

    assert saved["saved"] is True
    assert saved["drawing_count"] == 1
    snapshot = store.snapshot("trader@example.com", symbol="AAPL", market="stock", timeframe="15m")
    assert snapshot["status"] == "READY"
    assert snapshot["drawings"][0]["tool"] == "trend"
    assert snapshot["drawings"][0]["version"] == 2
    assert snapshot["settings"] == {"EMA9": True, "SMA200": False}
    assert snapshot["viewport"] == {"from": 1_700_000_000, "to": 1_700_086_400}
    assert store.snapshot("trader@example.com", symbol="AAPL", market="stock", timeframe="1h")["status"] == "NO_DATA"


def test_chart_state_rejects_unknown_tools_nonfinite_values_and_markup():
    assert normalize_chart_drawing({"tool": "script", "price1": 10}) is None
    assert normalize_chart_drawing({"tool": "trend", "text": "x"}) is None
    clean = normalize_chart_drawing(
        {"tool": "text", "price1": 10, "time1": 20, "text": " <b>nota</b> ", "price2": float("inf")}
    )
    assert clean == {"tool": "text", "version": 2, "time1": 20, "price1": 10, "text": "bnota/b"}


def test_chart_state_accepts_manual_structure_drawings():
    for tool in ("triangle", "wedgeUp", "wedgeDown"):
        clean = normalize_chart_drawing(
            {"tool": tool, "time1": 1_700_000_000, "time2": 1_700_003_600, "price1": 104, "price2": 98}
        )
        assert clean == {
            "tool": tool,
            "version": 2,
            "time1": 1_700_000_000,
            "time2": 1_700_003_600,
            "price1": 104,
            "price2": 98,
        }


def test_chart_state_caps_payload_and_writes_valid_json(tmp_path):
    store = ChartStateStore(tmp_path / "chart_state.json")
    drawings = [{"tool": "horizontal", "price1": index + 1} for index in range(240)]
    settings = {f"S{index}": index % 2 == 0 for index in range(50)}

    result = store.save(
        "local",
        symbol="BTC/USD",
        market="crypto",
        timeframe="1h",
        drawings=drawings,
        settings=settings,
    )

    assert result["drawing_count"] == 200
    payload = json.loads((tmp_path / "chart_state.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    snapshot = store.snapshot("local", symbol="BTC/USD", market="crypto", timeframe="1h")
    assert len(snapshot["drawings"]) == 200
    assert len(snapshot["settings"]) == 32


def test_chart_state_normalizers_ignore_invalid_container_types():
    assert normalize_chart_drawings({"tool": "trend"}) == []
    assert normalize_chart_settings(["EMA9"]) == {}
    assert normalize_chart_viewport([1, 2]) == {}
    assert normalize_chart_viewport({"from": 10, "to": 9}) == {}
    assert normalize_chart_viewport({"from": 1, "to": 400_000_000}) == {}


def test_chart_sync_query_payload_decoder_accepts_urlsafe_json_and_rejects_oversize():
    payload = {
        "symbol": "AAPL",
        "market": "stock",
        "timeframe": "15m",
        "drawings": [],
        "settings": {"EMA9": True},
        "viewport": {"from": 1_700_000_000, "to": 1_700_086_400},
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")

    assert streamlit_app.roxy_decode_chart_sync_payload(encoded) == payload
    assert streamlit_app.roxy_decode_chart_sync_payload("not+urlsafe") is None
    assert streamlit_app.roxy_decode_chart_sync_payload("a" * 64001) is None
