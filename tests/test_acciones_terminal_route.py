import inspect

import streamlit_app as app


def test_acciones_direct_route_uses_reference_terminal_without_legacy_fallbacks():
    source = inspect.getsource(app.render_roxy_actions_operating_route)

    assert "render_roxy_actions_folder" in source
    assert "render_roxy_actions_folder_fast" not in source
    assert "render_roxy_asset_cards" not in source


def test_acciones_folder_always_shows_strategy_sections_and_headless_voice():
    source = inspect.getsource(app.render_roxy_actions_folder)

    assert "render_roxy_headless_voice_runtime()" in source
    assert "render_actions_reference_terminal_deploy(show_strategy_sections=True)" in source
    assert "render_roxy_actions_reference_market_terminal" in source
