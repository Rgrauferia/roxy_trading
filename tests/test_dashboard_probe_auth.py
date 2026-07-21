from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit_app
from tools.dashboard_render_probe import (
    collect_rendered_text,
    diagnostic_probe_token,
    url_with_diagnostic_probe_token,
    url_without_diagnostic_probe_token,
    visible_view_from_text,
)


def _streamlit_source() -> str:
    return "\n".join(
        (
            Path("streamlit_app.py").read_text(encoding="utf-8"),
            Path("assets/runtime/roxy_elevenlabs_assistant.js.html").read_text(encoding="utf-8"),
        )
    )


class _FakeLocator:
    def __init__(self, text):
        self.text = text

    def inner_text(self, timeout):
        return self.text


class _FakeFrame:
    def __init__(self, text):
        self.text = text

    def locator(self, selector):
        assert selector == "body"
        return _FakeLocator(self.text)


class _FakePage:
    def __init__(self, frame_texts):
        self.frames = [_FakeFrame(text) for text in frame_texts]

    def locator(self, selector):
        return _FakeLocator("fallback")


def test_visible_view_from_text_is_case_insensitive_for_branded_routes():
    assert visible_view_from_text("ROXY\nACADEMY\n", "Academy") == "Academy"


def test_dashboard_probe_token_is_short_lived_and_verified_by_streamlit(tmp_path):
    secret_path = tmp_path / "dashboard_probe_secret"
    token = diagnostic_probe_token(secret_path=secret_path, now=1_800_000_000)

    assert streamlit_app.roxy_verify_diagnostic_probe_token(
        token,
        secret_path=secret_path,
        now=1_800_000_100,
    )
    assert not streamlit_app.roxy_verify_diagnostic_probe_token(
        token,
        secret_path=secret_path,
        now=1_800_000_400,
    )
    assert not streamlit_app.roxy_verify_diagnostic_probe_token(
        token + "tampered",
        secret_path=secret_path,
        now=1_800_000_100,
    )
    assert secret_path.stat().st_mode & 0o777 == 0o600


def test_dashboard_probe_adds_auth_only_to_navigation_url(tmp_path):
    secret_path = tmp_path / "dashboard_probe_secret"
    public_url = "http://127.0.0.1:3000/?view=Dashboard&symbol=AAPL"

    navigation_url = url_with_diagnostic_probe_token(
        public_url,
        secret_path=secret_path,
        now=1_800_000_000,
    )
    query = parse_qs(urlsplit(navigation_url).query)

    assert "rx_probe" not in parse_qs(urlsplit(public_url).query)
    assert len(query["rx_probe"][0]) > 80
    assert query["view"] == ["Dashboard"]
    assert query["symbol"] == ["AAPL"]


def test_diagnostic_probe_auth_keeps_session_stable_and_reports_public_url():
    source = _streamlit_source()
    restore = source[
        source.index("def roxy_restore_diagnostic_probe_session") : source.index("def render_roxy_browser_session_bridge")
    ]
    assert "del st.query_params" not in restore
    assert "roxy_diagnostic_probe" in restore
    public_url = url_without_diagnostic_probe_token(
        url_with_diagnostic_probe_token("http://127.0.0.1:3000/?view=Dashboard&symbol=AAPL")
    )
    assert "rx_probe" not in public_url
    assert parse_qs(urlsplit(public_url).query)["symbol"] == ["AAPL"]


def test_dashboard_probe_collects_component_iframe_text_without_duplicates():
    page = _FakePage(["Dashboard exterior", "Plan pendiente\nEntrada Pendiente", "Dashboard exterior"])

    text = collect_rendered_text(page)

    assert text.count("Dashboard exterior") == 1
    assert "Plan pendiente" in text


def test_voice_cleanup_never_hides_document_root_or_body():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "node === doc.body || node === doc.documentElement" in assistant_source
    assert "candidate === doc.body" in assistant_source
    assert 'node.removeAttribute("data-roxy-legacy-voice")' in assistant_source


def test_voice_cleanup_does_not_scan_every_roxy_component_as_voice_ui():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "[class*='roxy'],[id*='roxy']" not in assistant_source
    assert "[class*='roxy'][class*='voice']" in assistant_source


