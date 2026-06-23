from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_SOURCE = Path.home() / "Parallels" / "Windows 11.pvm"
DEFAULT_TARGET = Path("/Volumes/RoxyData/MacArchive/Parallels/Windows 11.pvm")
PARALLELS_PROCESS_PATTERNS = ("Parallels Desktop", "prl_client_app", "prl_disp_service", "prl_vm_app")


def parallels_processes_running() -> list[str]:
    try:
        result = subprocess.run(["pgrep", "-alf", "Parallels|prl_"], capture_output=True, text=True, check=False)
    except Exception:
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [
        line
        for line in lines
        if any(pattern in line for pattern in PARALLELS_PROCESS_PATTERNS)
        and "move_parallels_vm_to_external.py" not in line
    ]


def move_vm(source: Path, target: Path, *, dry_run: bool = False) -> dict[str, object]:
    running = parallels_processes_running()
    if running:
        return {
            "status": "blocked",
            "reason": "Parallels is running; close Windows/Parallels before moving the VM.",
            "processes": running,
            "source": str(source),
            "target": str(target),
        }
    if source.is_symlink():
        return {
            "status": "already_linked",
            "source": str(source),
            "target": os.readlink(source),
        }
    if not source.exists():
        return {
            "status": "missing",
            "reason": "Source VM not found.",
            "source": str(source),
            "target": str(target),
        }
    if target.exists():
        return {
            "status": "target_exists",
            "reason": "Target already exists; refusing to overwrite.",
            "source": str(source),
            "target": str(target),
        }
    if dry_run:
        return {"status": "dry_run", "source": str(source), "target": str(target)}

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    source.symlink_to(target, target_is_directory=True)
    return {"status": "moved", "source": str(source), "target": str(target)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move the Parallels Windows VM to the external RoxyData disk and leave a symlink.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = move_vm(Path(args.source), Path(args.target), dry_run=args.dry_run)
    print(result)
    if result["status"] == "blocked":
        raise SystemExit(2)
    if result["status"] in {"missing", "target_exists"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
