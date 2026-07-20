#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from roxy_os import RoxyOrchestrator


DEFAULT_MEMORY_PATH = Path("data/roxy_os_memory.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a safe local Roxy OS command.")
    parser.add_argument("command", nargs="+", help="Command to send to Roxy, for example: Hola Roxy clima en Miami")
    parser.add_argument("--user", default="local_user", help="Memory scope user id.")
    parser.add_argument("--page", default="CLI", help="Current surface/page context.")
    parser.add_argument("--module", default="local-assistant", help="Current Roxy module context.")
    parser.add_argument("--symbol", default="", help="Optional market symbol context.")
    parser.add_argument("--market", default="", help="Optional market context.")
    parser.add_argument("--timeframe", default="", help="Optional timeframe context.")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Allow a permission for this command, for example --allow file_read.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full response as JSON.")
    parser.add_argument("--memory", default=str(DEFAULT_MEMORY_PATH), help="Memory file path.")
    return parser


def context_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "surface": "cli",
        "page": args.page,
        "module": args.module,
        "symbol": args.symbol or None,
        "market": args.market or None,
        "timeframe": args.timeframe or None,
        "allowed_permissions": args.allow,
        "authenticated": True,
    }


def main() -> int:
    args = build_parser().parse_args()
    command = " ".join(args.command).strip()
    roxy = RoxyOrchestrator(memory_path=args.memory)
    response = roxy.handle(command, user_id=args.user, context=context_from_args(args))
    payload = response.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"Roxy OS · {payload['agent']} · {payload['intent']}")
    print(response.message)
    permission = payload.get("permission") or {}
    if permission:
        print(f"Permiso: {permission.get('mode')} · riesgo: {permission.get('risk_level')}")
    actions = payload.get("actions") or []
    if actions:
        print("Acciones preparadas:")
        for action in actions:
            print(f"- {action.get('type')}: {json.dumps(action, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