def test_opening_stage_has_no_fixed_market_or_trade_numbers():
    source = _streamlit_source()
    opening_source = source[
        source.index("def render_roxy_opening_stage") : source.index("def render_roxy_first_screen_launchpad")
    ]

    for fake_value in ("5,278.40", "16,735.02", "38,991.12", "194.50", "190.20", "201.80", "9:02 AM"):
        assert fake_value not in opening_source
    assert "Sin lectura se muestra como estado, no como precio" in opening_source
    assert "La fuente de velas se muestra en la grafica" in opening_source
    assert "for row in all_opportunity_rows" in opening_source
    assert "Capital paper ${equity:,.2f} · sin broker" in opening_source
    assert "roxy_hologram_avatar_html" not in opening_source
    assert 'class="roxy-prof-home"' in opening_source


def test_opening_stage_mobile_prioritizes_chart_and_persistent_navigation():
    source = _streamlit_source()
    opening_source = source[
        source.index("def render_roxy_opening_stage") : source.index("def render_roxy_first_screen_launchpad")
    ]

    assert ".roxy-prof-grid:nth-of-type(2){{order:2}}" in opening_source
    assert ".roxy-prof-status{{order:3;grid-template-columns:repeat(2" in opening_source
    assert ".roxy-prof-links{{order:6;position:fixed" in opening_source
    assert "min-height:46px" in opening_source
    nav_source = opening_source[opening_source.index('<nav class="roxy-prof-links"') :]
    assert nav_source.count('class="material-symbols-outlined"') == 5
    assert "trading.opportunities" in opening_source
    assert "trading.watchlists" in opening_source
    assert "trading.alerts" in opening_source


def test_roxy_os_debug_panel_is_scoped_to_roxy_and_diagnostics_pages():
    source = _streamlit_source()
    main_source = source[source.index("def main()") :]

    assert 'roxy_os_page in {"Roxy IA", "Diagnostico"}' in main_source


def test_crypto_modules_render_directly_without_waiting_for_dashboard_scan():
    source = _streamlit_source()
    main_source = source[source.index("def main()") :]
    direct = main_source[
        main_source.index('if active_module_query in {"crypto-20m", "crypto-2h", "crypto-daily"}') :
        main_source.index("render_roxy_browser_session_bridge()", main_source.index('if active_module_query in {"crypto-20m", "crypto-2h", "crypto-daily"}') + 1)
    ]

    assert 'pd.DataFrame([roxy_selected_asset_row(crypto_symbol, "crypto")])' in main_source
    assert "render_roxy_module_workspace(" in main_source
    assert "show_focused_roxy_app()" not in direct
    assert "render_roxy_os_command_center()" in main_source


def test_voice_commands_and_feedback_run_before_direct_module_returns():
    source = _streamlit_source()
    main_source = source[source.index("def main()") :]

    command_index = main_source.index("process_roxy_os_query_command()")
    actions_index = main_source.index('if active_module_query in {"acciones-operar"')
    crypto_index = main_source.index('if active_module_query in {"crypto-20m"')

    assert command_index < actions_index < crypto_index
    assert 'st.session_state.pop("roxy_launch_message", "")' in main_source
    assert 'st.toast(command_feedback, icon="✅")' in main_source


def test_missing_voice_query_does_not_execute_placeholder_command(monkeypatch):
    calls = []
    monkeypatch.setattr(streamlit_app.st, "query_params", {})
    monkeypatch.setattr(streamlit_app.st, "session_state", {})
    monkeypatch.setattr(streamlit_app, "run_roxy_os_command", lambda command: calls.append(command))

    streamlit_app.process_roxy_os_query_command()

    assert calls == []


def test_empty_command_feedback_is_not_normalized_into_visible_dash():
    source = _streamlit_source()

    assert 'command_feedback = str(st.session_state.pop("roxy_launch_message", "") or "").strip()' in source
    assert 'default_command = str(st.session_state.pop("roxy_os_pending_command", "") or "").strip()' in source
    assert 'security_message = str(st.session_state.pop("roxy_account_security_message", "") or "").strip()' in source


def test_visible_url_asset_wins_over_stale_voice_session_context():
    context = streamlit_app.resolve_roxy_operational_context(
        {"symbol": "NVDA", "market": "stock", "tf": "15m"},
        {"command_symbol": "AAPL", "command_market": "crypto", "command_timeframe": "1h"},
    )

    assert context == {"symbol": "NVDA", "market": "stock", "timeframe": "15m"}


def test_voice_timeframe_command_recognizes_supported_spoken_ranges():
    cases = {
        "Roxy, cambia a la grafica de una hora": "1h",
        "pon la temporalidad en quince minutos": "15m",
        "muestra la grafica semanal": "1w",
        "cambiar timeframe a 4h": "4h",
    }

    for command, expected in cases.items():
        assert streamlit_app.timeframe_command_request(command) == {"timeframe": expected}


