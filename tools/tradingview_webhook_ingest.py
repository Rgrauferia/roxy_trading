#!/usr/bin/env python3
"""Append a TradingView alert payload to Roxy's local webhook journal.

Usage:
  echo '{"symbol":"AAPL","timeframe":"15","signal":"BUY","price":185}' \
    | .venv/bin/python tools/tradingview_webhook_ingest.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tradingview_webhooks import DEFAULT_WEBHOOK_PATH, append_tradingview_webhook


def _read_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.json:
        text = args.json
    else:
        text = sys.stdin.read()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise SystemExit("TradingView payload must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest one TradingView webhook payload into Roxy.")
    parser.add_argument("--file", help="Path to a JSON payload file.")
    parser.add_argument("--json", help="Inline JSON payload.")
    parser.add_argument("--path", default=str(DEFAULT_WEBHOOK_PATH), help="Output JSONL path.")
    args = parser.parse_args()
    row = append_tradingview_webhook(_read_payload(args), path=args.path)
    print(json.dumps({key: row.get(key) for key in ("duplicate", "symbol", "timeframe", "signal", "received_at")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
