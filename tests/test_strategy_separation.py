import ast
from pathlib import Path

from salto_strategies import (
    SALTO_KEY_TO_FAMILY,
    best_opportunities_by_strategy,
    separate_opportunities_by_strategy,
    strategy_family_for_opportunity,
)

ACTION_TERMINAL_TEMPLATE = Path("assets/runtime/roxy_actions_reference_terminal.html").read_text(
    encoding="utf-8"
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


def test_actions_folder_has_reference_command_center_and_operational_charts():
    app_source = Path("streamlit_app.py").read_text(encoding="utf-8")
    module = ast.parse(app_source)
    target_names = {
        "render_roxy_actions_command_center",
        "render_roxy_actions_reference_market_terminal",
        "render_roxy_actions_folder",
    }
    functions = {
        item.name: ast.get_source_segment(app_source, item) or ""
        for item in module.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name in target_names
    }
    wrapper = functions["render_roxy_actions_command_center"]
    terminal = functions["render_roxy_actions_reference_market_terminal"] + ACTION_TERMINAL_TEMPLATE
    folder = functions["render_roxy_actions_folder"]

    assert "render_roxy_actions_reference_market_terminal(" in wrapper
    assert len(wrapper.splitlines()) < 40
    assert "WatchlistStore(" in terminal
    assert "Estado de datos" in terminal
    assert "Escáner Finviz" in terminal
    assert "Mapa de Mercado" in terminal
    assert "Movers del Día" in terminal
    assert "Alertas Activas" in terminal
    assert "Tus Watchlists" in terminal
    assert "Finviz sin candidatos reales" in terminal
    assert "Roxy no inserta patrones, tickers, niveles ni puntuaciones" in terminal
    assert 'class="strategy-card strategy-empty"' not in terminal
    for strategy in ("Wedge Up", "Wedge Down", "Triangle Asc.", "Triangle Desc.", "Channel Up", "Channel Down"):
        assert strategy in terminal
    assert "render_finviz_pattern_strategy_board(limit=24)" in folder
    assert "render_roxy_strategy_split_board(rows, limit=12)" in folder
    assert "render_roxy_actions_dual_pro_charts" in folder
    for fake_value in ("Guardian Novato", "3,450 / 5,000 XP", 'Crude Oil", "72.22'):
        assert fake_value not in app_source


def test_active_actions_terminal_has_durable_state_real_routes_and_no_gamification():
    app_source = Path("streamlit_app.py").read_text(encoding="utf-8")
    module = ast.parse(app_source)
    node = next(
        item
        for item in module.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == "render_roxy_actions_reference_market_terminal"
    )
    source = (ast.get_source_segment(app_source, node) or "") + ACTION_TERMINAL_TEMPLATE

    assert "WatchlistStore(" in source
    assert "alerts_snapshot" in source
    assert "data_bucket\": \"Universe seed" not in source
    assert "Guardian Novato" not in source
    assert "Nivel 12" not in source
    assert "3,450 / 5,000 XP" not in source
    assert "Apple Inc." not in source
    assert 'roxy_route_href("trading.alerts"' in source
    assert "?view=Dashboard&module=acciones-operar&tab=alertas" not in source
    assert 'tab=watchlists" target="_self"' in source
    assert 'tab=movers" target="_self"' in source
    assert 'tab=mapa" target="_self"' in source


def test_strategy_empty_states_do_not_create_reference_opportunities():
    app_source = Path("streamlit_app.py").read_text(encoding="utf-8")
    module = ast.parse(app_source)
    functions = {
        item.name: ast.get_source_segment(app_source, item) or ""
        for item in module.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name in {"render_finviz_pattern_strategy_board", "render_roxy_strategy_split_board"}
    }

    finviz = functions["render_finviz_pattern_strategy_board"]
    split = functions["render_roxy_strategy_split_board"]

    assert "if not strategies:" in finviz
    assert "Roxy no inserta patrones, tickers, niveles ni puntuaciones de referencia" in finviz
    assert "reference_strategies" not in finviz
    assert '"symbol": "FINVIZ"' not in finviz
    assert "if not groups:" in split
    assert "0 detecciones" in split
    assert "Roxy no inserta familias, tickers, puntuaciones ni niveles de referencia" in split
    assert "fallback_families" not in split


def test_direct_asset_routes_do_not_expand_static_universe_seeds():
    app_source = Path("streamlit_app.py").read_text(encoding="utf-8")
    module = ast.parse(app_source)
    functions = {
        item.name: ast.get_source_segment(app_source, item) or ""
        for item in module.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name in {"roxy_selected_asset_row", "roxy_asset_rows_for_market", "roxy_crypto20_rows", "main"}
    }

    assert "roxy_fallback_asset_rows" not in app_source
    assert "Universe seed" not in app_source
    assert '"data_bucket": "User selection"' in functions["roxy_selected_asset_row"]
    assert "for row in source_rows:" in functions["roxy_crypto20_rows"]
    assert 'wanted = ["BTC/USD"' not in functions["roxy_crypto20_rows"]
    assert 'pd.DataFrame([roxy_selected_asset_row(actions_symbol, actions_market)])' in functions["main"]
    assert 'pd.DataFrame([roxy_selected_asset_row(crypto_symbol, "crypto")])' in functions["main"]
    assert 'first_query_param_value(st.query_params, "market")' in functions["main"]