def test_voice_timeframe_command_does_not_intercept_unrelated_numbers():
    assert streamlit_app.timeframe_command_request("avisame si NVDA supera 150") is None
    assert streamlit_app.timeframe_command_request("explicame esta oportunidad") is None


def test_voice_timeframe_safe_action_updates_visible_platform_context(monkeypatch):
    calls = []
    monkeypatch.setattr(
        streamlit_app,
        "resolve_roxy_operational_context",
        lambda *_args: {"symbol": "NVDA", "market": "stock", "timeframe": "15m"},
    )
    monkeypatch.setattr(streamlit_app, "apply_roxy_navigation_target", lambda **kwargs: calls.append(kwargs))

    applied = streamlit_app.apply_roxy_os_safe_actions(
        {
            "ok": True,
            "actions": [
                {
                    "type": "set_timeframe",
                    "symbol": "NVDA",
                    "market": "stock",
                    "timeframe": "1h",
                    "confirmation_required": False,
                }
            ],
        }
    )

    assert applied == ["Cambiar grafica a 1h"]
    assert calls[0]["symbol"] == "NVDA"
    assert calls[0]["market"] == "stock"
    assert calls[0]["timeframe"] == "1h"


def test_voice_command_replay_guard_expires_instead_of_blocking_command_forever():
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    first = streamlit_app.roxy_voice_command_replay_state("Roxy, cambia a una hora", "", "", now=now)
    immediate = streamlit_app.roxy_voice_command_replay_state(
        "Roxy, cambia a una hora", first["key"], first["at"], now=now + timedelta(seconds=2)
    )
    later = streamlit_app.roxy_voice_command_replay_state(
        "Roxy, cambia a una hora", first["key"], first["at"], now=now + timedelta(seconds=8)
    )

    assert first["replay"] is False
    assert immediate["replay"] is True
    assert later["replay"] is False


def test_local_voice_explains_only_selected_visible_opportunity(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "roxy_elevenlabs_page_context",
        lambda: {"module": "acciones-operar", "symbol": "AAPL", "market": "stock", "timeframe": "15m"},
    )
    monkeypatch.setattr(
        streamlit_app,
        "roxy_resolved_voice_opportunity_snapshot",
        lambda: {
            "module": "acciones-operar",
            "rows": [
                {"symbol": "TSLA", "decision": "OPERAR", "price": "400", "confidence": "95"},
                {
                    "symbol": "AAPL",
                    "decision": "ESPERAR",
                    "price": "210",
                    "entry": "211",
                    "stop": "207",
                    "target": "219",
                    "confidence": "82",
                    "reason": "retroceso a EMA21",
                    "next_step": "cierre 15m sobre 211",
                },
            ],
        },
    )

    reply = streamlit_app.roxy_voice_local_context_reply("Roxy, explicame esta oportunidad")

    assert "oportunidad visible de AAPL" in reply
    assert "Temporalidad 15m" in reply
    assert "Confirmacion pendiente: cierre 15m sobre 211" in reply
    assert "TSLA" not in reply


def test_alert_panel_does_not_block_on_sequential_quotes_for_every_rule():
    source = _streamlit_source()
    panel = source[source.index("def render_roxy_alerts_panel") : source.index("def sync_roxy_operational_watchlist")]

    assert "for symbol in list(dict.fromkeys" not in panel
    assert "quote_payloads[selected_symbol]" in panel
    assert "alert_quote_gate(current_snapshot" in panel
    assert "record_alert_monitor_state" in panel
    assert "los demas permanecen a cargo del monitor operativo" in panel


def test_alerts_is_a_focused_fast_route_without_full_market_context():
    source = _streamlit_source()
    focused = source[source.index("def show_focused_roxy_app") : source.index("def main()")]

    assert "Alertas" in streamlit_app.FOCUSED_PAGE_LABELS
    assert streamlit_app.ROXY_ROUTE_REGISTRY["trading.alerts"]["view"] == "Alertas"
    assert '"Diagnostico", "Noticias", "Calendario", "Tareas", "Compras", "Hogar", "Documentos", "Correo", "Alertas"' in focused


def test_dashboard_probe_maps_personal_task_route_to_visible_label():
    from tools.dashboard_render_probe import visible_label_for_view

    assert visible_label_for_view("Tareas") == "Tareas personales"
    assert visible_label_for_view("Compras") == "Lista de compras"
    assert visible_label_for_view("Hogar") == "Roxy Home"
