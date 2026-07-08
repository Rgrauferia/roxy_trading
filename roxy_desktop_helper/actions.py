from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from .safety import is_safe_read_path


TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".html",
    ".css",
}


def env_flag(name: str, env: dict[str, str] | None = None) -> bool:
    values = env or os.environ
    return str(values.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def desktop_feature_flags(env: dict[str, str] | None = None) -> dict[str, bool]:
    return {
        "screen_summary": env_flag("ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE", env),
        "browser_control": env_flag("ROXY_DESKTOP_ALLOW_BROWSER_OPEN", env),
        "file_read": env_flag("ROXY_DESKTOP_ALLOW_FILE_READ", env),
        "screen_control": False,
        "system_write": False,
    }


def prepare_browser_target(query_or_url: str) -> tuple[bool, str, str]:
    value = str(query_or_url or "").strip()
    if not value:
        return False, "", "Falta la busqueda o URL."

    lowered = value.lower()
    if lowered.startswith(("javascript:", "file:", "data:", "ftp:")):
        return False, "", "Roxy bloquea URLs locales, scripts y esquemas inseguros."

    if lowered.startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False, "", "La URL no parece valida."
        return True, value, "URL segura preparada."

    return True, f"https://www.google.com/search?q={quote_plus(value)}", "Busqueda segura preparada."


def open_browser(query_or_url: str) -> dict[str, Any]:
    allowed, target_url, reason = prepare_browser_target(query_or_url)
    if not allowed:
        return {"ok": False, "executed": False, "reason": reason, "target_url": target_url}

    if not env_flag("ROXY_DESKTOP_ALLOW_BROWSER_OPEN"):
        return {
            "ok": True,
            "executed": False,
            "requires_permission": "ROXY_DESKTOP_ALLOW_BROWSER_OPEN=1",
            "target_url": target_url,
            "message": "Prepare la pagina, pero no la abri porque el permiso de navegador local esta apagado.",
        }

    subprocess.Popen(["open", target_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {
        "ok": True,
        "executed": True,
        "target_url": target_url,
        "message": "Abri la pagina preparada en tu navegador.",
    }


def read_text_file(path_value: str) -> dict[str, Any]:
    allowed, reason = is_safe_read_path(path_value)
    if not allowed:
        return {"ok": False, "executed": False, "reason": reason, "path": path_value}

    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    if not env_flag("ROXY_DESKTOP_ALLOW_FILE_READ"):
        return {
            "ok": True,
            "executed": False,
            "requires_permission": "ROXY_DESKTOP_ALLOW_FILE_READ=1",
            "path": str(path),
            "message": "Puedo leer esa ruta, pero el permiso local de lectura de archivos esta apagado.",
        }

    if not path.exists():
        return {"ok": False, "executed": False, "reason": "No encontre esa ruta.", "path": str(path)}

    if path.is_dir():
        children = sorted(child.name for child in path.iterdir() if not child.name.startswith("."))[:60]
        return {
            "ok": True,
            "executed": True,
            "path": str(path),
            "type": "directory",
            "children": children,
            "message": "Revise la carpeta y prepare la lista de archivos visibles.",
        }

    if path.suffix.lower() not in TEXT_SUFFIXES:
        return {
            "ok": False,
            "executed": False,
            "reason": "Por ahora el helper local solo lee texto y codigo. PDF/OCR debe pasar por el pipeline de conocimiento.",
            "path": str(path),
        }

    content = path.read_text(encoding="utf-8", errors="replace")[:12000]
    preview = " ".join(content.split())[:900]
    return {
        "ok": True,
        "executed": True,
        "path": str(path),
        "type": "file",
        "chars_read": len(content),
        "preview": preview,
        "message": f"Lei {path.name} y prepare un resumen inicial.",
    }


def capture_screen_summary(context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    if not env_flag("ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE"):
        return {
            "ok": True,
            "executed": False,
            "requires_permission": "ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE=1",
            "message": (
                "Puedo resumir el contexto visible de Roxy Trading, pero para ver toda tu Mac "
                "debes activar permiso local de captura de pantalla."
            ),
            "visible_context": {
                "page": context.get("page"),
                "module": context.get("module"),
                "symbol": context.get("symbol"),
                "market": context.get("market"),
                "timeframe": context.get("timeframe"),
            },
        }

    capture_dir = Path(tempfile.gettempdir()) / "roxy_desktop_captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    target = capture_dir / "latest_screen.png"
    result = subprocess.run(
        ["/usr/sbin/screencapture", "-x", str(target)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "executed": False,
            "reason": (result.stderr or "screencapture failed").strip()[:240],
        }
    return {
        "ok": True,
        "executed": True,
        "screenshot_path": str(target),
        "message": "Capture la pantalla local. El siguiente paso es conectar OCR/vision para resumirla.",
    }


def apply_prepared_action(action: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any] | None:
    action_type = str(action.get("type") or "")
    if action_type == "browser_search_or_open":
        return open_browser(str(action.get("query") or ""))
    if action_type == "file_read_request":
        path_value = str(action.get("path") or "")
        if not path_value:
            return {
                "ok": True,
                "executed": False,
                "message": "Falta la ruta del archivo o carpeta que quieres que lea.",
            }
        return read_text_file(path_value)
    if action_type == "screen_capture_summary":
        return capture_screen_summary(context)
    return None
