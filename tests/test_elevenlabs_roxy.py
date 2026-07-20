import json
from pathlib import Path

from tools.elevenlabs_roxy import (
    DEFAULT_ELEVENLABS_AGENT_ID,
    ElevenLabsRoxySession,
    build_roxy_personalization,
    elevenlabs_agent_id,
    elevenlabs_env_fingerprint,
    get_conversation_token,
    get_conversation_signed_url,
    sanitize_mapping,
)
from roxy_trader.api_budget import ApiUsageLedger
import streamlit_app


def _streamlit_source() -> str:
    return "\n".join(
        (
            Path("streamlit_app.py").read_text(encoding="utf-8"),
            Path("assets/runtime/roxy_elevenlabs_assistant.js.html").read_text(encoding="utf-8"),
        )
    )


def test_voice_runtime_template_round_trip_and_escapes_inline_script_values():
    payload = {"userName": "</script><script>alert('x')</script>", "context": "A&B\u2028C"}

    markup = streamlit_app.roxy_elevenlabs_runtime_markup(
        voice_payload=payload,
        avatar_html="<svg onload=alert(1)></svg>",
    )

    assert "__ROXY_VOICE_PAYLOAD_JSON__" not in markup
    assert "__ROXY_AVATAR_MARKUP_JSON__" not in markup
    assert "</script><script>alert('x')</script>" not in markup
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert('x')\\u003c/script\\u003e" in markup
    assert "A\\u0026B\\u2028C" in markup
    assert "Conversation.startSession" in markup


def test_elevenlabs_agent_id_uses_existing_roxy_agent_by_default():
    assert elevenlabs_agent_id({}) == DEFAULT_ELEVENLABS_AGENT_ID


def test_signed_url_reports_missing_api_key_without_exposing_secret():
    session = get_conversation_signed_url(env={"ELEVENLABS_AGENT_ID": "agent_test"})

    assert session.configured is False
    assert session.agent_id == "agent_test"
    assert "ELEVENLABS_API_KEY" in session.error
    assert session.signed_url == ""
    assert session.state == "NOT_CONFIGURED"


def test_conversation_token_reports_missing_api_key_without_exposing_secret():
    session = get_conversation_token(env={"ELEVENLABS_AGENT_ID": "agent_test"})

    assert session.configured is False
    assert session.agent_id == "agent_test"
    assert "ELEVENLABS_API_KEY" in session.error
    assert session.conversation_token == ""
    assert session.state == "NOT_CONFIGURED"


