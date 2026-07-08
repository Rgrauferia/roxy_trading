from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from roxy_trader.strike_options_strategy import build_strike_learning_report, load_strike_signal_history


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Roxy's Strike Options learning report from the signal journal."
    )
    parser.add_argument(
        "--log",
        default="logs/strike_options_signals.jsonl",
        help="Source JSONL signal journal. Default: logs/strike_options_signals.jsonl",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum recent rows to read. Use 0 for all rows. Default: 500",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full learning report as JSON.",
    )
    return parser.parse_args()


def _fmt_pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "sin muestra"
    return f"{value * 100:.1f}%"


def _compact_items(items: list[dict[str, Any]], *, max_items: int = 3) -> list[str]:
    lines: list[str] = []
    for item in items[:max_items]:
        lines.append(
            f"- {item.get('key')}: win rate {_fmt_pct(item.get('win_rate'))}, "
            f"EV {item.get('expectancy', 'n/a')}, muestras {item.get('signals', 0)}"
        )
    return lines


def compact_report(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    policy = report.get("operational_policy") if isinstance(report.get("operational_policy"), dict) else {}
    strongest = report.get("strongest_conditions") if isinstance(report.get("strongest_conditions"), list) else []
    weakest = report.get("weakest_conditions") if isinstance(report.get("weakest_conditions"), list) else []
    timeframes = report.get("best_timeframes") if isinstance(report.get("best_timeframes"), list) else []
    recommendations = report.get("recommendations") if isinstance(report.get("recommendations"), list) else []

    lines = [
        "Roxy Strike Options - reporte de aprendizaje",
        f"Senales cerradas: {report.get('closed_signals', 0)}",
        f"Win rate global: {_fmt_pct(summary.get('win_rate'))}",
        f"Expectancy paper: {summary.get('expectancy', 'sin muestra')}",
        f"Mejor timeframe: {summary.get('best_timeframe') or 'sin muestra'}",
        f"Mejor condicion: {summary.get('best_condition') or 'sin muestra'}",
        f"Modo de riesgo: {policy.get('risk_mode', 'paper')}",
        f"Permitir senales verdes: {'si' if policy.get('allow_green_signals') else 'no'}",
        "",
        "Condiciones mas fuertes:",
        *(_compact_items(strongest) or ["- sin muestra suficiente"]),
        "",
        "Condiciones debiles:",
        *(_compact_items(weakest) or ["- sin muestra suficiente"]),
        "",
        "Timeframes con mejor comportamiento:",
        *(_compact_items(timeframes) or ["- sin muestra suficiente"]),
        "",
        "Recomendaciones operativas:",
    ]
    lines.extend(f"- {item}" for item in recommendations[:6])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    rows = load_strike_signal_history(args.log, limit=args.limit)
    report = build_strike_learning_report(rows)
    report["source_log"] = str(Path(args.log))
    report["rows_loaded"] = len(rows)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(compact_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
