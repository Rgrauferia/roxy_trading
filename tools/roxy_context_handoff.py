"""Read-only continuity check for the Home checkout; no private data or network."""
import argparse
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def check(root: Path):
    """Check only Home handoff files and local release markers, without mutations."""
    errors = []
    try:
        state = (root / "ROXY_CURRENT_STATE.md").read_text(encoding="utf-8")
        continuity = json.loads((root / "data/roxy_continuity.json").read_text(encoding="utf-8"))
        if not isinstance(continuity, dict) or continuity.get("product") != "roxy-home":
            return ["Este comprobador es exclusivo de Roxy Home."], {}
        version = continuity.get("candidate_version")
        if type(version) is not int or version <= 0:
            return ["candidate_version debe ser una versión positiva de Home."], continuity
        candidate = continuity.get(f"candidate_{version}")
        if not isinstance(candidate, dict):
            return [f"Falta el registro candidate_{version}."], continuity
        if not state.startswith("# Roxy Home"):
            errors.append("ROXY_CURRENT_STATE.md no identifica Roxy Home.")
        if not re.search(rf"^## {version}\b", state, re.MULTILINE):
            errors.append(f"El estado no contiene la entrega {version}.")
        next_step = continuity.get("next_step")
        if not isinstance(next_step, str) or not next_step.strip():
            errors.append("Falta next_step.")
        elif candidate.get("next_step") and next_step != candidate["next_step"]:
            errors.append("next_step está desactualizado frente a la entrega vigente.")
        report = candidate.get("report")
        if not isinstance(report, str) or not report.startswith("reports/") or ".." in Path(report).parts:
            errors.append("La entrega debe referenciar un informe local en reports/.")
        elif not (root / report).is_file():
            errors.append(f"Falta el informe de la entrega {version}.")
        html = (root / "assets/roxy_list.html").read_text(encoding="utf-8")
        js = (root / "assets/roxy_list.js").read_text(encoding="utf-8")
        html_version = re.search(r'name="roxy-home-version"\s+content="(\d+)"', html)
        js_version = re.search(r"\bconst\s+APP_VERSION\s*=\s*['\"](\d+)['\"]", js)
        if not html_version or html_version[1] != str(version):
            errors.append("La versión HTML no coincide con candidate_version.")
        if not js_version or js_version[1] != str(version):
            errors.append("APP_VERSION no coincide con candidate_version.")
    except (OSError, ValueError):
        return ["No se pudo leer la continuidad local completa; no se modificó ningún archivo."], {}
    return errors, continuity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    errors, continuity = check(ROOT)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"OK: Roxy Home {continuity['candidate_version']} — continuidad local coherente.")
    print(f"Worktree: {ROOT}")
    print(f"Siguiente paso: {continuity['next_step']}")
    result = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        print("ERROR: no se pudo comprobar git status; revisar antes de editar.")
        return 1
    print(f"Cambios existentes que preservar: {len(result.stdout.splitlines())} entradas de git status.")
    print("Sólo consulta local. No valida producción, saldo, proveedores ni datos privados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
