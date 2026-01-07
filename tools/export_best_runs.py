#!/usr/bin/env python3
"""Export top N backtest runs to individual JSON files and generate a combined plot.

Usage: python tools/export_best_runs.py --top 5
"""
from __future__ import annotations
import sqlite3, json, os, argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

os.makedirs('output/backtests', exist_ok=True)
os.makedirs('output/plots', exist_ok=True)

p = argparse.ArgumentParser()
p.add_argument('--top', type=int, default=3)
args = p.parse_args()

DB = 'db/roxy.db'
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT name, metrics_json FROM backtests ORDER BY json_extract(metrics_json,'$.realized_pnl') DESC LIMIT ?", (args.top,))
rows = cur.fetchall()

combined = []
for name, metrics_json in rows:
    try:
        m = json.loads(metrics_json)
    except Exception:
        continue
    outp = os.path.join('output','backtests', f"{name}.json")
    with open(outp,'w') as f:
        json.dump(m, f, indent=2)
    eq = m.get('equity_curve')
    if eq:
        combined.append((name, eq))

# combined plot
if combined:
    plt.figure(figsize=(10,6))
    for name, eq in combined:
        plt.plot(eq, label=name)
    plt.legend()
    plt.title('Top backtest equity curves')
    plt.grid(True, linewidth=0.3)
    plt.tight_layout()
    plt.savefig('output/plots/top_backtests_compare.png', dpi=180)

print('Exported', len(rows), 'runs to output/backtests and plotted', len(combined))
conn.close()
