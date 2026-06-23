from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from roxy_autopilot import CODE_WRITE_ENV, run_autopilot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Roxy Autopilot health, learning and self-improvement cycle.")
    parser.add_argument("--apply", action="store_true", help=f"Apply safe strategy overrides when {CODE_WRITE_ENV}=1.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_autopilot(apply=args.apply)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    applied_count = sum(1 for item in report.get("applied", []) if item.get("applied"))
    print(
        "Roxy Autopilot: "
        f"{report.get('status')} | proposals={report.get('proposal_count')} | applied={applied_count} | "
        f"code_write={'ON' if report.get('code_write_enabled') else 'OFF'}"
    )
    print("Status: alerts/roxy_autopilot_status.json")


if __name__ == "__main__":
    main()
