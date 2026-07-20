import inspect
from pathlib import Path
from types import SimpleNamespace

import streamlit_app


def test_operational_styles_exclude_academy_and_auth_payload_only_when_authenticated():
    markup = (
        "<style>.core{color:white}"
        ".roxy-academy-shell{display:grid}.roxy-auth-screen{display:block}"
        '[data-testid="stTabs"] button{font-weight:800}</style>'
    )

    operational = streamlit_app.operational_style_payload(markup, include_academy_auth=False)
    full = streamlit_app.operational_style_payload(markup, include_academy_auth=True)

    assert ".core{color:white}" in operational
    assert ".roxy-academy-shell" not in operational
    assert ".roxy-auth-screen" not in operational
    assert '[data-testid="stTabs"] button' in operational
    assert full == markup


def test_modular_style_resources_round_trip_exact_route_payloads():
    streamlit_app.roxy_application_style_markup.cache_clear()
    full = streamlit_app.roxy_application_style_markup(include_academy_auth=True)
    operational = streamlit_app.roxy_application_style_markup(include_academy_auth=False)

    assert full.lstrip().startswith("<style>")
    assert full.rstrip().endswith("</style>")
    assert streamlit_app.ACADEMY_AUTH_STYLE_START in full
    assert streamlit_app.ACADEMY_AUTH_STYLE_START not in operational
    assert streamlit_app.ACADEMY_AUTH_STYLE_END in operational
    assert streamlit_app.operational_style_payload(full, include_academy_auth=False) == operational
    assert len(full) > len(operational) + 500_000


def test_main_no_longer_embeds_the_application_stylesheet():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    main = source[source.index("def main()") :]

    assert 'roxy_style_markup = """' not in main
    assert "roxy_application_style_markup(" in main
    assert source.count(".roxy-academy-shell{") == 1  # only the split marker constant remains


def test_startup_profiler_requires_signed_diagnostic_session(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        streamlit_app,
        "st",
        SimpleNamespace(query_params={"profile_startup": "1"}, session_state={}),
    )

    streamlit_app.render_with_diagnostic_profile(lambda: calls.append("rendered"))

    assert calls == ["rendered"]


def test_heavy_voice_and_security_payloads_are_scoped_to_consumer_pages():
    assert "Activo" in streamlit_app.ROXY_VOICE_FOCUSED_PAGES
    assert "Roxy IA" in streamlit_app.ROXY_VOICE_FOCUSED_PAGES
    assert "Backtest" not in streamlit_app.ROXY_VOICE_FOCUSED_PAGES
    assert "Diagnostico" not in streamlit_app.ROXY_VOICE_FOCUSED_PAGES
    assert streamlit_app.ROXY_SECURITY_FOCUSED_PAGES == {"Plataformas", "Roxy IA", "Diagnostico"}


def test_width_compat_prefers_current_streamlit_width_contract():
    normalized = streamlit_app._streamlit_width_kwargs(
        {"use_container_width": True},
        supports_width=True,
        supports_container_width=True,
    )
    assert normalized == {"width": "stretch"}

    current = streamlit_app._streamlit_width_kwargs(
        {"width": "content"},
        supports_width=True,
        supports_container_width=True,
    )
    assert current == {"width": "content"}


def test_main_resolves_authentication_before_selecting_style_payload():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    main = source[source.index("def main()") :]

    assert main.index("roxy_restore_user_from_session()") < main.index("roxy_style_markup =")
    assert main.index("roxy_restore_diagnostic_probe_session()") < main.index("roxy_style_markup =")


def test_legacy_modules_resolve_to_real_surfaces():
    expected = {
        "watchlist": ("Dashboard", "acciones-operar", "watchlists"),
        "scanner": ("Dashboard", "acciones-operar", "escaner"),
        "alertas": ("Dashboard", "acciones-operar", "alertas"),
        "historial": ("Precision", "acciones-operar", "reportes"),
        "progreso": ("Precision", "acciones-operar", "reportes"),
        "portafolio": ("Capital", "acciones-operar", "resumen"),
        "opciones": ("Opciones", "acciones-operar", "resumen"),
    }

    for legacy_module, route_values in expected.items():
        route = streamlit_app.roxy_legacy_module_route(legacy_module)
        assert route is not None
        assert (route["page"], route["module"], route["tab"]) == route_values
        assert streamlit_app.normalize_roxy_module(legacy_module) == route_values[1]


def test_explicit_tab_wins_over_legacy_module_default():
    params = {"module": "watchlist", "tab": "analisis"}

    assert streamlit_app.roxy_actions_tab_from_query(params) == "analisis"


