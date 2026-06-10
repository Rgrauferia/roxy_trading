#!/usr/bin/env python3
"""Resume and complete a fine-grid sweep around top sweep runs.
Writes progress to output/fine_sweep_log.txt and summaries/plots when done.
"""
import sqlite3, json, os, re, subprocess, shlex, sys, time
os.makedirs('output', exist_ok=True)
os.makedirs('output/plots', exist_ok=True)
LOG='output/fine_sweep_log.txt'
DB='db/roxy.db'
CSV='output/synthetic_ohlcv.csv'
pat = re.compile(r"sweep_bs(\d+)_ps(\d+)p(\d+)")
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT name, json_extract(metrics_json,'$.realized_pnl') as pnl FROM backtests WHERE name LIKE 'sweep_bs%' ORDER BY pnl DESC LIMIT 3;")
rows = cur.fetchall()
if not rows:
    print('No top runs found; exiting')
    sys.exit(0)
new_runs = []
with open(LOG,'a') as log:
    log.write('\n=== START RUN %s ===\n' % time.asctime())
    for name, pnl in rows:
        m = pat.match(name)
        if not m:
            log.write(f'WARN: cannot parse {name}\n')
            continue
        bs = int(m.group(1))
        ps_str = f"{m.group(2)}.{m.group(3)}"
        ps = float(ps_str)
        bs_grid = [max(1, bs-4), max(1, bs-2), bs, bs+2, bs+4]
        ps_grid = [round(ps*0.5,6), ps, round(ps*1.5,6)]
        for b in sorted(set(bs_grid)):
            for p in sorted(set(ps_grid)):
                fine_name = f"fine_{name}_bs{b}_ps{str(p).replace('.','p')}"
                cur.execute("SELECT COUNT(1) FROM backtests WHERE name=?", (fine_name,))
                if cur.fetchone()[0]>0:
                    log.write(f'SKIP exists {fine_name}\n')
                    continue
                cmd = [sys.executable, 'backtester.py', CSV, '--name', fine_name, '--buy-score', str(b), '--position-size', str(p), '--warmup', '60']
                log.write('RUN: ' + ' '.join(cmd) + '\n')
                log.flush()
                try:
                    proc = subprocess.run(cmd, cwd='.', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    log.write(proc.stdout + '\n')
                except Exception as e:
                    log.write('ERROR running: ' + str(e) + '\n')
                new_runs.append(fine_name)
                # small sleep to avoid tight loop
                time.sleep(0.2)
    log.write('=== DONE SUBMISSIONS %s ===\n' % time.asctime())
# aggregate
out = []
for name in new_runs:
    cur.execute("SELECT id,name,ts,metrics_json FROM backtests WHERE name=?", (name,))
    r = cur.fetchone()
    if not r:
        continue
    id_, name, ts, metrics_json = r
    try:
        m = json.loads(metrics_json)
    except Exception:
        m = {}
    row = {'id': id_, 'name': name, 'ts': ts}
    for k,v in m.items():
        if k=='equity_curve':
            continue
        row[k]=v
    out.append(row)
with open('output/fine_sweep_summary.json','w') as f:
    json.dump(out,f,indent=2)
import csv
if out:
    keys = list({k for r in out for k in r.keys()})
    with open('output/fine_sweep_summary.csv','w',newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in out:
            w.writerow(r)
# plots
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    count=0
    for name in new_runs:
        cur.execute("SELECT metrics_json FROM backtests WHERE name=?", (name,))
        r = cur.fetchone()
        if not r:
            continue
        try:
            m = json.loads(r[0])
        except Exception:
            continue
        eq = m.get('equity_curve')
        if not eq:
            continue
        pnl = m.get('realized_pnl')
        plt.figure(figsize=(8,4))
        plt.plot(eq)
        plt.title(f"{name} pnl={pnl}")
        plt.grid(True, linewidth=0.3)
        outp = os.path.join('output','plots', f"{name}.png")
        plt.tight_layout()
        plt.savefig(outp,dpi=150)
        plt.close()
        count+=1
    with open(LOG,'a') as log:
        log.write(f'WROTE {count} fine plots\n')
except Exception as e:
    with open(LOG,'a') as log:
        log.write('PLOT ERROR: ' + str(e) + '\n')
conn.close()
print('Launched fine sweep runner; check', LOG)
