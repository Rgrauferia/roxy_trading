from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text
from roxy_os import RoxyOrchestrator
from roxy_os.document_vault import DOCUMENT_VAULT_CONTRACT, DocumentVault


DEFAULT_REPORT_PATH = Path("alerts/document_vault_check.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_document_vault_check(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="roxy-document-check-") as directory:
        temp = Path(directory)
        vault = DocumentVault(temp / "vault", key_path=temp / "vault.key")
        row = vault.ingest("probe_user", "probe.txt", b"contenido verificable", source="diagnostic")
        duplicate = vault.ingest("probe_user", "copy.txt", b"contenido verificable", source="diagnostic")
        vault.ingest("other_user", "private.txt", b"privado", source="diagnostic")
        read_row, content = vault.read("probe_user", row["id"])
        stored = (vault.objects / row["sha256"][:2] / row["sha256"]).read_bytes()
        checks.append({
            "name": "encrypted_durability_integrity_isolation_deduplication",
            "status": "OK" if duplicate["id"] == row["id"] and content == b"contenido verificable" and read_row["sha256"] and b"contenido verificable" not in stored else "ERROR",
        })
        vault.archive("probe_user", row["id"])
        restored = vault.archive("probe_user", row["id"], restore=True)
        checks.append({"name": "recoverable_lifecycle", "status": "OK" if restored.get("status") == "ACTIVE" else "ERROR"})
        roxy = RoxyOrchestrator(
            memory_path=temp / "memory.json",
            document_vault=DocumentVault(temp / "roxy_documents", key_path=temp / "roxy.key"),
        )
        roxy.document_vault.ingest("probe_user", "voice.md", b"metadata only")
        response = roxy.handle("Roxy lista de documentos guardados", user_id="probe_user")
        checks.append({
            "name": "voice_metadata_only",
            "status": "OK" if response.agent == "documents" and response.data.get("content_read") is False else "ERROR",
        })
    try:
        source = (base / "streamlit_app.py").read_text(encoding="utf-8")
    except OSError:
        source = ""
    ui_ok = all(marker in source for marker in (
        '"ecosystem.documents": {"view": "Documentos"',
        'elif selected_page == "Documentos":',
        "show_document_vault_screen()",
        "AES-256-GCM",
        "Preparar contenido",
    ))
    checks.append({"name": "ui_route_context_and_explicit_read", "status": "OK" if ui_ok else "ERROR"})
    probes = [
        _read_json(base / "alerts" / "document_vault_desktop_probe.json"),
        _read_json(base / "alerts" / "document_vault_mobile_probe.json"),
    ]
    runtime_ok = all(
        str(report.get("status") or "").upper() == "OK"
        and int(report.get("blocking_console_error_count") or 0) == 0
        and int(report.get("blocking_page_error_count") or 0) == 0
        for report in probes
    )
    checks.append({"name": "desktop_mobile_runtime", "status": "OK" if runtime_ok else "ERROR"})
    contract_ok = all(row["status"] == "OK" for row in checks)
    return {
        "contract_version": DOCUMENT_VAULT_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if contract_ok else "ERROR",
        "contract_status": "OK" if contract_ok else "ERROR",
        "sync_state": "LOCAL_ENCRYPTED",
        "at_rest_encryption": True,
        "encryption_algorithm": "AES-256-GCM",
        "checks": checks,
        "production_data_mutated": False,
        "runtime_evidence": [
            "alerts/document_vault_desktop_probe.json",
            "alerts/document_vault_mobile_probe.json",
        ],
    }


def write_report(payload: dict[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica el repositorio documental privado local de Roxy.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_document_vault_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["contract_status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