def test_conversation_token_records_returned_rate_limit(tmp_path, monkeypatch):
    class Response:
        status_code = 429

        @staticmethod
        def json():
            return {}

    usage_path = tmp_path / "usage.sqlite"
    monkeypatch.setenv("ROXY_API_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("ROXY_API_USAGE_DB", str(usage_path))
    monkeypatch.setattr("tools.elevenlabs_roxy.requests.get", lambda *args, **kwargs: Response())

    session = get_conversation_token(
        env={"ELEVENLABS_AGENT_ID": "agent_test", "ELEVENLABS_API_KEY": "secret-value"}
    )
    summary = ApiUsageLedger(usage_path).provider_summary("elevenlabs")

    assert session.configured is False
    assert "429" in session.error
    assert session.state == "RATE_LIMITED"
    assert session.http_status == 429
    assert summary["rate_limited"] == 1
    assert "secret-value" not in str(summary)

    protected = get_conversation_token(
        env={"ELEVENLABS_AGENT_ID": "agent_test", "ELEVENLABS_API_KEY": "secret-value"}
    )
    protected_summary = ApiUsageLedger(usage_path).provider_summary("elevenlabs")

    assert protected.configured is False
    assert "cooldown activo" in protected.error
    assert protected_summary["requests"] == 1
    assert protected_summary["blocks"] == 1


def test_auth_invalid_opens_persistent_circuit_until_credentials_change(tmp_path, monkeypatch):
    class Response:
        status_code = 401

        @staticmethod
        def json():
            return {}

    calls = {"count": 0}

    def rejected(*args, **kwargs):
        calls["count"] += 1
        return Response()

    circuit_path = tmp_path / "elevenlabs_auth_circuit.json"
    env = {
        "ELEVENLABS_AGENT_ID": "agent_test",
        "ELEVENLABS_API_KEY": "secret-value",
        "ROXY_ELEVENLABS_AUTH_CIRCUIT_PATH": str(circuit_path),
        "ROXY_ELEVENLABS_AUTH_RETRY_SECONDS": "21600",
    }
    monkeypatch.setenv("ROXY_API_TELEMETRY_ENABLED", "0")
    monkeypatch.setattr("tools.elevenlabs_roxy.requests.get", rejected)

    first = get_conversation_token(env=env)
    protected = get_conversation_signed_url(env=env)

    assert first.state == "AUTH_INVALID"
    assert protected.state == "AUTH_INVALID"
    assert "circuit active" in protected.error
    assert calls["count"] == 1
    assert circuit_path.stat().st_mode & 0o777 == 0o600
    serialized = circuit_path.read_text(encoding="utf-8")
    assert "secret-value" not in serialized
    assert json.loads(serialized)["fingerprint"] == elevenlabs_env_fingerprint(env)

    changed = get_conversation_token(env={**env, "ELEVENLABS_API_KEY": "rotated-value"})

    assert changed.state == "AUTH_INVALID"
    assert calls["count"] == 2
    assert "rotated-value" not in circuit_path.read_text(encoding="utf-8")


def test_elevenlabs_env_fingerprint_changes_without_exposing_secret():
    first = elevenlabs_env_fingerprint({"ELEVENLABS_AGENT_ID": "agent_test", "ELEVENLABS_API_KEY": "key_one"})
    second = elevenlabs_env_fingerprint({"ELEVENLABS_AGENT_ID": "agent_test", "ELEVENLABS_API_KEY": "key_two"})

    assert first != second
    assert "key_one" not in first
    assert "key_two" not in second


def test_sanitize_mapping_removes_unapproved_and_secret_fields():
    payload = {
        "user_name": "Roberto",
        "watchlist": ["AAPL", "BTC"],
        "ELEVENLABS_API_KEY": "should-not-leak",
        "session_token": "should-not-leak",
        "password": "should-not-leak",
    }

    clean = sanitize_mapping(payload, ("user_name", "watchlist"))

    assert clean == {"user_name": "Roberto", "watchlist": ["AAPL", "BTC"]}
    assert "should-not-leak" not in str(clean)


def test_roxy_personalization_includes_risk_and_no_profit_guarantee_rules():
    personalization = build_roxy_personalization(
        {
            "user_name": "Roberto",
            "preferred_language": "es",
            "trading_level": "principiante",
            "risk_tolerance": "conservador",
        },
        {"page": "Dashboard", "module": "acciones-operar", "symbol": "AAPL", "timeframe": "1h"},
    )

    assert personalization["assistant_rules"]["display_name"] == "Roberto"
    assert personalization["context"]["symbol"] == "AAPL"
    must_do = " ".join(personalization["assistant_rules"]["must_do"])
    must_not = " ".join(personalization["assistant_rules"]["must_not_do"])
    assert "stop loss" in must_do
    assert "No prometer ganancias" in must_not


def test_streamlit_uses_single_elevenlabs_sdk_runtime_without_widget_duplicate():
    source = _streamlit_source()

    assert "https://esm.sh/@elevenlabs/client?bundle" in source
    assert "Conversation.startSession" in source
    assert "https://unpkg.com/@elevenlabs/convai-widget-embed" not in source
    assert "https://elevenlabs.io/convai-widget/index.js" not in source
    assert "elevenlabs-convai" not in source
    assert 'widget.setAttribute("dynamic-variables"' not in source


def test_streamlit_frontend_payload_does_not_include_api_key_secret():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "ELEVENLABS_API_KEY" not in assistant_source
    assert "conversationToken" in assistant_source
    assert "signedUrl" in assistant_source


def test_streamlit_roxy_voice_supports_hola_roxy_and_mobile_tap_activation():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "SpeechRecognition" in assistant_source
    assert "webkitSpeechRecognition" in assistant_source
    assert "Hola Roxy" in assistant_source
    assert "isWakePhrase" in assistant_source
    assert "Conversation.startSession" in assistant_source
    assert "roxy-el-button" not in assistant_source
    assert '[class*="roxy"][class*="voice"][class*="float"]' in assistant_source
    assert ".roxy-el-root.roxy-el-open .roxy-el-panel{display:grid!important}" in assistant_source
    assert 'root.classList.add("roxy-el-open");' in assistant_source
    assert 'wakeSurface.addEventListener("click", async function()' in assistant_source
    assert "Toca para hablar" in assistant_source


def test_streamlit_roxy_voice_prefers_webrtc_conversation_token():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    token_index = assistant_source.index("if (payload.conversationToken)")
    signed_url_index = assistant_source.index("options.signedUrl = payload.signedUrl")
    assert token_index < signed_url_index
    assert "https://cdn.jsdelivr.net/npm/@elevenlabs/client/+esm" in assistant_source
    assert "Roxy voz preparada" in assistant_source


def test_streamlit_voice_session_does_not_double_probe_invalid_credentials(monkeypatch):
    calls = {"token": 0, "signed": 0}

    def token_probe(*, agent_id):
        calls["token"] += 1
        return ElevenLabsRoxySession(
            agent_id=agent_id,
            configured=False,
            error="ElevenLabs token error 401",
            state="AUTH_INVALID",
            http_status=401,
        )

    def signed_probe(*, agent_id):
        calls["signed"] += 1
        raise AssertionError("signed URL must not retry a key already rejected with 401")

    monkeypatch.setattr(streamlit_app, "get_conversation_token", token_probe)
    monkeypatch.setattr(streamlit_app, "get_conversation_signed_url", signed_probe)
    streamlit_app.roxy_elevenlabs_signed_session_payload.clear()

    payload = streamlit_app.roxy_elevenlabs_signed_session_payload("agent_test", "invalid-key-fingerprint")

    assert calls == {"token": 1, "signed": 0}
    assert payload["configured"] is False
    assert payload["voice_mode"] == "unavailable"
    assert payload["state"] == "AUTH_INVALID"
    assert payload["http_status"] == 401


def test_streamlit_roxy_voice_does_not_fall_back_to_public_agent_id():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "else options.agentId = payload.agentId" not in assistant_source
    assert 'else throw new Error("Secure ElevenLabs session unavailable")' in assistant_source
    assert "startOptions.agentId = payload.agentId" not in assistant_source
    assert "const canUseSecureVoice = Boolean(payload.signedUrl || payload.conversationToken);" in assistant_source
    assert "if (!canUseSecureVoice)" in assistant_source
    assert '"voice_mode": voice_mode' in source
    assert '"agent_id_fallback"' not in source


def test_streamlit_roxy_voice_uses_local_brain_when_secure_voice_unavailable():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "Roxy voz preparada" in assistant_source
    assert 'payload.voiceMode === "unavailable"' in assistant_source
    assert "Roxy usara el cerebro local visible de la plataforma" in assistant_source
    assert "pendingText ||" in assistant_source
    assert '(!payload.agentId && payload.error) ? "roxy-el-status-error" : ""' in assistant_source


def test_streamlit_roxy_voice_retries_microphone_permission_from_page_tap():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "Toca la pantalla y acepta el microfono" not in assistant_source
    assert "armMicPermissionRetry" in assistant_source
    assert "armFallbackMicPermissionRetry" not in assistant_source


def test_streamlit_roxy_voice_avatar_surface_primes_microphone_from_mobile_tap():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert 'const wakeSurface = root.querySelector(".roxy-el-wake")' in assistant_source
    assert 'wakeSurface.addEventListener("click", async function()' in assistant_source
    assert 'wakeSurface.setAttribute("title", "Toca para hablar o di Hola Roxy")' in assistant_source
    assert "pointer-events:auto!important" in assistant_source
    assert "restartWakeListener();" in assistant_source
    assert 'wakeSurface.addEventListener("click", startRoxyConversation)' not in assistant_source
    assert "cursor:pointer" in assistant_source


def test_streamlit_roxy_voice_has_browser_speech_fallback():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "speechSynthesis" in assistant_source
    assert "SpeechSynthesisUtterance" in assistant_source
    assert "Roxy hablando" in assistant_source
    assert "ElevenLabs no conecto todavia" in assistant_source
    assert "temporaryVoicePrimed" not in assistant_source
    assert "conversation || win.__roxyVoiceConversation || payload.signedUrl" not in assistant_source


def test_streamlit_roxy_voice_routes_platform_context_through_local_roxy_brain_first():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "Roxy OS local proceso la instruccion" in assistant_source
    assert "async function speakThroughRoxyBrain(message, command)" in assistant_source
    assert "async function sendTextToSecureRoxy(message)" in assistant_source
    assert "return speakLocalRoxyReply(win.__roxyPendingHelperVoiceReply.text, true);" in assistant_source
    assert "return speakLocalRoxyReply(localReply, true);" in assistant_source
    assert "return speakLocalRoxyReply(wakeGreetingReply(), true);" in assistant_source
    assert "Roxy respondiendo con ElevenLabs" in assistant_source
    assert "roxy_trading_context_voice" in assistant_source
    assert "Roxy voz local preparada" in assistant_source


def test_streamlit_roxy_voice_has_no_direct_audio_test_button():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "roxyVoiceTestButton" not in assistant_source
    assert "components.html(voice_test_html" not in assistant_source
    assert "Probar voz de Roxy" not in assistant_source
    assert "Esta es una prueba temporal de voz" not in assistant_source
    assert "Audio OK" not in assistant_source
    assert "Wake word" in assistant_source or "wake-word" in assistant_source


def test_streamlit_roxy_voice_sends_platform_context_to_agent():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "voiceContextBrief" in assistant_source
    assert "Contexto obligatorio de esta sesion" in assistant_source
    assert "No hables de taxes" in assistant_source
    assert "ignorado en esta sesion" not in assistant_source
    assert "ignoralo en esta sesion salvo peticion explicita" in assistant_source
    assert "oportunidades, graficas, classroom, watchlist y riesgo" in assistant_source


def test_streamlit_roxy_voice_overrides_elevenlabs_agent_with_roxy_trading_brain():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "roxyConversationOverrides" in assistant_source
    assert "Identidad fija: eres Roxy Trading" in assistant_source
    assert "Nunca digas que ayudas con taxes" in assistant_source
    assert "usa solo los datos visibles enviados en el contexto" in assistant_source
    assert "sendContextualUpdate" in assistant_source
    assert "delete options.overrides" not in assistant_source
    assert "No pude iniciar voz de ElevenLabs con el cerebro de Roxy" in assistant_source


def test_streamlit_roxy_voice_registers_context_client_tools():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "function roxyClientTools()" in assistant_source
    assert '"userProfile": user_profile' in assistant_source
    assert '"opportunitySnapshot": voice_snapshot' in assistant_source
    assert '"visibleOpportunitiesText": voice_visible_opportunities' in assistant_source
    assert '"operationalResponseContract": voice_operational_contract' in assistant_source
    assert "getVisibleOpportunities" in assistant_source
    assert "getRoxyTradingDecision" in assistant_source
    assert "getCurrentScreenContext" in assistant_source
    assert "openRoxyModule" in assistant_source
    assert "sendCommandToRoxyOS: async function" in assistant_source
    assert "callRoxyDesktopHelper: async function" in assistant_source
    assert "summarizeCurrentScreen: async function" in assistant_source
    assert "openBrowserTarget: async function" in assistant_source
    assert "readLocalPath: async function" in assistant_source
    assert 'postDesktopHelper("/screen/summary"' in assistant_source
    assert 'postDesktopHelper("/browser/open"' in assistant_source
    assert 'postDesktopHelper("/file/read"' in assistant_source
    assert "desktopHelperUrl" in assistant_source
    assert "roxy_desktop_helper" in assistant_source
    assert "desktopActions: data.response.desktop_actions || []" in assistant_source
    assert "permission: data.response.permission || null" in assistant_source
    assert "clientTools: roxyClientTools()" in assistant_source
    assert "sin hablar de taxes/notaria/DMV" in assistant_source
    assert "no inventes datos" in assistant_source
    assert "clima, calendario, compras" in assistant_source


def test_streamlit_roxy_voice_hides_legacy_floating_avatar_when_runtime_mounts():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "body.roxy-el-runtime-mounted .roxy-floating-avatar,.roxy-floating-avatar{display:none!important}" in assistant_source
    assert ".roxy-floating-avatar{display:none!important}" in assistant_source
    assert 'parentDoc.body.classList.add("roxy-el-runtime-mounted")' in assistant_source


def test_streamlit_roxy_wake_word_routes_to_local_brain_before_url_reload():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "async function processWakeCommand(value)" in assistant_source
    assert "callRoxyDesktopHelper({" in assistant_source
    assert 'source: "hola_roxy_wake_word"' in assistant_source
    assert "voiceWake: true" in assistant_source
    assert "function localPlatformVoiceReply(command)" in assistant_source
    assert 'const watchCandidates = String(snapshot.snapshot_kind || "") === "watch_candidate"' in assistant_source
    assert "estas son candidatas en observacion; ninguna esta lista para entrada" in assistant_source
    assert 'const scoreLabel = watchCandidates ? "Score de vigilancia " : "Confianza "' in assistant_source
    assert "Target sin definir; no hay objetivo explicito" in assistant_source
    assert "Niveles incompletos para operar" in assistant_source
    assert 'source: "browser_visible_context"' in assistant_source
    assert "Roxy preparo respuesta local" in assistant_source
    assert "speakLocalRoxyReply(wakeGreetingReply(), true)" in assistant_source
    assert "__roxyPendingHelperVoiceReply" in assistant_source
    assert "Roxy OS local proceso la instruccion" in assistant_source
    assert 'sendCommandToRoxyOSNavigation("Hola Roxy " + command)' in assistant_source
    assert "processWakeCommand(transcript).then(function(sent)" in assistant_source


def test_streamlit_roxy_voice_uses_single_parent_runtime_guard():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "__roxyVoiceConversation" in assistant_source
    assert "oldParentWakeRuntime" in assistant_source
    assert "parentDoc.body.appendChild(parentWakeRuntime);" in assistant_source
    assert "Roxy esta escuchando" not in assistant_source
    assert "elevenLabsModulePromise" not in assistant_source


def test_streamlit_roxy_voice_does_not_trigger_second_agent_reply_for_context_only():
    source = _streamlit_source()
    assistant_source = source[source.index("function sendRoxyContextToConversation") :]
    context_only_block = assistant_source.split("function roxyConversationOverrides", 1)[0]

    assert "conversation.sendContextualUpdate(roxyVoiceContextMessage());" in context_only_block
    assert "El usuario acaba de decir Hola Roxy" not in context_only_block
    assert "Responde breve y lista" not in context_only_block


def test_streamlit_roxy_voice_exposes_clear_mobile_tap_copy():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "Toca para hablar" in assistant_source
    assert "Toca para hablar con Roxy" in assistant_source
    assert "Roxy lista" not in assistant_source


def test_streamlit_roxy_voice_sends_visible_opportunities_and_contract():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "roxy_voice_response_contract" in source
    assert "roxy_voice_opportunity_snapshot" in source
    assert "voice_snapshot = roxy_resolved_voice_opportunity_snapshot()" in source
    assert "roxy_visible_opportunities" in assistant_source
    assert "roxy_voice_response_contract" in assistant_source
    assert "YES / NO / NO TRADE" in source
    assert "No inventes precios live" in source
    assert "responde como copiloto de Roxy Trading" in source


def test_streamlit_roxy_voice_answers_platform_context_locally_before_generic_agent():
    source = _streamlit_source()

    assert "def roxy_voice_local_context_reply" in source
    assert "local_reply = roxy_voice_local_context_reply(command_text)" in source
    assert '"intent": "platform_context_query"' in source
    assert 'opportunity_snapshot.get("source") or "visible_platform_context"' in source
    assert "No voy a inventar precios" in source
    assert "Usa esto como apoyo educativo y paper trading" in source
    assert "La lista disponible contiene candidatas WATCH" in source
    assert "score de vigilancia en vez de confianza" in source


def test_streamlit_roxy_os_context_passes_same_visible_snapshot_to_local_orchestrator():
    source = _streamlit_source()
    context_source = source[source.index("def roxy_os_context") : source.index("def roxy_desktop_helper_url")]

    assert "roxy_resolved_voice_opportunity_snapshot()" in context_source
    assert '"opportunity_snapshot": opportunity_snapshot' in context_source
    assert '"visible_opportunities_text": roxy_voice_snapshot_text(opportunity_snapshot)' in context_source
    assert '"operational_response_contract": roxy_voice_response_contract(context, opportunity_snapshot)' in context_source


def test_browser_speech_fallback_remains_available_when_secure_voice_fails():
    assert streamlit_app.browser_voice_fallback_enabled({"ELEVENLABS_API_KEY": "configured"}) is True
    assert streamlit_app.browser_voice_fallback_enabled(
        {"ELEVENLABS_API_KEY": "configured", "ROXY_ENABLE_BROWSER_VOICE_FALLBACK": "0"}
    ) is False
    source = _streamlit_source()
    assert "SpeechSynthesisUtterance" in source


def test_streamlit_roxy_voice_remembers_opportunities_from_command_and_modules():
    source = _streamlit_source()
    module_source = source[source.index("def render_roxy_module_workspace") : source.index("def render_command_center_controls")]
    command_source = source[source.index("def render_command_center_controls") : source.index("def render_launch_operator_shell")]

    assert "def remember_roxy_voice_opportunities" in source
    assert "roxy_voice_table_rows" in source
    assert "remember_roxy_voice_opportunities(" in module_source
    assert "source=f\"module:{active_module}\"" in module_source
    assert "remember_roxy_voice_opportunities(" in command_source
    assert 'source="command_center"' in command_source


def test_streamlit_roxy_voice_can_send_commands_to_roxy_os():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "roxy_os_cmd" in assistant_source
    assert "sendCommandToRoxyOS" in assistant_source
    assert "commandAfterWakePhrase" in assistant_source
    assert 'tool: "sendCommandToRoxyOS"' in assistant_source
    assert "opportunity_snapshot: payload.opportunitySnapshot || null" in assistant_source
    assert "visible_opportunities_text: payload.visibleOpportunitiesText ||" in assistant_source
    assert 'url.searchParams.set("roxy_os_cmd", command)' in assistant_source


def test_streamlit_roxy_voice_speaks_roxy_os_results_once_without_widget_duplicate():
    source = _streamlit_source()
    command_source = source[source.index("def process_roxy_os_query_command") : source.index("def render_roxy_os_command_center")]
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert "roxy_voice_pending_reply" in command_source
    assert '"pendingVoiceReply": pending_voice_reply' in assistant_source
    assert "Roxy OS ya proceso la instruccion del usuario" in assistant_source
    assert "schedulePendingVoiceReply" in assistant_source
    assert "__roxyAutoStartedPendingVoiceReplyId" in assistant_source
    assert "const pending = win.__roxyPendingHelperVoiceReply || payload.pendingVoiceReply ||" in assistant_source
    assert "widget.click" not in assistant_source


def test_streamlit_roxy_voice_recognizes_personal_assistant_commands():
    source = _streamlit_source()
    assistant_source = source[source.index("def render_roxy_elevenlabs_assistant") :]

    assert '"clima"' in assistant_source
    assert '"lluvia"' in assistant_source
    assert '"pantalla"' in assistant_source
    assert '"archivo"' in assistant_source
    assert '"calendario"' in assistant_source
    assert '"recordatorio"' in assistant_source
    assert '"oportunidades"' in assistant_source
    assert '"strike"' in assistant_source
    assert '"deriv"' in assistant_source
    assert '"watchlist"' in assistant_source
    assert '"portfolio"' in assistant_source


def test_streamlit_roxy_os_preserves_personal_assistant_actions():
    source = _streamlit_source()
    actions_source = source[source.index("def apply_roxy_os_safe_actions") : source.index("def process_roxy_os_query_command")]

    assert 'action_type == "weather_lookup"' in actions_source
    assert 'st.session_state["roxy_last_weather_request"]' in actions_source
    assert 'action_type == "file_read_request"' in actions_source
    assert 'st.session_state["roxy_pending_file_read"]' in actions_source
    assert 'action_type == "screen_capture_summary"' in actions_source
    assert 'st.session_state["roxy_pending_screen_summary"]' in actions_source
    assert 'action_type == "browser_search_or_open"' in actions_source
    assert 'st.session_state["roxy_pending_browser_action"]' in actions_source


def test_streamlit_roxy_os_renders_pending_action_inbox():
    source = _streamlit_source()
    inbox_source = source[source.index("def render_roxy_os_action_inbox") : source.index("def render_roxy_elevenlabs_assistant")]

    assert "def render_roxy_os_action_inbox" in source
    assert "render_roxy_os_action_inbox()" in source
    assert "Acciones preparadas por Roxy" in inbox_source
    assert "roxy_last_weather_request" in inbox_source
    assert "roxy_pending_browser_action" in inbox_source
    assert "roxy_pending_file_read" in inbox_source
    assert "roxy_pending_screen_summary" in inbox_source
    assert "OPENWEATHER_API_KEY" in inbox_source
    assert "Abrir busqueda preparada" in inbox_source
    assert "Autorizar lectura segura" in inbox_source
    assert "Roxy Desktop Helper" in inbox_source


def test_streamlit_roxy_os_surfaces_desktop_helper_status():
    source = _streamlit_source()
    bridge_source = source[source.index("def roxy_desktop_helper_url") : source.index("def render_roxy_os_action_inbox")]

    assert "def roxy_desktop_helper_url" in bridge_source
    assert "ROXY_DESKTOP_HELPER_URL" in bridge_source
    assert "def roxy_desktop_helper_status" in bridge_source
    assert "helper_must_be_localhost" in bridge_source
    assert "Roxy Desktop Helper conectado en localhost" in bridge_source
    assert "Permisos activos" in bridge_source
    assert "Protegidos/apagados" in bridge_source


def test_streamlit_roxy_voice_cache_depends_on_env_fingerprint():
    source = _streamlit_source()
    from roxy_trader.cache_policy import cache_ttl

    assert "elevenlabs_env_fingerprint" in source
    assert "def roxy_elevenlabs_signed_session_payload(agent_id: str, env_fingerprint: str)" in source
    assert 'ttl=cache_ttl("voice_session")' in source
    assert cache_ttl("voice_session", {}) == 45


def test_streamlit_roxy_display_name_rejects_placeholder_dash():
    source = _streamlit_source()
    display_source = source[source.index("def roxy_user_display_name") : source.index("def roxy_auth_db_path")]

    assert 'value in {"-", "—", "None", "null"}' in display_source
    assert "clean_display_name" in display_source
