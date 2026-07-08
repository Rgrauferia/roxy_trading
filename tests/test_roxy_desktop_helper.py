from __future__ import annotations

import json
from urllib.request import Request, urlopen

from roxy_desktop_helper import create_server
from roxy_desktop_helper.actions import prepare_browser_target
from roxy_desktop_helper.safety import desktop_capabilities, is_safe_read_path


def test_desktop_helper_blocks_secret_paths() -> None:
    allowed, reason = is_safe_read_path("/Users/roberto/project/.env")
    assert allowed is False
    assert "bloquea" in reason

    allowed, reason = is_safe_read_path("/Users/roberto/Desktop/article.txt")
    assert allowed is True
    assert "permitida" in reason


def test_desktop_helper_capabilities_are_safe_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE", raising=False)
    monkeypatch.delenv("ROXY_DESKTOP_ALLOW_BROWSER_OPEN", raising=False)
    monkeypatch.delenv("ROXY_DESKTOP_ALLOW_FILE_READ", raising=False)

    capabilities = desktop_capabilities()
    assert capabilities["roxy_os_commands"] is True
    assert capabilities["screen_control"] is False
    assert capabilities["system_write"] is False
    assert capabilities["screen_summary"] is False
    assert capabilities["browser_control"] is False
    assert capabilities["file_read"] is False


def test_desktop_helper_capabilities_reflect_opt_in_env(monkeypatch) -> None:
    monkeypatch.setenv("ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE", "1")
    monkeypatch.setenv("ROXY_DESKTOP_ALLOW_BROWSER_OPEN", "true")
    monkeypatch.setenv("ROXY_DESKTOP_ALLOW_FILE_READ", "yes")

    capabilities = desktop_capabilities()
    assert capabilities["screen_summary"] is True
    assert capabilities["browser_control"] is True
    assert capabilities["file_read"] is True
    assert capabilities["screen_control"] is False
    assert capabilities["system_write"] is False


def test_prepare_browser_target_blocks_unsafe_url() -> None:
    allowed, target_url, reason = prepare_browser_target("javascript:alert(1)")

    assert allowed is False
    assert target_url == ""
    assert "bloquea" in reason


def test_prepare_browser_target_converts_search_query() -> None:
    allowed, target_url, reason = prepare_browser_target("precio de bitcoin hoy")

    assert allowed is True
    assert target_url.startswith("https://www.google.com/search?q=")
    assert "bitcoin" in target_url
    assert "preparada" in reason


def test_desktop_helper_command_endpoint(tmp_path) -> None:
    server = create_server("127.0.0.1", 0)
    server.orchestrator.memory.path = tmp_path / "memory.json"
    host, port = server.server_address

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://{host}:{port}/command",
            data=json.dumps(
                {
                    "user_id": "roberto",
                    "text": "Hola Roxy dime que estoy viendo en la pantalla",
                    "context": {"page": "Dashboard", "module": "acciones", "symbol": "AAPL"},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert payload["ok"] is True
    assert payload["response"]["intent"] == "screen_summary"
    assert payload["response"]["permission"]["mode"] in {"autopilot_safe", "ask_before_action"}
    assert payload["response"]["desktop_actions"][0]["action"] == "screen_capture_summary"
    assert payload["response"]["desktop_actions"][0]["executed"] is False


def test_desktop_helper_screen_summary_endpoint_is_blocked_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE", raising=False)
    server = create_server("127.0.0.1", 0)
    host, port = server.server_address

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://{host}:{port}/screen/summary",
            data=json.dumps({"context": {"page": "Dashboard", "module": "acciones", "symbol": "AAPL"}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert payload["ok"] is True
    assert payload["executed"] is False
    assert payload["visible_context"]["symbol"] == "AAPL"
    assert payload["requires_permission"] == "ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE=1"


def test_desktop_helper_browser_open_endpoint_prepares_without_opening(monkeypatch) -> None:
    monkeypatch.delenv("ROXY_DESKTOP_ALLOW_BROWSER_OPEN", raising=False)
    server = create_server("127.0.0.1", 0)
    host, port = server.server_address

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://{host}:{port}/browser/open",
            data=json.dumps({"query": "Roxy Trading oportunidades AAPL"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert payload["ok"] is True
    assert payload["executed"] is False
    assert payload["target_url"].startswith("https://www.google.com/search?q=")


def test_desktop_helper_file_read_endpoint_blocks_until_opt_in(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ROXY_DESKTOP_ALLOW_FILE_READ", raising=False)
    sample = tmp_path / "notes.txt"
    sample.write_text("Roxy debe resumir esto.", encoding="utf-8")
    server = create_server("127.0.0.1", 0)
    host, port = server.server_address

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://{host}:{port}/file/read",
            data=json.dumps({"path": str(sample)}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert payload["ok"] is True
    assert payload["executed"] is False
    assert payload["requires_permission"] == "ROXY_DESKTOP_ALLOW_FILE_READ=1"


def test_desktop_helper_file_read_endpoint_reads_text_when_opted_in(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ROXY_DESKTOP_ALLOW_FILE_READ", "1")
    sample = tmp_path / "notes.txt"
    sample.write_text("Roxy puede leer este archivo seguro.", encoding="utf-8")
    server = create_server("127.0.0.1", 0)
    host, port = server.server_address

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://{host}:{port}/file/read",
            data=json.dumps({"path": str(sample)}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["type"] == "file"
    assert "archivo seguro" in payload["preview"]


def test_desktop_helper_cors_allows_roxy_origins(tmp_path) -> None:
    server = create_server("127.0.0.1", 0)
    host, port = server.server_address

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://{host}:{port}/health",
            headers={"Origin": "https://roxy-trading.onrender.com"},
            method="GET",
        )
        with urlopen(request, timeout=5) as response:
            origin = response.headers.get("Access-Control-Allow-Origin")
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert origin == "https://roxy-trading.onrender.com"
    assert payload["ok"] is True


def test_desktop_helper_cors_rejects_unknown_origins() -> None:
    server = create_server("127.0.0.1", 0)
    host, port = server.server_address

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://{host}:{port}/health",
            headers={"Origin": "https://malicious.example"},
            method="GET",
        )
        with urlopen(request, timeout=5) as response:
            origin = response.headers.get("Access-Control-Allow-Origin")
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert origin is None
    assert payload["ok"] is True
