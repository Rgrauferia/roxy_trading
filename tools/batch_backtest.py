"""Run batch backtests over recent CSVs and aggregate metrics.

Usage: python tools/batch_backtest.py --limit 5 --buy-score 55
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime

import pandas as pd
import sys

# ensure repo root is importable when running as a script
sys.path.insert(0, os.getcwd())
from backtester import run_backtest


def find_csvs(pattern: str = "output/*.csv", limit: int = 5):
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return files[:limit]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pattern", default="output/*.csv")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--buy-score", type=int, default=55)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    files = find_csvs(args.pattern, args.limit)
    results = {}
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            df = pd.read_csv(path)
        except Exception as e:
            results[name] = {"error": str(e)}
            continue
        metrics = run_backtest(df, buy_score=args.buy_score, name=name)
        results[name] = metrics

    out_path = args.out or f"output/backtest_batch_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(results, fh, indent=2)

    print(f"Wrote summary to {out_path}")


if __name__ == "__main__":
    main()
