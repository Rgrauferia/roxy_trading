import pandas as pd

from roxy_ai import build_strategy_lab
from salto_strategies import (
    SALTO_STRATEGIES,
    SALTO_STRATEGY_FAMILIES,
    apply_learned_strategy_brain,
    detect_salto_setups,
)
from symbol_detail import prepare_symbol_chart_data
from trade_brief import CORE_STRATEGIES, build_symbol_trade_brief, strategy_family_from_setup


def _sample_chart() -> pd.DataFrame:
    rows = []
    for idx in range(240):
        close = 50.0 + idx * 0.22
        rows.append(
            {
                "ts": pd.Timestamp("2026-01-01") + pd.to_timedelta(idx, unit="h"),
                "open": close - 0.05,
                "high": close + 0.15,
                "low": close - 0.20,
                "close": close,
                "volume": 1_000_000 + idx * 1_000,
            }
        )
    return prepare_symbol_chart_data(pd.DataFrame(rows))


def test_salto_families_are_core_strategies():
    assert set(SALTO_STRATEGY_FAMILIES).issubset(set(CORE_STRATEGIES))


def test_strategy_family_from_setup_maps_salto_keys():
    assert strategy_family_from_setup("SALTO_MA_DISTANCE") == "Salto por distancia entre medias moviles"
    assert strategy_family_from_setup("Salto por ruptura de maximos historicos") == "Salto por ruptura de maximos historicos"
    assert strategy_family_from_setup("PATRON_IMPARABLE_EMA9") == "Patron imparable EMA9"
    assert strategy_family_from_setup("Patron imparable") == "Patron imparable EMA9"
    assert strategy_family_from_setup("REBOTE_EN_MEDIA") == "Busqueda de media movil con confirmacion"


def test_detect_salto_setups_from_chart_data():
    rows = detect_salto_setups(_sample_chart(), {"setup": "TREND_CONTINUATION", "signal": "WATCH"})

    active_or_watch = {row["family"] for row in rows if row["status"] in {"ACTIVE", "WATCH"}}
    assert "Salto por distancia entre medias moviles" in active_or_watch
    assert all(row["requirements"] for row in rows)
    assert all("15m" in row["confirmation_timeframes"] for row in rows)


def test_salto_definitions_include_masterclass_checklists():
    assert len(SALTO_STRATEGIES) >= 7
    for strategy in SALTO_STRATEGIES:
        assert len(strategy.requirements) >= 6
        assert strategy.confirmation_timeframes
        assert strategy.direction
    assert "Patron imparable EMA9" in SALTO_STRATEGY_FAMILIES
    assert "Busqueda de media movil con confirmacion" in SALTO_STRATEGY_FAMILIES


def test_detects_media_rebound_as_learned_strategy():
    chart = _sample_chart()
    last_idx = chart.index[-1]
    sma20 = float(chart.loc[last_idx, "sma20"])
    sma40 = float(chart.loc[last_idx, "sma40"])
    chart.loc[last_idx, "open"] = sma20 * 0.997
    chart.loc[last_idx, "low"] = min(sma20, sma40) * 0.995
    chart.loc[last_idx, "close"] = sma20 * 1.006
    chart.loc[last_idx, "high"] = sma20 * 1.012
    chart.loc[last_idx, "relative_volume"] = 1.25

    rows = detect_salto_setups(chart, {"setup": "PULLBACK", "signal": "WATCH"})
    rebound = next(row for row in rows if row["family"] == "Busqueda de media movil con confirmacion")

    assert rebound["status"] in {"ACTIVE", "WATCH"}
    assert "cierre confirmado" in rebound["trigger"].lower()
    assert rebound["direction"] == "rebound"


def test_symbol_trade_brief_respects_explicit_salto_family():
    brief = build_symbol_trade_brief(
        symbol="NVDA",
        market="stock",
        timeframe="1h",
        setup={
            "signal": "WATCH",
            "setup": "TREND_CONTINUATION",
            "strategy_family": "SALTO_ATH_BREAKOUT",
            "entry": 100,
            "stop": 97,
            "score": 68,
            "backtest_eligible": True,
        },
        confluence={"signal": "WATCH", "trade_decision": "WAIT", "recommended_target_pct": 0.02},
    )

    assert brief["strategy_family"] == "Salto por ruptura de maximos historicos"
    assert "Regla de salto" in " ".join(brief["strategy_explanation"])
    assert brief["multitimeframe"]["alignment"] == "UNKNOWN"


def test_learned_strategy_brain_enriches_trade_brief():
    chart = _sample_chart()
    setup = apply_learned_strategy_brain(
        chart,
        {
            "signal": "WATCH",
            "setup": "TREND_CONTINUATION",
            "entry": 100,
            "stop": 97,
            "score": 60,
            "backtest_eligible": True,
        },
    )
    brief = build_symbol_trade_brief(
        symbol="AMD",
        market="stock",
        timeframe="1h",
        setup=setup,
        confluence={"signal": "WATCH", "trade_decision": "WAIT", "recommended_target_pct": 0.02},
    )

    assert setup["learned_strategy_status"] in {"ACTIVE", "WATCH"}
    assert brief["learned_strategy"]["name"].startswith("Salto")
    assert "Cerebro aprendido" in " ".join(brief["strategy_explanation"])
    assert "Multitemporal" in " ".join(brief["strategy_explanation"])
    assert any("Estrategia aprendida" in reason for reason in brief["reasons"])


