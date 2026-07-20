import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from roxy_os import RoxyOrchestrator
from roxy_os.memory import RoxyMemoryManager


def test_roxy_os_adds_and_recalls_shopping_items(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Hola Roxy, acuerdame que tengo que comprar pan, cafe y leche", user_id="robert")

    assert response.intent == "shopping_add"
    assert response.agent == "shopping"
    assert "pan" in response.message
    assert "cafe" in response.message

    followup = roxy.handle("Roxy, que necesito comprar en la lista de compra", user_id="robert")

    assert followup.intent == "shopping_query"
    assert "pan" in followup.message
    assert "cafe" in followup.message
    assert "leche" in followup.message
    assert [item["name"] for item in roxy.shopping_list.list_items("robert")] == ["cafe", "leche", "pan"]


def test_roxy_os_splits_common_grocery_voice_dictation_without_commas(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Hola Roxy acuerdame comprar pan cafe leche", user_id="robert")

    assert response.intent == "shopping_add"
    assert [item["content"] for item in response.data["items"]] == ["pan", "cafe", "leche"]


def test_roxy_os_persists_memory_between_instances(tmp_path):
    memory_path = tmp_path / "memory.json"
    RoxyOrchestrator(memory_path=memory_path).handle("Roxy, acuerdame comprar pan", user_id="robert")

    second_instance = RoxyOrchestrator(memory_path=memory_path)
    response = second_instance.handle("Roxy, lista de compra", user_id="robert")

    assert "pan" in response.message
    assert (tmp_path / "roxy_shopping_list.json").exists()


def test_roxy_os_blocks_destructive_or_sensitive_commands(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Roxy ejecuta rm -rf en el proyecto", user_id="robert")

    assert response.permission is not None
    assert response.permission.allowed is False
    assert response.permission.risk_level == "high"
    assert response.data["blocked"] is True


def test_roxy_os_routes_screen_summary_with_permission_gate(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Roxy dime que estoy viendo en la pantalla", user_id="robert")

    assert response.intent == "screen_summary"
    assert response.agent == "screen"
    assert response.permission is not None
    assert response.permission.allowed is True
    assert response.data["required_permission"] == "screen_read"
    assert response.actions[0]["type"] == "screen_capture_summary"


def test_roxy_os_routes_trading_scan_without_real_trade(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle(
        "Roxy abre Roxy Trading y dime las mejores oportunidades de inversion",
        user_id="robert",
        context={"page": "Dashboard", "module": "crypto-20m", "symbol": "BTC/USD", "market": "crypto"},
    )

    assert response.intent == "trading_scan"
    assert response.agent == "trader"
    assert response.data["module"] == "acciones-operar"
    assert response.actions[0]["module"] == "acciones-operar"
    assert response.data["requires_live_market_data"] is True
    assert response.data["context"]["module"] == "crypto-20m"
    assert response.data["context"]["symbol"] == "BTC/USD"
    assert response.data["plan"][0]["step"] == "open_trading_module"
    assert response.data["events"][0]["type"] == "request_handled"
    assert any(action["type"] == "run_trading_scan" for action in response.actions)
    assert "No ejecutare trades reales" in response.message


def test_roxy_os_routes_named_stock_to_operational_chart(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Hola Roxy muestrame Apple en la grafica", user_id="robert")

    assert response.intent == "trading_scan"
    assert response.data["module"] == "acciones-operar"
    assert response.data["symbol"] == "AAPL"
    assert response.actions[0]["symbol"] == "AAPL"
    assert response.actions[0]["market"] == "stock"


def test_roxy_os_trader_uses_visible_opportunity_snapshot_for_voice_decision(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle(
        "Hola Roxy dame las mejores oportunidades",
        user_id="robert",
        context={
            "module": "acciones-operar",
            "symbol": "AAPL",
            "market": "stock",
            "opportunity_snapshot": {
                "rows": [
                    {
                        "symbol": "AAPL",
                        "decision": "ESPERAR CONFIRMACION",
                        "price": "288.88",
                        "entry": "289.20",
                        "stop": "287.00",
                        "target": "294.14",
                        "confidence": "89",
                        "risk_reward": "1R:2.8R",
                        "reason": "EMA9 sobre EMA21 y volumen creciente",
                    },
                    {
                        "symbol": "TSLA",
                        "decision": "NO OPERAR",
                        "price": "416.05",
                        "confidence": "74",
                    },
                ]
            },
        },
    )

    assert response.intent == "trading_scan"
    assert response.data["best_visible_opportunity"]["symbol"] == "AAPL"
    assert "Mejor oportunidad visible: AAPL" in response.message
    assert "Entrada: 289.20" in response.message
    assert "Stop loss: 287.00" in response.message
    assert "Target: 294.14" in response.message
    assert "EMA9 sobre EMA21" in response.message


def test_roxy_os_trader_formats_crypto_visible_snapshot_as_yes_no(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle(
        "Roxy analiza Bitcoin crypto 20 minutos",
        user_id="robert",
        context={
            "module": "crypto-20m",
            "symbol": "BTC/USD",
            "market": "crypto",
            "opportunity_snapshot": {
                "rows": [
                    {
                        "symbol": "BTC/USD",
                        "decision": "YES",
                        "price": "59670.20",
                        "entry": "59845",
                        "stop_loss": "59590",
                        "target": "59845",
                        "confidence": "84%",
                        "risk_reward": "edge positivo",
                        "reason": "EMA9 cruzo EMA21, momentum positivo y volumen creciente",
                    }
                ]
            },
        },
    )

    assert response.data["module"] == "crypto-20m"
    assert "Senal: YES" in response.message
    assert "Entrada/strike: 59845" in response.message
    assert "Stop virtual: 59590" in response.message
    assert "contrato" in response.message


def test_roxy_os_trader_explains_explicit_visible_asset_not_highest_other_row(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle(
        "Roxy analiza Apple",
        user_id="robert",
        context={
            "module": "acciones-operar",
            "symbol": "AAPL",
            "market": "stock",
            "opportunity_snapshot": {
                "rows": [
                    {"symbol": "TSLA", "confidence": "99", "decision": "ESPERAR", "price": "400"},
                    {"symbol": "AAPL", "confidence": "72", "decision": "VIGILAR", "price": "210"},
                ]
            },
        },
    )

    assert response.data["best_visible_opportunity"]["symbol"] == "AAPL"
    assert response.data["selected_visible_opportunity"]["symbol"] == "AAPL"
    assert "Mejor oportunidad visible: AAPL" in response.message
    assert "TSLA" not in response.message


def test_roxy_os_routes_crypto_2h_voice_command(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Roxy abre Bitcoin crypto 2 horas", user_id="robert")

    assert response.intent == "trading_scan"
    assert response.data["module"] == "crypto-2h"
    assert response.data["symbol"] == "BTC/USD"
    assert response.actions[0]["timeframe"] == "2h"


def test_roxy_os_routes_classroom_to_open_module_action(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Roxy abre classroom y empieza la clase", user_id="robert")

    assert response.intent == "academy_query"
    assert response.agent == "academy"
    assert response.actions[0]["type"] == "open_module"
    assert response.actions[0]["module"] == "classroom"


def test_roxy_os_routes_weather_query_without_exposing_keys(tmp_path, monkeypatch):
    from tools.weather_service import WeatherSnapshot
    import roxy_os.agents.simple_agents as simple_agents

    def fake_weather(location):
        return WeatherSnapshot(
            status="ok",
            location=location,
            description="cielo claro",
            temperature_c=28.4,
            feels_like_c=30.1,
            humidity=61,
            wind_mps=2.8,
        )

    monkeypatch.setattr(simple_agents.weather_service, "fetch_current_weather", fake_weather)
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Hola Roxy, va a llover en Miami?", user_id="robert")

    assert response.intent == "weather_query"
    assert response.agent == "weather"
    assert response.data["location"] == "Miami"
    assert response.actions[0]["type"] == "weather_lookup"
    assert "28.4 C" in response.message


def test_roxy_os_routes_reader_request_with_permission_gate(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Roxy lee este archivo README.md", user_id="robert")

    assert response.intent == "reader_request"
    assert response.agent == "reader"
    assert response.permission is not None
    assert response.permission.confirmation_required is True
    assert response.data["required_permission"] == "file_read"
    assert response.actions[0]["type"] == "file_read_request"


def test_roxy_os_extracts_browser_search_query(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Hola Roxy abre Google y busca calendario economico de esta semana", user_id="robert")

    assert response.intent == "browser_action"
    assert response.agent == "browser"
    assert response.data["query"] == "calendario economico de esta semana"
    assert response.actions[0]["type"] == "browser_search_or_open"
    assert response.actions[0]["query"] == "calendario economico de esta semana"


def test_roxy_os_saves_and_lists_general_reminders(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    saved = roxy.handle("Hola Roxy acuerdame llamar al cliente manana", user_id="robert")
    listed = roxy.handle("Roxy que recordatorios tengo", user_id="robert")

    assert saved.intent == "calendar_query"
    assert saved.agent == "calendar"
    assert "llamar al cliente manana" in saved.message
    assert saved.data["reminder"]["content"] == "llamar al cliente manana"
    assert "llamar al cliente manana" in listed.message
    tasks = roxy.personal_tasks.list_tasks("robert")
    assert tasks[0]["title"] == "llamar al cliente manana"
    assert tasks[0]["source"] == "voice_or_text"


def test_roxy_os_personal_tasks_are_shared_between_instances(tmp_path):
    memory_path = tmp_path / "memory.json"
    first = RoxyOrchestrator(memory_path=memory_path)
    first.handle("Roxy acuerdame revisar el calendario", user_id="robert")

    second = RoxyOrchestrator(memory_path=memory_path)
    response = second.handle("Roxy que recordatorios tengo", user_id="robert")

    assert "revisar el calendario" in response.message
    assert response.data["tasks"][0]["status"] == "PENDING"
    assert (tmp_path / "roxy_personal_tasks.json").exists()


def test_roxy_os_lists_document_metadata_without_reading_content(tmp_path):
    memory_path = tmp_path / "memory.json"
    roxy = RoxyOrchestrator(memory_path=memory_path)
    roxy.document_vault.ingest("robert", "contrato.pdf", b"pdf fixture")

    response = roxy.handle("Roxy, lista de documentos guardados", user_id="robert")

    assert response.agent == "documents"
    assert response.intent == "documents_query"
    assert "contrato.pdf" in response.message
    assert response.data["content_read"] is False
    assert response.data["document_snapshot"]["sync_state"] == "LOCAL_ENCRYPTED"
    assert response.data["document_snapshot"]["at_rest_encryption"] is True
    assert response.actions[0]["view"] == "Documentos"


def test_roxy_os_email_is_read_only_and_explicit_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("ROXY_GMAIL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ROXY_OUTLOOK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ROXY_EMAIL_PROVIDER", raising=False)
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle("Roxy revisa mis correos recientes", user_id="robert")

    assert response.agent == "email"
    assert response.intent == "email_query"
    assert "SERVICE_NOT_CONFIGURED" in response.message
    assert response.data["body_read"] is False
    assert response.data["send_enabled"] is False
    assert response.actions[0]["view"] == "Correo"


def test_roxy_os_refuses_reader_secret_paths_when_permission_allowed(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle(
        "Roxy lee este archivo .env",
        user_id="robert",
        context={"allowed_permissions": ["file_read"]},
    )

    assert response.intent == "reader_request"
    assert response.data["blocked"] is True
    assert "secretos" in response.message


def test_roxy_os_blocked_commands_still_return_plan_and_context(tmp_path):
    roxy = RoxyOrchestrator(memory_path=tmp_path / "memory.json")

    response = roxy.handle(
        "Roxy haz git push a produccion",
        user_id="robert",
        context={"page": "Code", "module": "developer"},
    )

    assert response.permission is not None
    assert response.permission.allowed is False
    assert response.data["blocked"] is True
    assert response.data["context"]["module"] == "developer"
    assert response.data["plan"][0]["step"] == "inspect_project_files"


def test_streamlit_roxy_os_unavailable_result_keeps_import_diagnostic():
    source = __import__("pathlib").Path("streamlit_app.py").read_text(encoding="utf-8")

    assert "ROXY_OS_IMPORT_ERROR" in source
    assert '\"reason\": \"roxy_os_unavailable\"' in source
    assert '\"diagnostic\": ROXY_OS_IMPORT_ERROR' in source


def test_memory_search_is_user_scoped(tmp_path):
    memory = RoxyMemoryManager(tmp_path / "memory.json")
    memory.remember(
        user_id="robert",
        memory_type="shopping_item",
        title="Comprar cafe",
        content="cafe",
        source="test",
        tags=["shopping"],
    )
    memory.remember(
        user_id="other",
        memory_type="shopping_item",
        title="Comprar leche",
        content="leche",
        source="test",
        tags=["shopping"],
    )

    results = memory.search("comprar cafe leche", user_id="robert")

    assert len(results) == 1
    assert results[0]["content"] == "cafe"


def test_memory_store_preserves_concurrent_writes_across_instances(tmp_path):
    path = tmp_path / "memory.json"

    def remember(index):
        return RoxyMemoryManager(path).remember(
            user_id=f"user-{index:02d}",
            memory_type="note",
            title=f"Note {index}",
            content=f"Content {index}",
            source="concurrency-test",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(remember, range(16)))

    payload = json.loads(path.read_text())
    assert len(payload["memories"]) == 16
    assert {row["user_id"] for row in payload["memories"]} == {f"user-{index:02d}" for index in range(16)}
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".memory.json.lock").stat().st_mode & 0o777 == 0o600


def test_memory_store_does_not_overwrite_unreadable_content(tmp_path):
    path = tmp_path / "memory.json"
    original = b'{"memories": ['
    path.write_bytes(original)

    with pytest.raises(ValueError, match="memory store unreadable"):
        RoxyMemoryManager(path).remember(
            user_id="local",
            memory_type="note",
            title="Safe",
            content="Do not overwrite",
            source="test",
        )

    assert path.read_bytes() == original
