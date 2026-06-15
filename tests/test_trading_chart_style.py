import altair as alt
import pandas as pd

from streamlit_app import candle_wick_pressure_label, chart_window_pressure_label, style_trading_chart


def test_style_trading_chart_uses_compact_terminal_axis_config():
    chart = alt.Chart(pd.DataFrame({"ts": pd.date_range("2026-01-01", periods=2), "price": [1, 2]})).mark_line().encode(
        x="ts:T",
        y="price:Q",
    )

    spec = style_trading_chart(chart).to_dict()

    assert spec["config"]["axisX"]["title"] is None
    assert spec["config"]["axisX"]["labelAngle"] == 0
    assert spec["config"]["legend"]["orient"] == "bottom"
    assert spec["config"]["background"] == "#0b1220"
    assert spec["params"][0]["bind"] == "scales"
    assert spec["params"][0]["select"]["encodings"] == ["x"]


def test_chart_window_pressure_label_explains_range_position():
    assert chart_window_pressure_label(0.9, 0.004, -0.08)[0:2] == ("avoid", "Presion en techo")
    assert chart_window_pressure_label(0.1, 0.08, -0.004)[0:2] == ("buy", "Presion en piso")
    assert chart_window_pressure_label(0.5, 0.03, -0.03)[0:2] == ("watch", "Rango medio")


def test_candle_wick_pressure_label_explains_supply_demand():
    assert candle_wick_pressure_label(0.008, 0.001, 0.003) == "Oferta arriba"
    assert candle_wick_pressure_label(0.001, 0.008, 0.003) == "Demanda abajo"
    assert candle_wick_pressure_label(0.003, 0.003, 0.002) == "Mechas mixtas"


def test_style_trading_chart_can_disable_live_refresh_selection():
    chart = alt.Chart(pd.DataFrame({"ts": pd.date_range("2026-01-01", periods=2), "price": [1, 2]})).mark_line().encode(
        x="ts:T",
        y="price:Q",
    )

    spec = style_trading_chart(chart, interactive=False).to_dict()

    assert spec["config"]["axisX"]["title"] is None
    assert spec["config"]["background"] == "#0b1220"
    assert "params" not in spec


def test_style_trading_chart_skips_scale_binding_for_layered_charts():
    data = pd.DataFrame({"ts": pd.date_range("2026-01-01", periods=2), "price": [1, 2]})
    line = alt.Chart(data).mark_line().encode(x="ts:T", y="price:Q")
    rule = alt.Chart(data).mark_rule().encode(x="ts:T")

    spec = style_trading_chart(line + rule).to_dict()

    assert "params" not in spec
