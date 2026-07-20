from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from roxy_trader.strike_options_strategy import settle_expired_strike_signal_history, settle_strike_signal_history


def _parse_price_pair(value: str) -> tuple[str, float]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Use SYMBOL=PRICE, for example BTC=60074.29")
    symbol, price_text = value.split("=", 1)
    symbol = symbol.strip().upper()
    if not symbol:
        raise argparse.ArgumentTypeError("Symbol cannot be empty")
    try:
        price = float(price_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid price for {symbol}: {price_text}") from exc
    if price <= 0:
        raise argparse.ArgumentTypeError("Price must be positive")
    return symbol, price


def _pairs_to_dict(pairs: list[tuple[str, float]]) -> dict[str, float]:
    return {symbol: price for symbol, price in pairs}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Settle Roxy Strike Options signal journal with final market prices."
    )
    parser.add_argument(
        "--log",
        default="logs/strike_options_signals.jsonl",
        help="Source JSONL signal journal. Default: logs/strike_options_signals.jsonl",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSONL path. Defaults to overwriting --log.",
    )
    parser.add_argument(
        "--price",
        action="append",
        type=_parse_price_pair,
        default=[],
        help="Final settlement price as SYMBOL=PRICE. Can be repeated.",
    )
    parser.add_argument(
        "--payout",
        action="append",
        type=_parse_price_pair,
        default=[],
        help="Optional payout as SYMBOL=PAYOUT. Can be repeated.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON summary instead of a compact text summary.",
    )
    parser.add_argument(
        "--expired-only",
        action="store_true",
        help="Settle only signals whose timestamp + remaining time has already expired.",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="Optional ISO timestamp used with --expired-only. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--grace-seconds",
        type=int,
        default=0,
        help="Extra seconds to wait after expiration before settling with --expired-only.",
    )
    return parser.parse_args()


def compact_summary(result: dict[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    win_rate = summary.get("win_rate")
    win_rate_text = f"{win_rate * 100:.1f}%" if isinstance(win_rate, (int, float)) else "pendiente"
    return "\n".join(
        [
            f"Journal: {result.get('path')}",
            f"Senales cerradas: {result.get('settled', 0)}",
            f"Senales activas: {result.get('pending', 0)}",
            f"Filas sin cerrar: {result.get('skipped', 0)}",
            f"Win rate: {win_rate_text}",
            f"P/L paper: {summary.get('profit_loss', 0)}",
            f"Mejor timeframe: {summary.get('best_timeframe') or 'sin muestra'}",
            f"Mejor condicion: {summary.get('best_condition') or 'sin muestra'}",
        ]
    )


def main() -> int:
    args = parse_args()
    if not args.price:
        raise SystemExit("Add at least one --price SYMBOL=PRICE to settle pending signals.")
    settle_fn = settle_expired_strike_signal_history if args.expired_only else settle_strike_signal_history
    kwargs: dict[str, Any] = {
        "output_path": Path(args.output) if args.output else None,
        "payout_by_asset": _pairs_to_dict(args.payout),
    }
    if args.expired_only:
        kwargs["now"] = args.now
        kwargs["grace_seconds"] = max(0, args.grace_seconds)
    result = settle_fn(Path(args.log), _pairs_to_dict(args.price), **kwargs)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(compact_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