def test_legacy_module_supplies_tab_when_link_does_not_have_one():
    assert streamlit_app.roxy_actions_tab_from_query({"module": "watchlist"}) == "watchlists"
    assert streamlit_app.roxy_actions_tab_from_query({"module": "scanner"}) == "escaner"
    assert streamlit_app.roxy_actions_tab_from_query({"module": "alertas"}) == "alertas"


def test_legacy_page_links_resolve_without_silent_dashboard_fallback():
    assert streamlit_app.normalize_focused_page("Portafolio") == "Capital"
    assert streamlit_app.normalize_focused_page("Aprender") == "Estudios"
    assert streamlit_app.normalize_focused_page("Configuracion") == "Diagnostico"


def test_professional_route_registry_builds_canonical_links_and_rejects_unknown_routes():
    assert streamlit_app.roxy_route_href("market.news") == "?view=Noticias"
    assert streamlit_app.roxy_route_href("market.calendar") == "?view=Calendario"
    assert streamlit_app.roxy_route_href("trading.alerts") == "?view=Alertas"
    assert streamlit_app.roxy_route_href("roxy.notifications") == "?view=Notificaciones"
    assert streamlit_app.roxy_route_href("roxy.activity") == "?view=Actividad"
    assert streamlit_app.roxy_route_href("roxy.memory") == "?view=Memoria"
    assert streamlit_app.roxy_route_href("trading.watchlists") == (
        "?view=Dashboard&module=acciones-operar&tab=watchlists"
    )
    assert streamlit_app.roxy_route_href(
        "trading.charts", symbol="BTC/USD", market="crypto", tf="15m"
    ) == "?view=Dashboard&module=acciones-operar&tab=analisis&symbol=BTC%2FUSD&market=crypto&tf=15m"

    try:
        streamlit_app.roxy_route_href("missing.route")
    except KeyError as exc:
        assert "missing.route" in str(exc)
    else:
        raise AssertionError("Una ruta desconocida no debe caer silenciosamente al Dashboard")


def test_canonical_dual_chart_workspace_preserves_crypto_market_end_to_end():
    source = inspect.getsource(streamlit_app.main)
    folder = inspect.getsource(streamlit_app.render_roxy_actions_folder)
    terminal = inspect.getsource(streamlit_app.render_roxy_actions_reference_market_terminal)

    assert 'roxy_selected_asset_row(actions_symbol, actions_market)' in source
    assert 'first_query_param_value(st.query_params, "market")' in source
    assert 'roxy_asset_rows_for_market(table, requested_market' in folder
    assert 'default_market=requested_market' in folder
    assert 'market=selected_market' in folder
    assert 'if selected_market == "stock"' in folder
    assert "roxy_live_stock_symbols(rows" in folder
    assert "if live_stock_symbols:" in terminal

    crypto_row = streamlit_app.roxy_selected_asset_row("ETH/USD", "crypto")
    rows = streamlit_app.roxy_asset_rows_for_market(
        streamlit_app.pd.DataFrame([crypto_row]), "crypto", limit=12
    )
    assert [(row["symbol"], row["market"]) for row in rows] == [("ETH/USD", "crypto")]
    assert streamlit_app.roxy_live_stock_symbols(rows) == []
    assert streamlit_app.roxy_live_stock_symbols(
        [{"symbol": "AAPL", "market": "stock"}, {"symbol": "BTC/USD", "market": "crypto"}]
    ) == ["AAPL"]
    assert streamlit_app.normalize_watchlist_symbol("eth-usd") == "ETH/USD"


def test_primary_navigation_uses_only_registered_operational_routes():
    html = streamlit_app.roxy_primary_navigation_html(
        "market.crypto_2h", symbol="ETH/USD", market="crypto", tf="2h"
    )

    assert html.count('class="active"') == 1
    assert "?view=Dashboard&amp;module=crypto-2h" in html
    assert "?view=Dashboard&amp;module=acciones-operar&amp;tab=watchlists" in html
    assert "module=watchlist" not in html
    assert "view=Configuracion" not in html
    assert html.count("symbol=ETH%2FUSD") == len(streamlit_app.ROXY_PRIMARY_NAVIGATION)
    assert html.count("market=crypto") == len(streamlit_app.ROXY_PRIMARY_NAVIGATION)
    assert html.count("tf=2h") == len(streamlit_app.ROXY_PRIMARY_NAVIGATION)


