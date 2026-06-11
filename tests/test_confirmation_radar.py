import pandas as pd

from streamlit_app import confirmation_radar_action, confirmation_radar_rows


def test_confirmation_radar_rows_groups_repeated_missing_requirements():
    confluence = pd.DataFrame(
        [
            {
                "symbol": "WMT",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 90,
                "trigger_raw_signal": "WATCH",
                "trend_signal": "WATCH",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_confirmations": 1,
                "higher_tf_blocks": 0,
                "risk_pct": 0.02,
                "relative_volume_15m": 0.4,
                "target_2pct_ok": False,
                "backtest_eligible": True,
            },
            {
                "symbol": "SCHW",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 84,
                "trigger_raw_signal": "BUY",
                "trend_signal": "WATCH",
                "trend_setup": "PULLBACK",
                "higher_tf_confirmations": 0,
                "higher_tf_blocks": 1,
                "risk_pct": 0.05,
                "relative_volume_15m": 0.3,
                "target_2pct_ok": False,
                "backtest_eligible": False,
            },
            {
                "symbol": "AAPL",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "confluence_score": 99,
                "trigger_raw_signal": "BUY",
                "trend_signal": "WATCH",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_confirmations": 2,
                "higher_tf_blocks": 0,
                "risk_pct": 0.018,
                "relative_volume_15m": 1.2,
                "target_2pct_ok": True,
                "backtest_eligible": True,
            },
        ]
    )

    rows = confirmation_radar_rows(confluence, limit=5)
    by_requirement = {row["requirement"]: row for row in rows.to_dict("records")}

    assert rows.columns.tolist() == ["requirement", "tone", "missing_count", "top_symbols", "action"]
    assert by_requirement["target 2% viable"]["missing_count"] == 2
    assert by_requirement["target 2% viable"]["top_symbols"] == "WMT · SCHW"
    assert by_requirement["volumen acompaña"]["missing_count"] == 2
    assert by_requirement["riesgo <=3.5%"]["tone"] == "avoid"
    assert rows.iloc[0]["missing_count"] >= rows.iloc[-1]["missing_count"]


def test_confirmation_radar_rows_ignores_ready_setups_and_empty_input():
    ready = pd.DataFrame(
        [
            {
                "symbol": "NVDA",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "trigger_raw_signal": "BUY",
                "trend_signal": "WATCH",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_confirmations": 2,
                "higher_tf_blocks": 0,
                "risk_pct": 0.02,
                "relative_volume_15m": 1.4,
                "target_2pct_ok": True,
                "backtest_eligible": True,
            }
        ]
    )

    assert confirmation_radar_rows(ready).empty
    assert confirmation_radar_rows(pd.DataFrame()).empty


def test_confirmation_radar_action_maps_known_requirement():
    assert "stop queda amplio" in confirmation_radar_action("riesgo <=3.5%")
