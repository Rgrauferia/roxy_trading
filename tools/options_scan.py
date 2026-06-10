from __future__ import annotations

import argparse
import glob
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from options_strategy import OptionSelectionConfig, fetch_scored_option_candidates
from roxy_paths import alerts_dir, output_dir


OUTPUT_DIR = output_dir()
ALERTS_DIR = alerts_dir()


def latest_confluence_path() -> Path | None:
    matches = sorted(
        (Path(path) for path in glob.glob(str(OUTPUT_DIR / "ma_confluence_*.csv"))),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def actionable_rows(df: pd.DataFrame, include_watch: bool = False) -> pd.DataFrame:
    if df.empty:
        return df
    data = df.copy()
    data = data[data["market"].eq("stock")]
    if include_watch:
        return data[data["signal"].isin(["BUY", "WATCH"])]
    return data[data["signal"].eq("BUY") & data["trade_decision"].astype(str).str.startswith("TRADE_FOR_")]


def build_options_candidates(df: pd.DataFrame, config: OptionSelectionConfig, *, include_watch: bool = False) -> pd.DataFrame:
    candidates = []
    for _, row in actionable_rows(df, include_watch=include_watch).iterrows():
        symbol = str(row["symbol"])
        underlying_price = _safe_float(row.get("entry"))
        target_pct = _safe_float(row.get("recommended_target_pct")) or 0.02
        if underlying_price is None or underlying_price <= 0:
            continue
        try:
            scored = fetch_scored_option_candidates(
                symbol,
                underlying_price=underlying_price,
                target_pct=target_pct,
                option_type="call",
                config=config,
            )
        except Exception as exc:
            candidates.append(
                pd.DataFrame(
                    [
                        {
                            "symbol": symbol,
                            "option_decision": "ERROR",
                            "option_score": 0,
                            "error": str(exc),
                            "underlying_price": underlying_price,
                            "target_pct": target_pct,
                        }
                    ]
                )
            )
            continue
        if scored.empty:
            continue
        scored = scored.copy()
        scored["underlying_signal"] = row.get("signal")
        scored["underlying_trade_decision"] = row.get("trade_decision")
        scored["underlying_confluence_score"] = row.get("confluence_score")
        scored["underlying_stop"] = row.get("stop")
        scored["underlying_risk_pct"] = row.get("risk_pct")
        candidates.append(scored)

    if not candidates:
        return pd.DataFrame()
    out = pd.concat(candidates, ignore_index=True)
    return out.sort_values(["option_decision", "option_score", "symbol"], ascending=[True, False, True]).reset_index(drop=True)


def build_summary(df: pd.DataFrame, source: str | Path | None, limit: int) -> dict[str, Any]:
    if df.empty:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "source": str(source) if source else None,
            "rows": 0,
            "candidate_count": 0,
            "symbols": [],
            "best": [],
        }
    candidates = df[df["option_decision"].eq("OPTION_CANDIDATE")].copy()
    best = candidates.sort_values(["option_score", "spread_pct"], ascending=[False, True]).head(limit)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "source": str(source) if source else None,
        "rows": int(len(df)),
        "candidate_count": int(len(candidates)),
        "symbols": sorted(df["symbol"].dropna().astype(str).unique().tolist()),
        "best": best.to_dict(orient="records"),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "Roxy Options Candidates Report",
        f"Generated: {summary.get('generated_at', '-')}",
        f"Source: {summary.get('source', '-')}",
        f"Rows: {summary.get('rows', 0)}",
        f"Candidates: {summary.get('candidate_count', 0)}",
        "",
        "Best contracts",
    ]
    best = summary.get("best", [])
    if not best:
        lines.append("- No option contracts passed the filters.")
    else:
        for row in best:
            lines.append(
                f"- {row.get('symbol')} {row.get('contractSymbol')} exp {row.get('expiry')} "
                f"strike {row.get('strike')} ask {row.get('ask')} delta {row.get('delta')} score {row.get('option_score')} "
                f"spread {(_safe_float(row.get('spread_pct')) or 0) * 100:.2f}% "
                f"vol {row.get('volume')} oi {row.get('openInterest')} "
                f"breakeven {row.get('breakeven_price')} max_loss ${row.get('max_loss_per_contract')}"
            )
    return "\n".join(lines) + "\n"


def print_table(df: pd.DataFrame, limit: int) -> None:
    if df.empty:
        print("No option candidates.")
        return
    display = df.head(limit)
    columns = [
        "symbol",
        "contractSymbol",
        "option_decision",
        "option_score",
        "expiry",
        "dte",
        "strike",
        "bid",
        "ask",
        "delta",
        "spread_pct",
        "volume",
        "openInterest",
        "moneyness_pct",
        "target_pct",
        "target_reaches_strike",
        "breakeven_price",
        "breakeven_pct",
        "risk_reward_at_target",
        "max_loss_per_contract",
    ]
    columns = [column for column in columns if column in display.columns]
    print(display[columns].to_string(index=False, max_colwidth=80))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select liquid option contracts from SMA confluence trade plans.")
    parser.add_argument("--confluence-csv", help="Confluence CSV. Defaults to latest output/ma_confluence_*.csv.")
    parser.add_argument("--include-watch", action="store_true")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--report-path", default=str(ALERTS_DIR / "options_report.txt"))
    parser.add_argument("--json-path", default=str(ALERTS_DIR / "options_summary.json"))
    parser.add_argument("--min-volume", type=int, default=50)
    parser.add_argument("--min-open-interest", type=int, default=100)
    parser.add_argument("--max-spread-pct", type=float, default=0.18)
    parser.add_argument("--min-dte", type=int, default=7)
    parser.add_argument("--max-dte", type=int, default=45)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.confluence_csv) if args.confluence_csv else latest_confluence_path()
    if not path or not path.exists():
        raise SystemExit("No confluence CSV found. Run tools/ma_confluence.py first.")

    config = OptionSelectionConfig(
        min_dte=args.min_dte,
        max_dte=args.max_dte,
        min_volume=args.min_volume,
        min_open_interest=args.min_open_interest,
        max_spread_pct=args.max_spread_pct,
    )
    confluence = pd.read_csv(path)
    candidates = build_options_candidates(confluence, config, include_watch=args.include_watch)
    print_table(candidates, args.limit)

    if args.save and not candidates.empty:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = output_dir / f"options_candidates_{ts}.csv"
        candidates.to_csv(out_path, index=False)
        print(f"\nSaved: {out_path}")

    summary = build_summary(candidates, path, args.limit)
    report = render_report(summary)
    Path(args.report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_path).write_text(report, encoding="utf-8")
    Path(args.json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_path).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Wrote report: {args.report_path}")
    print(f"Wrote summary: {args.json_path}")
    print(f"Option candidates: {summary['candidate_count']}")


if __name__ == "__main__":
    main()
