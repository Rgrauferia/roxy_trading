from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from roxy_os import RoxyOrchestrator

from .actions import capture_screen_summary, open_browser, read_text_file, apply_prepared_action
from .safety import desktop_capabilities, is_safe_read_path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_ALLOWED_ORIGINS = {
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://roxy-trading.onrender.com",
}


class RoxyDesktopServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[BaseHTTPRequestHandler],
        *,
        orchestrator: RoxyOrchestrator | None = None,
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.orchestrator = orchestrator or RoxyOrchestrator()


class RoxyDesktopHandler(BaseHTTPRequestHandler):
    server: RoxyDesktopServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "service": "roxy-desktop-helper",
                    "capabilities": desktop_capabilities(),
                }
            )
            return
        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def do_POST(self) -> None:
        payload = self._read_json()
        if self.path == "/command":
            self._handle_command(payload)
            return
        if self.path == "/file/check":
            self._handle_file_check(payload)
            return
        if self.path == "/file/read":
            self._handle_file_read(payload)
            return
        if self.path == "/browser/open":
            self._handle_browser_open(payload)
            return
        if self.path == "/screen/summary":
            self._handle_screen_summary(payload)
            return
        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def _handle_command(self, payload: dict[str, Any]) -> None:
        text = str(payload.get("text") or "").strip()
        if not text:
            self._send_json({"ok": False, "error": "Missing text"}, status=400)
            return
        context = dict(payload.get("context") or {})
        context.setdefault("source", "roxy_desktop_helper")
        context.setdefault("allowed_permissions", [])
        response = self.server.orchestrator.handle(
            text,
            user_id=str(payload.get("user_id") or "local_desktop_user"),
            context=context,
        )
        response_payload = response.to_dict()
        desktop_actions = self._apply_safe_desktop_actions(response_payload, context)
        if desktop_actions:
            response_payload["desktop_actions"] = desktop_actions
            response_payload["message"] = self._append_desktop_action_message(
                str(response_payload.get("message") or ""),
                desktop_actions,
            )
        self._send_json({"ok": True, "response": response_payload})

    def _handle_file_check(self, payload: dict[str, Any]) -> None:
        path_value = str(payload.get("path") or "").strip()
        if not path_value:
            self._send_json({"ok": False, "error": "Missing path"}, status=400)
            return
        allowed, reason = is_safe_read_path(path_value)
        self._send_json({"ok": True, "allowed": allowed, "reason": reason})

    def _handle_file_read(self, payload: dict[str, Any]) -> None:
        path_value = str(payload.get("path") or "").strip()
        if not path_value:
            self._send_json({"ok": False, "error": "Missing path"}, status=400)
            return
        self._send_json(read_text_file(path_value))

    def _handle_browser_open(self, payload: dict[str, Any]) -> None:
        query = str(payload.get("url") or payload.get("query") or payload.get("text") or "").strip()
        if not query:
            self._send_json({"ok": False, "error": "Missing url or query"}, status=400)
            return
        self._send_json(open_browser(query))

    def _handle_screen_summary(self, payload: dict[str, Any]) -> None:
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        self._send_json(capture_screen_summary(context))

    def _apply_safe_desktop_actions(
        self,
        response_payload: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for action in response_payload.get("actions") or []:
            if not isinstance(action, dict):
                continue
            result = apply_prepared_action(action, context)
            if result is not None:
                results.append({"action": action.get("type"), **result})
        return results

    def _append_desktop_action_message(self, message: str, desktop_actions: list[dict[str, Any]]) -> str:
        useful = [item for item in desktop_actions if isinstance(item, dict) and item.get("message")]
        if not useful:
            return message
        action_messages = " ".join(str(item.get("message") or "") for item in useful[:2])
        if not message:
            return action_messages
        return f"{message} {action_messages}"

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin") or ""
        allowed_origins = set(DEFAULT_ALLOWED_ORIGINS)
        configured = getattr(self.server, "allowed_origins", None)
        if isinstance(configured, set):
            allowed_origins |= configured
        if origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    orchestrator: RoxyOrchestrator | None = None,
) -> RoxyDesktopServer:
    return RoxyDesktopServer((host, port), RoxyDesktopHandler, orchestrator=orchestrator)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = create_server(host, port)
    print(f"Roxy Desktop Helper listening on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Roxy Desktop Helper.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
