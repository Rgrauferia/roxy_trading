from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import requests


HOME_ASSISTANT_CONTRACT = "roxy-home-assistant/1.0.0"
READABLE_DOMAINS = {"light", "switch", "climate", "sensor", "binary_sensor", "media_player", "camera", "lock"}
WRITABLE_SERVICES = {("light", "turn_on"), ("light", "turn_off"), ("switch", "turn_on"), ("switch", "turn_off")}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_base_url(value: Any) -> tuple[str, str]:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return "", "missing_url"
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "", "invalid_url"
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return "", "invalid_url"
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        return "", "base_url_must_not_include_path_query_or_fragment"
    if parsed.scheme == "http":
        host = parsed.hostname.casefold()
        local = host in {"localhost", "127.0.0.1", "::1"}
        try:
            address = ipaddress.ip_address(host)
            local = local or address.is_private or address.is_loopback
        except ValueError:
            local = local or host.endswith(".local")
        if not local:
            return "", "https_required_for_non_local_host"
    return raw, ""


@dataclass(frozen=True)
class HomeAssistantConfig:
    base_url: str
    token: str
    control_enabled: bool
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "HomeAssistantConfig":
        try:
            timeout = float(os.environ.get("ROXY_HOME_ASSISTANT_TIMEOUT") or 5)
        except (TypeError, ValueError):
            timeout = 5.0
        return cls(
            base_url=str(os.environ.get("ROXY_HOME_ASSISTANT_URL") or "").strip(),
            token=str(os.environ.get("ROXY_HOME_ASSISTANT_TOKEN") or "").strip(),
            control_enabled=str(os.environ.get("ROXY_HOME_CONTROL_ENABLED") or "0").strip() == "1",
            timeout_seconds=max(1.0, min(timeout, 15.0)),
        )


class HomeAssistantClient:
    def __init__(self, config: HomeAssistantConfig | None = None, *, session: Any = None) -> None:
        self.config = config or HomeAssistantConfig.from_env()
        self.session = session or requests.Session()

    def _configuration_state(self) -> tuple[str, str]:
        base_url, error = _safe_base_url(self.config.base_url)
        if error == "missing_url" or not self.config.token:
            return "SERVICE_NOT_CONFIGURED", "Configura ROXY_HOME_ASSISTANT_URL y ROXY_HOME_ASSISTANT_TOKEN."
        if error:
            return "CONFIGURATION_ERROR", error
        return "READY", base_url

    def _request(self, method: str, path: str, *, payload: dict[str, Any] | None = None) -> tuple[str, Any, str]:
        configuration, detail = self._configuration_state()
        if configuration != "READY":
            return configuration, None, detail
        headers = {"Authorization": f"Bearer {self.config.token}", "Content-Type": "application/json"}
        try:
            response = self.session.request(
                method,
                f"{detail}{path}",
                headers=headers,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.Timeout:
            return "UNAVAILABLE", None, "Home Assistant excedio el timeout."
        except requests.RequestException as exc:
            return "UNAVAILABLE", None, f"Home Assistant no responde: {type(exc).__name__}."
        if response.status_code in {401, 403}:
            return "AUTH_INVALID", None, "Home Assistant rechazo el token."
        if not 200 <= int(response.status_code) < 300:
            return "ERROR", None, f"Home Assistant respondio HTTP {int(response.status_code)}."
        try:
            data = response.json()
        except (TypeError, ValueError):
            data = None
        return "CONNECTED", data, "Conexion verificada."

    def status(self) -> dict[str, Any]:
        state, payload, detail = self._request("GET", "/api/")
        return {
            "contract_version": HOME_ASSISTANT_CONTRACT,
            "status": state,
            "connected": state == "CONNECTED",
            "control_enabled": bool(self.config.control_enabled),
            "checked_at": _now_iso(),
            "detail": detail,
            "message": str((payload or {}).get("message") or "") if isinstance(payload, dict) else "",
        }

    def entities(self) -> dict[str, Any]:
        state, payload, detail = self._request("GET", "/api/states")
        entities: list[dict[str, Any]] = []
        if state == "CONNECTED" and isinstance(payload, list):
            for raw in payload:
                if not isinstance(raw, dict):
                    continue
                entity_id = str(raw.get("entity_id") or "")[:160]
                domain = entity_id.split(".", 1)[0]
                if domain not in READABLE_DOMAINS:
                    continue
                attributes = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
                entities.append({
                    "entity_id": entity_id,
                    "domain": domain,
                    "name": str(attributes.get("friendly_name") or entity_id)[:160],
                    "state": str(raw.get("state") or "unknown")[:80],
                    "unit": str(attributes.get("unit_of_measurement") or "")[:32],
                    "updated_at": str(raw.get("last_updated") or raw.get("last_changed") or "")[:64],
                    "writable": domain in {"light", "switch"},
                    "sensitive": domain in {"camera", "lock"},
                })
        entities.sort(key=lambda row: (row["domain"], row["name"].casefold()))
        return {
            "contract_version": HOME_ASSISTANT_CONTRACT,
            "status": state,
            "detail": detail,
            "checked_at": _now_iso(),
            "control_enabled": bool(self.config.control_enabled),
            "entity_count": len(entities),
            "entities": entities,
        }

    def call_service(
        self,
        *,
        domain: str,
        service: str,
        entity_id: str,
        confirmed: bool,
        permission_granted: bool,
    ) -> dict[str, Any]:
        normalized_domain = str(domain or "").strip().lower()
        normalized_service = str(service or "").strip().lower()
        normalized_entity = str(entity_id or "").strip().lower()
        if (normalized_domain, normalized_service) not in WRITABLE_SERVICES:
            return {"status": "BLOCKED", "executed": False, "detail": "Servicio no permitido por Roxy Home."}
        if not normalized_entity.startswith(f"{normalized_domain}."):
            return {"status": "BLOCKED", "executed": False, "detail": "La entidad no coincide con el dominio."}
        if not self.config.control_enabled:
            return {"status": "CONTROL_DISABLED", "executed": False, "detail": "ROXY_HOME_CONTROL_ENABLED no esta activo."}
        if not permission_granted or not confirmed:
            return {"status": "CONFIRMATION_REQUIRED", "executed": False, "detail": "Falta permiso o confirmacion explicita."}
        state, payload, detail = self._request(
            "POST",
            f"/api/services/{normalized_domain}/{normalized_service}",
            payload={"entity_id": normalized_entity},
        )
        return {
            "status": state,
            "executed": state == "CONNECTED",
            "detail": detail,
            "entity_id": normalized_entity,
            "service": normalized_service,
            "provider_response_count": len(payload) if isinstance(payload, list) else 0,
            "executed_at": _now_iso() if state == "CONNECTED" else None,
        }
