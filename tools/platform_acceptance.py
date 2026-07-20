from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text


CONTRACT_VERSION = "roxy-platform-acceptance/1.0.0"
DEFAULT_REPORT_PATH = Path("alerts/platform_phase_acceptance.json")
VOICE_EVIDENCE_FILES = (
    "voice_operational_coherence_probe.json",
    "voice_shared_context_probe.json",
    "voice_timeframe_e2e_probe.json",
    "voice_watchlist_e2e_probe.json",
    "voice_api_security_probe.json",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _named_check_status(report: Mapping[str, Any], name: str) -> str:
    for item in report.get("checks", []):
        if isinstance(item, Mapping) and str(item.get("name") or "") == name:
            return str(item.get("status") or "UNKNOWN").upper()
    return "MISSING"


def _phase(
    number: int,
    name: str,
    status: str,
    proven: list[str],
    blockers: list[str],
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "phase": number,
        "name": name,
        "status": status,
        "accepted": status == "ACCEPTED",
        "proven": proven,
        "blockers": blockers,
        "evidence": evidence,
    }


def build_platform_acceptance(
    root: str | Path = ".",
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    base = Path(root)
    alerts = base / "alerts"
    health = _read_json(alerts / "roxy_realtime_check.json")
    responsive = _read_json(alerts / "responsive_route_matrix.json")
    chart_health = _read_json(alerts / "chart_realtime_health.json")
    opportunity_sync = _read_json(alerts / "opportunity_sync.json")
    output_maintenance = _read_json(alerts / "output_maintenance.json")
    elevenlabs_circuit = _read_json(alerts / "elevenlabs_auth_circuit.json")
    personal_tasks = _read_json(alerts / "personal_task_check.json")
    shopping_list = _read_json(alerts / "shopping_list_check.json")
    home_assistant = _read_json(alerts / "home_assistant_check.json")
    document_vault = _read_json(alerts / "document_vault_check.json")
    email = _read_json(alerts / "email_check.json")
    device_sync = _read_json(alerts / "device_sync_check.json")
    mobile_client = _read_json(alerts / "mobile_client_check.json")
    mobile_gateway = _read_json(alerts / "mobile_gateway_check.json")
    stability = health.get("stability_summary") if isinstance(health.get("stability_summary"), Mapping) else {}
    market = health.get("market_realtime") if isinstance(health.get("market_realtime"), Mapping) else {}
    allowed_markets = {
        str(value).strip().lower() for value in market.get("allowed_markets", []) if str(value).strip()
    }
    blocked_markets = {
        str(value).strip().lower() for value in market.get("blocked_markets", []) if str(value).strip()
    }
    external_blocking = bool(stability.get("external_blocking"))
    core_recovered = bool(stability.get("core_recovered_sustained")) and str(
        stability.get("core_recovery_state") or ""
    ).upper() == "RECOVERED"

    phase1_blockers: list[str] = []
    if not core_recovered:
        recovery_state = str(stability.get("core_recovery_state") or "UNKNOWN").upper()
        streak = int(stability.get("current_core_streak_count") or 0)
        required = int(stability.get("core_recovery_required_streak") or 0)
        remaining = int(stability.get("core_recovery_cycles_remaining") or max(0, required - streak))
        if recovery_state == "PENDING" and required > 0:
            phase1_blockers.append(
                f"Recuperación sostenida del núcleo pendiente: {streak}/{required} ciclos OK; faltan {remaining}."
            )
        else:
            phase1_blockers.append(f"Núcleo sin aceptación sostenida: estado {recovery_state}.")
    if "stock" in blocked_markets:
        phase1_blockers.append(
            "Acciones premium bloqueadas: Alpaca AUTH_INVALID o proveedor equivalente ausente; "
            "validar con tools/provider_credential_setup.py alpaca."
        )
    if output_maintenance.get("external_snapshot_degraded") is True or (
        isinstance(output_maintenance.get("hygiene_summary"), Mapping)
        and output_maintenance["hygiene_summary"].get("external_snapshot_degraded") is True
    ):
        phase1_blockers.append("Snapshots externos RoxyData no responden dentro del timeout.")
    phase1_status = "ACCEPTED" if core_recovered and not external_blocking else (
        "PARTIAL_EXTERNAL" if core_recovered else "INCOMPLETE"
    )

    responsive_ok = (
        str(responsive.get("status") or "").upper() == "OK"
        and int(responsive.get("passed") or 0) >= 42
        and int(responsive.get("failed") or 0) == 0
    )
    phase2_status = "ACCEPTED_LOCAL" if responsive_ok else "INCOMPLETE"

    crypto_allowed = "crypto" in allowed_markets
    stocks_allowed = "stock" in allowed_markets
    if crypto_allowed and stocks_allowed:
        phase3_status = "ACCEPTED"
    elif crypto_allowed:
        phase3_status = "PARTIAL_MARKET"
    else:
        phase3_status = "INCOMPLETE"

    chart_checks = {
        name: _named_check_status(health, name)
        for name in (
            "chart_indicators",
            "chart_realtime_health_report",
            "dashboard_render_probe",
            "dashboard_search_render_probe",
            "dual_chart_crosshair_probe",
        )
    }
    charts_ok = str(chart_health.get("status") or "").upper() == "OK" and all(
        value == "OK" for value in chart_checks.values()
    )
    phase4_status = (
        "ACCEPTED" if charts_ok and stocks_allowed else
        "ACCEPTED_CRYPTO_PARTIAL_STOCK" if charts_ok and crypto_allowed else
        "INCOMPLETE"
    )

    opportunity_checks = {
        name: _named_check_status(health, name)
        for name in ("smart_alert_contract", "price_alert_monitor", "opportunity_sync", "opportunity_lifecycle")
    }
    opportunities_ok = str(opportunity_sync.get("status") or "").upper() == "OK" and all(
        value == "OK" for value in opportunity_checks.values()
    )
    phase5_status = (
        "ACCEPTED" if opportunities_ok and stocks_allowed else
        "ACCEPTED_CRYPTO_PARTIAL_STOCK" if opportunities_ok and crypto_allowed else
        "INCOMPLETE"
    )

    voice_evidence = {name: _read_json(alerts / name) for name in VOICE_EVIDENCE_FILES}
    voice_local_ok = all(str(payload.get("status") or "").upper() == "OK" for payload in voice_evidence.values())
    elevenlabs_blocked = str(elevenlabs_circuit.get("state") or "").upper() == "AUTH_INVALID"
    phase6_status = (
        "ACCEPTED" if voice_local_ok and not elevenlabs_blocked else
        "ACCEPTED_LOCAL_PARTIAL_EXTERNAL" if voice_local_ok else
        "INCOMPLETE"
    )
    personal_tasks_ok = str(personal_tasks.get("status") or "").upper() == "OK"
    shopping_list_ok = str(shopping_list.get("status") or "").upper() == "OK"
    home_contract_ok = str(home_assistant.get("contract_status") or "").upper() == "OK"
    home_connected = bool(home_assistant.get("connected"))
    document_contract_ok = str(document_vault.get("contract_status") or "").upper() == "OK"
    document_encrypted = bool(document_vault.get("at_rest_encryption"))
    email_contract_ok = str(email.get("contract_status") or "").upper() == "OK"
    email_connected = bool(email.get("connected"))
    device_sync_contract_ok = str(device_sync.get("contract_status") or "").upper() == "OK"
    device_sync_remote_ready = str(device_sync.get("remote_status") or "").upper() == "CONNECTED"
    mobile_client_ok = str(mobile_client.get("contract_status") or "").upper() == "OK"
    mobile_gateway_ready = (
        str(mobile_gateway.get("contract_status") or "").upper() == "OK"
        and str(mobile_gateway.get("gateway_status") or "").upper() in {"READY_FOR_PHYSICAL_TEST", "CONNECTED_PHYSICAL"}
    )
    mobile_gateway_physical = str(mobile_gateway.get("physical_reachability") or "").upper() == "VERIFIED_REMOTE_CLIENT"

    phase7_proven = ["Calendario, actividad, memoria y notificaciones disponibles."]
    if personal_tasks_ok:
        phase7_proven.append("Tareas personales durables, aisladas por usuario y compartidas con voz/texto.")
    if shopping_list_ok:
        phase7_proven.append("Lista de compras durable, deduplicada y compartida con voz/texto.")
    if device_sync_contract_ok:
        phase7_proven.append("Tareas, compras, watchlists y estado UI tienen sincronización revisionada con conflictos explícitos.")
    if mobile_client_ok:
        phase7_proven.append("Cliente móvil PWA opera los cuatro ámbitos sin persistir token ni snapshots sensibles.")
    if mobile_gateway_ready:
        phase7_proven.append(
            "Gateway móvil HTTPS, Bearer, allowlist y cliente remoto verificados."
            if mobile_gateway_physical
            else "Gateway móvil HTTPS, Bearer y allowlist verificados localmente y listo para prueba física."
        )
    if home_contract_ok:
        phase7_proven.append("Adaptador Home Assistant fail-closed con lectura y controles protegidos.")
    if document_contract_ok:
        phase7_proven.append(
            "Repositorio documental privado con contenido AES-256-GCM."
            if document_encrypted else "Repositorio documental privado, íntegro y aislado por usuario."
        )
    if email_contract_ok:
        phase7_proven.append("Adaptador Gmail metadata-only con envío bloqueado.")
    phase7_blockers: list[str] = []
    if not mobile_gateway_physical:
        if mobile_gateway_ready:
            phase7_blockers.append("Instalar y confiar la CA local, y validar acceso desde iPad/teléfono físico.")
        elif device_sync_contract_ok and not device_sync_remote_ready:
            phase7_blockers.append("Transporte remoto Bearer/HTTPS y validación en cliente móvil físico pendientes.")
        else:
            phase7_blockers.append("Sincronización remota personal y cliente móvil completo pendientes.")
    if home_contract_ok and not home_connected:
        phase7_blockers.append(
            "Home Assistant requiere URL/token reales; validar con tools/provider_credential_setup.py home_assistant."
        )
    if not document_encrypted:
        phase7_blockers.append("Documentos requieren cifrado en reposo antes de sincronización remota.")
    if not email_connected:
        phase7_blockers.append(
            "Correo requiere OAuth readonly real para Gmail o Outlook; validar con "
            "tools/provider_credential_setup.py gmail|outlook; "
            "envío permanece deshabilitado."
        )
    phase7_evidence = ["docs/platform_audit_2026-07-18.md#fase-7--ecosistema"]
    for condition, name in (
        (personal_tasks_ok, "personal_task_check.json"),
        (shopping_list_ok, "shopping_list_check.json"),
        (device_sync_contract_ok, "device_sync_check.json"),
        (mobile_client_ok, "mobile_client_check.json"),
        (mobile_gateway_ready, "mobile_gateway_check.json"),
        (home_contract_ok, "home_assistant_check.json"),
        (document_contract_ok, "document_vault_check.json"),
        (email_contract_ok, "email_check.json"),
    ):
        if condition:
            phase7_evidence.append(f"alerts/{name}")

    phases = [
        _phase(
            1,
            "Auditoría y estabilización",
            phase1_status,
            ["Core recuperado de forma sostenida."] if core_recovered else (
                ["Runtime actual del núcleo en OK; ventana sostenida aún pendiente."]
                if str(stability.get("core_runtime_status") or "").upper() == "OK"
                else []
            ),
            phase1_blockers,
            ["alerts/roxy_realtime_check.json", "alerts/output_maintenance.json"],
        ),
        _phase(
            2,
            "Sistema visual y navegación",
            phase2_status,
            [f"Matriz responsive {int(responsive.get('passed') or 0)}/42."] if responsive_ok else [],
            [] if responsive_ok else ["Matriz responsive ausente, incompleta o fallida."],
            ["alerts/responsive_route_matrix.json"],
        ),
        _phase(
            3,
            "Infraestructura de datos",
            phase3_status,
            [f"Mercados permitidos: {', '.join(sorted(allowed_markets)) or 'ninguno'}."],
            [f"Mercados bloqueados: {', '.join(sorted(blocked_markets))}."] if blocked_markets else [],
            ["alerts/roxy_realtime_check.json#market_realtime"],
        ),
        _phase(
            4,
            "Gráficas profesionales",
            phase4_status,
            ["Salud de gráficas, indicadores, probes y cursor sincronizado en OK."] if charts_ok else [],
            ["Falta repetir aceptación con datos bursátiles autenticados."] if charts_ok and not stocks_allowed else [],
            ["alerts/chart_realtime_health.json", "alerts/dashboard_render_probe.json"],
        ),
        _phase(
            5,
            "Estrategias y oportunidades",
            phase5_status,
            ["Alertas, sincronización y ciclo de vida en OK."] if opportunities_ok else [],
            ["Cobertura bursátil bloqueada por proveedor premium."] if opportunities_ok and not stocks_allowed else [],
            ["alerts/opportunity_sync.json", "alerts/opportunity_lifecycle.json"],
        ),
        _phase(
            6,
            "Cerebro y voz",
            phase6_status,
            ["Contexto, timeframe, watchlist y seguridad local de voz probados."] if voice_local_ok else [],
            [
                "ElevenLabs AUTH_INVALID; fallback local activo. "
                "Rotar con tools/provider_credential_setup.py elevenlabs."
            ] if elevenlabs_blocked else [],
            [f"alerts/{name}" for name in VOICE_EVIDENCE_FILES],
        ),
        _phase(
            7,
            "Ecosistema",
            "IN_PROGRESS",
            phase7_proven,
            phase7_blockers,
            phase7_evidence,
        ),
    ]
    accepted_count = sum(1 for item in phases if item["accepted"])
    partial_count = sum(1 for item in phases if str(item["status"]).startswith(("PARTIAL", "ACCEPTED_")))
    incomplete_count = len(phases) - accepted_count - partial_count
    current = now or datetime.now(timezone.utc)
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": current.astimezone(timezone.utc).isoformat(),
        "status": "ACCEPTED" if accepted_count == len(phases) else "IN_PROGRESS",
        "ready_for_full_vision": accepted_count == len(phases),
        "accepted_count": accepted_count,
        "partial_count": partial_count,
        "incomplete_count": incomplete_count,
        "phase_count": len(phases),
        "core_recovered": core_recovered,
        "external_blocking": external_blocking,
        "allowed_markets": sorted(allowed_markets),
        "blocked_markets": sorted(blocked_markets),
        "phases": phases,
    }


def write_acceptance_report(payload: Mapping[str, Any], path: str | Path) -> Path:
    target = Path(path)
    serialized = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(serialized, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Roxy's evidence-backed phase acceptance snapshot.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_platform_acceptance(args.root)
    path = write_acceptance_report(payload, args.output)
    print(
        f"Platform acceptance: {payload['status']} | accepted {payload['accepted_count']}/"
        f"{payload['phase_count']} | partial {payload['partial_count']} | {path}"
    )
    return 0 if payload["status"] == "ACCEPTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