def test_crypto_20m_workspace_preserves_the_requested_20m_timeframe():
    workspace_source = inspect.getsource(streamlit_app.render_roxy_module_workspace)
    folder_source = inspect.getsource(streamlit_app.render_roxy_crypto20_folder)

    assert 'render_roxy_crypto20_folder(table, timeframe=timeframe or "20m")' in workspace_source
    assert 'default_timeframe=timeframe or "20m"' in folder_source
    assert '"20m"' in folder_source
    assert "tf=selected_timeframe" in folder_source
    assert streamlit_app.normalize_command_timeframe("20m") == "20m"


def test_every_focused_page_has_one_canonical_registered_route():
    assert set(streamlit_app.ROXY_FOCUSED_PAGE_ROUTES) == set(streamlit_app.FOCUSED_PAGE_LABELS)

    for page in streamlit_app.FOCUSED_PAGE_LABELS:
        route_id = streamlit_app.roxy_route_id_for_focused_page(page)
        assert route_id in streamlit_app.ROXY_ROUTE_REGISTRY
        assert streamlit_app.roxy_route_href(route_id).startswith("?view=")
        assert streamlit_app.roxy_focused_page_label(page)


def test_news_and_calendar_aliases_resolve_to_canonical_focused_pages():
    assert streamlit_app.normalize_focused_page("News") == "Noticias"
    assert streamlit_app.normalize_focused_page("Calendar") == "Calendario"


def test_crypto_bottom_navigation_uses_canonical_real_surfaces():
    html = streamlit_app.roxy_bottom_navigation_html(
        "market.crypto_20m", symbol="BTC/USD", market="crypto", tf="1m"
    )

    assert html.count('class="active"') == 1
    assert "module=crypto-20m" in html
    assert "view=Roxy%20IA" in html
    assert "view=Precision" in html
    assert "module=progreso" not in html
    assert "Classes Room" not in html


def test_actions_tabs_are_rendered_from_registered_routes():
    html = streamlit_app.roxy_actions_tabs_html("analisis", symbol="AAPL", market="stock", tf="15m")

    assert html.count('class="active"') == 1
    assert "tab=analisis" in html
    assert "tab=dividendos" in html
    assert "tab=mapa" in html
    assert "symbol=AAPL" in html
    assert all(route_id in streamlit_app.ROXY_ROUTE_REGISTRY for _, route_id in streamlit_app.ROXY_ACTIONS_TAB_ROUTES)


def test_market_map_and_news_links_do_not_fall_back_to_scanner():
    assert streamlit_app.roxy_route_href("market.stocks_map") == (
        "?view=Dashboard&module=acciones-operar&tab=mapa"
    )
    source = inspect.getsource(streamlit_app.render_roxy_actions_reference_market_terminal)
    assert 'tab=noticias' not in source
    assert 'roxy_route_href("market.news")' in source or "roxy_route_href('market.news')" in source


def test_education_navigation_does_not_link_to_unknown_or_wrong_surfaces():
    academy = inspect.getsource(streamlit_app.render_roxy_academy_module)
    classroom = inspect.getsource(streamlit_app.render_roxy_classroom_module)

    assert "?view=Settings" not in academy
    assert "roxy_route_href(\"system.integrations\")" in academy
    assert "roxy_route_href('trading.portfolio')" in academy
    assert "module=acciones-operar&tab=escaner" not in classroom
    assert "roxy_route_href('trading.performance')" in classroom


def test_dead_legacy_market_news_and_prototype_simulator_stay_removed():
    source = open("streamlit_app.py", encoding="utf-8").read()

    assert "def show_market_tab(" not in source
    assert "def show_news_tab(" not in source
    assert "Generate Grok suggestion" not in source
    assert "Voice Assistant (prototype)" not in source
    assert not (Path(__file__).resolve().parents[1] / "grok_integration.py").exists()
    assert not (Path(__file__).resolve().parents[1] / "grok_control.py").exists()
    assert "ENABLE_GROK_CODE_FAST" not in source
    assert "equity = 10000.0" not in source
    assert "def load_latest_tech_df(" not in source
    assert "def read_latest_alert_text(" not in source
    assert "def show_sma_strategy_tab(" not in source
    assert "def render_alert_noise_contract(" not in source
    assert "def show_sma_symbol_analyzer(" not in source
    assert "def render_center_decision_board(" not in source
    assert "def render_real_opportunity_panel(" not in source
    assert "def render_focus_opportunity_chart(" not in source
    assert "def render_roxy_actions_symbol_search(" not in source
    assert "def render_roxy_actions_reference_visual_lock(" not in source
    assert "def render_roxy_options_module(" not in source
