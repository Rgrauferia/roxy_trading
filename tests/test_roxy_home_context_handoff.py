"""Home handoff rejects stale/wrong-product state without changing any files."""
import json

import pytest

from tools.roxy_context_handoff import check


def fixture(root):
    (root / "data").mkdir()
    (root / "assets").mkdir()
    (root / "reports").mkdir()
    (root / "ROXY_CURRENT_STATE.md").write_text("# Roxy Home\n\n## 199 — publicado\n")
    payload = {"product": "roxy-home", "candidate_version": 199, "next_step": "Verificar respuesta real",
               "candidate_199": {"next_step": "Verificar respuesta real", "report": "reports/release.md"}}
    (root / "data/roxy_continuity.json").write_text(json.dumps(payload))
    (root / "reports/release.md").write_text("Evidencia sintética; no producción.")
    (root / "assets/roxy_list.html").write_text('<meta name="roxy-home-version" content="199" />')
    (root / "assets/roxy_list.js").write_text("const APP_VERSION = '199';")
    return payload


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_home_check_is_read_only_and_does_not_require_trading_data(tmp_path):
    fixture(tmp_path)
    before = snapshot(tmp_path)
    assert check(tmp_path)[0] == []
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["old_next_step", "old_js", "wrong_product", "missing_report", "invalid_json"])
def test_rejects_inconsistent_handoff_without_repairing_or_deleting(tmp_path, change):
    payload = fixture(tmp_path)
    if change == "old_next_step":
        payload["next_step"] = "Continuar versión 193"
    elif change == "wrong_product":
        payload["product"] = "roxy-trading"
    elif change == "missing_report":
        payload["candidate_199"]["report"] = "reports/missing.md"
    elif change == "old_js":
        (tmp_path / "assets/roxy_list.js").write_text("const APP_VERSION = '193';")
    (tmp_path / "data/roxy_continuity.json").write_text("{" if change == "invalid_json" else json.dumps(payload))
    before = snapshot(tmp_path)
    assert check(tmp_path)[0]
    assert snapshot(tmp_path) == before
