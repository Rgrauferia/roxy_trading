"""Export snapshot points to CSV per-user or global.

Usage:
  python tools/snapshot_exporter.py --once
  python tools/snapshot_exporter.py --interval 60
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import storage
import pandas as pd

OUT = Path("output")
OUT.mkdir(parents=True, exist_ok=True)


def export_all(db_path: str = storage.DB_PATH) -> list[Path]:
    rows = storage.list_accounts(path=db_path)
    written = []
    for user, created_ts, equity in rows:
        pts = storage.get_snapshot_points(user=user, path=db_path)
        if not pts:
            continue
        df = pd.DataFrame(pts, columns=["user", "ts", "equity"])  # type: ignore
        df["ts"] = pd.to_datetime(df["ts"])
        fn = OUT / f"snapshots_{user}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
        df.to_csv(fn, index=False)
        written.append(fn)
    return written


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--db", default=storage.DB_PATH)
    args = p.parse_args(argv)
    if args.once:
        files = export_all(db_path=args.db)
        for f in files:
            print("Wrote", f)
        return 0
    # otherwise run once (scheduler recommended externally)
    files = export_all(db_path=args.db)
    for f in files:
        print("Wrote", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
