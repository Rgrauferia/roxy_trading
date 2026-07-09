from pathlib import Path

from salto_strategies import (
    SALTO_KEY_TO_FAMILY,
    best_opportunities_by_strategy,
    separate_opportunities_by_strategy,
    strategy_family_for_opportunity,
)


def test_strategy_family_classifier_keeps_sources_separate():
    assert (
        strategy_family_for_opportunity({"symbol": "AAPL", "strategy_family": "SALTO_EMA_HOURS"})
        == SALTO_KEY_TO_FAMILY["SALTO_EMA_HOURS"]
    )
    assert (
        strategy_family_for_opportunity({"symbol": "NVDA", "finviz_signal": "Triangle Asc."})
        == "Finviz: Triangulo ascendente"
    )
    assert (
        strategy_family_for_opportunity({"symbol": "MSFT", "canonical_pattern": "Channel Up"})
        == "Finviz: Canal alcista"
    )


def test_separate_opportunities_by_strategy_ranks_each_setup_independently():
    rows = [
        {"symbol": "AAPL", "strategy_family": "SALTO_EMA_HOURS", "score": 72},
        {"symbol": "TSLA", "strategy_family": "SALTO_EMA_HOURS", "score": 91},
        {"symbol": "NVDA", "finviz_signal": "Triangle Asc.", "confidence": 86},
        {"symbol": "AMD", "finviz_signal": "Triangle Asc.", "confidence": 78},
        {"symbol": "MSFT", "canonical_pattern": "Channel Up", "readiness": 81},
    ]

    groups = separate_opportunities_by_strategy(rows, limit_per_strategy=2)
    by_family = {group["strategy_family"]: group for group in groups}

    assert by_family[SALTO_KEY_TO_FAMILY["SALTO_EMA_HOURS"]]["best"]["symbol"] == "TSLA"
    assert by_family["Finviz: Triangulo ascendente"]["best"]["symbol"] == "NVDA"
    assert by_family["Finviz: Canal alcista"]["best"]["symbol"] == "MSFT"
    assert by_family["Finviz: Triangulo ascendente"]["count"] == 2


def test_best_opportunities_by_strategy_returns_one_per_strategy():
    rows = [
        {"symbol": "AAPL", "setup": "EMA 9/21", "score": 88},
        {"symbol": "MSFT", "setup": "EMA 9/21", "score": 80},
        {"symbol": "NVDA", "finviz_signal": "Double Bottom", "confidence": 84},
    ]

    best = best_opportunities_by_strategy(rows)
    families = {row["_strategy_family"] for row in best}

    assert "Estrategia: Cruce EMA 9/21" in families
    assert "Finviz: Doble piso" in families
    assert len(best) == 2


def test_actions_folder_keeps_finviz_patterns_as_separate_lanes():
    source = Path("streamlit_app.py").read_text()

    assert "def render_finviz_strategy_lanes" in source
    assert "render_finviz_strategy_lanes(limit_per_strategy=5)" in source
    assert "load_finviz_pattern_strategy_rows(limit=600)" in source
    assert "Sin candidatos live ahora" in source

    for label in [
        "TL Support",
        "Horizontal S/R",
        "Wedge",
        "Wedge Down",
        "Triangle Asc.",
        "Channel Up",
        "Double Bottom",
        "Multiple Top",
        "Head & Shoulders",
    ]:
        assert label in source

    for plan_label in ["Entrada", "Salida", "Stop"]:
        assert plan_label in source
