import pandas as pd

from roxy_ai import build_strategy_lab
from salto_strategies import SALTO_STRATEGIES, SALTO_STRATEGY_FAMILIES, detect_salto_setups
from symbol_detail import prepare_symbol_chart_data
from trade_brief import CORE_STRATEGIES, build_symbol_trade_brief, strategy_family_from_setup


def _sample_chart() -> pd.DataFrame:
    rows = []
    for idx in range(240):
        close = 50.0 + idx * 0.22
        rows.append(
            {
                "ts": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=idx),
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


def test_detect_salto_setups_from_chart_data():
    rows = detect_salto_setups(_sample_chart(), {"setup": "TREND_CONTINUATION", "signal": "WATCH"})

    active_or_watch = {row["family"] for row in rows if row["status"] in {"ACTIVE", "WATCH"}}
    assert "Salto por distancia entre medias moviles" in active_or_watch
    assert all(row["requirements"] for row in rows)
    assert all("15m" in row["confirmation_timeframes"] for row in rows)


def test_salto_definitions_include_masterclass_checklists():
    assert len(SALTO_STRATEGIES) >= 5
    for strategy in SALTO_STRATEGIES:
        assert len(strategy.requirements) >= 6
        assert strategy.confirmation_timeframes
        assert strategy.direction


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


def test_roxy_lab_lists_salto_families_without_memory():
    rows = build_strategy_lab({"strategy_stats": {}, "signal_journal": []})
    families = {row["strategy_family"] for row in rows}

    assert set(SALTO_STRATEGY_FAMILIES).issubset(families)
