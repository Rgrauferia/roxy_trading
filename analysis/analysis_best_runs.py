# Simple analysis script for top backtest runs
import sqlite3, json, os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

os.makedirs('analysis', exist_ok=True)
DB='db/roxy.db'
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT name, metrics_json FROM backtests ORDER BY json_extract(metrics_json,'$.realized_pnl') DESC LIMIT 5")
rows = cur.fetchall()
summary = []
for name, mj in rows:
    m = json.loads(mj)
    eq = m.get('equity_curve')
    trades = m.get('trades',0)
    pnl = m.get('realized_pnl',0)
    sharpe = m.get('sharpe',0)
    cagr = m.get('cagr',0)
    summary.append({'name':name,'trades':trades,'realized_pnl':pnl,'sharpe':sharpe,'cagr':cagr})
    if eq:
        s = pd.Series(eq)
        s.plot(title=name)
        plt.savefig(f'output/plots/analysis_{name}.png')
        plt.clf()

pd.DataFrame(summary).to_csv('output/analysis_best_runs.csv', index=False)
print('WROTE output/analysis_best_runs.csv and plots')
conn.close()
