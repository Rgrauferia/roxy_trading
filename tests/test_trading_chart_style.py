import altair as alt
import pandas as pd

from streamlit_app import style_trading_chart


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