def test_trade_brief_flags_checklist_no_negotiables():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="1h",
        setup={
            "signal": "BUY",
            "setup": "TREND_CONTINUATION",
            "open": 100,
            "high": 111,
            "low": 99,
            "close": 110,
            "entry": 110,
            "stop": 107,
            "bb_upper": 108,
            "bb_lower": 95,
            "sma20": 102,
            "sma40": 100,
            "sma100": 97,
            "sma200": 94,
            "score": 80,
            "backtest_eligible": True,
        },
        confluence={"signal": "BUY", "trade_decision": "TRADE_FOR_2PCT", "recommended_target_pct": 0.02},
    )

    checks = {item["label"]: item for item in brief["condition_checks"]}
    assert checks["No expuesto Bollinger"]["passed"] is False
    assert checks["No vela llena"]["passed"] is False
    assert any("No negociable" in blocker for blocker in brief["blockers"])


def test_trade_brief_blocks_micro_timeframe_without_parent_confirmation():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="1m",
        setup={
            "signal": "BUY",
            "setup": "TREND_CONTINUATION",
            "entry": 100,
            "stop": 98,
            "score": 80,
            "backtest_eligible": True,
        },
        confluence={
            "signal": "BUY",
            "trade_decision": "WAIT",
            "recommended_target_pct": 0.02,
            "risk_pct": 0.02,
            "relative_volume_15m": 1.2,
        },
    )

    checks = {item["label"]: item for item in brief["condition_checks"]}
    assert brief["action"] != "BUY_STOCK"
    assert checks["1m/5m solo timing"]["passed"] is False
    assert any("1m/5m solo sirve" in blocker for blocker in brief["blockers"])
    assert "1m/5m no decide" in " ".join(brief["reasons"])


def test_trade_brief_blocks_bad_reward_risk_even_when_setup_confirms():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="1h",
        setup={
            "signal": "BUY",
            "setup": "TREND_CONTINUATION",
            "entry": 100,
            "stop": 97,
            "score": 85,
            "backtest_eligible": True,
        },
        confluence={
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_2PCT",
            "recommended_target_pct": 0.02,
            "risk_pct": 0.03,
            "relative_volume_15m": 1.3,
            "trend_score": 82,
            "trigger_score": 75,
            "backtest_eligible": True,
        },
    )

    checks = {item["label"]: item for item in brief["condition_checks"]}
    assert brief["action"] != "BUY_STOCK"
    assert checks["Reward/Risk viable"]["passed"] is False
    assert checks["Reward/Risk viable"]["detail"] == "0.67R"
    assert any("Reward/risk no compensa" in blocker for blocker in brief["blockers"])


def test_trade_brief_blocks_fed_event_without_strong_confirmation():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="1h",
        setup={
            "signal": "BUY",
            "setup": "TREND_CONTINUATION",
            "entry": 200,
            "stop": 196,
            "score": 82,
            "backtest_eligible": True,
            "news_event": "FOMC statement and Powell press conference",
        },
        confluence={
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "recommended_target_pct": 0.05,
            "risk_pct": 0.02,
            "relative_volume_15m": 1.2,
            "trend_score": 80,
            "trigger_score": 74,
            "higher_tf_bias": "CONFIRMED",
            "higher_tf_confirmations": 2,
            "backtest_eligible": True,
        },
    )

    checks = {item["label"]: item for item in brief["condition_checks"]}
    assert brief["action"] != "BUY_STOCK"
    assert brief["macro_event_risk"]["active"] is True
    assert checks["Evento FED/macro"]["passed"] is False
    assert any("Evento FED/macro activo" in blocker for blocker in brief["blockers"])


def test_trade_brief_blocks_chasing_extended_sma20_move():
    brief = build_symbol_trade_brief(
        symbol="NVDA",
        market="stock",
        timeframe="1h",
        setup={
            "signal": "BUY",
            "setup": "TREND_CONTINUATION",
            "entry": 120,
            "stop": 118,
            "close": 120,
            "sma20": 100,
            "sma40": 96,
            "score": 90,
            "backtest_eligible": True,
        },
        confluence={
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "recommended_target_pct": 0.05,
            "risk_pct": 0.016,
            "relative_volume_15m": 1.4,
            "trend_score": 85,
            "trigger_score": 78,
            "backtest_eligible": True,
        },
    )

    checks = {item["label"]: item for item in brief["condition_checks"]}
    assert brief["action"] != "BUY_STOCK"
    assert checks["No perseguir extension"]["passed"] is False
    assert any("No perseguir extension" in blocker for blocker in brief["blockers"])


def test_trade_brief_blocks_bullish_setup_that_lost_sma40():
    brief = build_symbol_trade_brief(
        symbol="MSFT",
        market="stock",
        timeframe="1h",
        setup={
            "signal": "BUY",
            "setup": "PULLBACK",
            "entry": 98,
            "stop": 96,
            "close": 98,
            "sma20": 101,
            "sma40": 100,
            "score": 82,
            "backtest_eligible": True,
        },
        confluence={
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "recommended_target_pct": 0.05,
            "risk_pct": 0.02,
            "relative_volume_15m": 1.2,
            "trend_score": 80,
            "trigger_score": 76,
            "backtest_eligible": True,
        },
    )

    checks = {item["label"]: item for item in brief["condition_checks"]}
    assert brief["action"] != "BUY_STOCK"
    assert checks["SMA40 sostiene canal"]["passed"] is False
    assert any("SMA40 sostiene canal" in blocker for blocker in brief["blockers"])


def test_roxy_lab_lists_salto_families_without_memory():
    rows = build_strategy_lab({"strategy_stats": {}, "signal_journal": []})
    families = {row["strategy_family"] for row in rows}

    assert set(SALTO_STRATEGY_FAMILIES).issubset(families)
