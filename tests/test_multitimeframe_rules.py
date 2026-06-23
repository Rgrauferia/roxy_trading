from multitimeframe_rules import (
    build_multitimeframe_context,
    channel_duration_for,
    multitimeframe_condition_checks,
)


def test_alcista_long_channel_duration_from_masterclass():
    result = channel_duration_for("alcista", "canal alcista largo plazo")

    assert result["trend_regime"] == "ALCISTA"
    assert result["estimated_duration"] == "10-12 dias aprox"
    assert result["trend_duration"] == "1-3 meses aprox"


def test_lateral_floor_to_ceiling_channel_duration():
    result = channel_duration_for("lateral", "canal alcista piso a techo")

    assert result["trend_regime"] == "LATERAL"
    assert result["estimated_duration"] == "10-12 dias aprox"


def test_blocked_higher_timeframe_blocks_15m_trigger():
    context = build_multitimeframe_context(
        {
            "symbol": "AAPL",
            "timeframe": "15m",
            "strategy_family": "Pullback",
            "higher_tf_bias": "BLOCKED",
            "higher_tf_blocks": 2,
        }
    )

    assert context["alignment"] == "BLOCKED"
    assert "No operar" in context["action_bias"]
    assert "15m" in context["explanation"]


def test_multitimeframe_checks_include_channel_duration():
    checks = multitimeframe_condition_checks(
        {"strategy_family": "Canal alcista", "timeframe": "1d", "higher_tf_bias": "CONFIRMED"}
    )

    labels = {item["label"] for item in checks}
    assert "Canal mayor" in labels
    assert "Duracion canal" in labels
    assert all("passed" in item for item in checks)
