"""CLI utilities for rotating keys and exporting rotation reports."""
import argparse
import csv
from datetime import datetime
from tools import secrets_service as ss


def cmd_rotate_expired(args):
    ss.rotate_expired_api_keys_job()
    print("Rotation job executed")


def cmd_export_revisions(args):
    out = args.out or 'rotation_report.csv'
    conn = ss._conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT s.name, r.version, r.rotated_by, r.rotated_at, r.reason FROM secret_revisions r JOIN secrets s ON s.id=r.secret_id ORDER BY r.rotated_at DESC")
        rows = cur.fetchall()
        with open(out, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['secret','version','rotated_by','rotated_at','reason'])
            for r in rows:
                w.writerow(r)
    finally:
        conn.close()
    print(f"Wrote {out}")


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers()
    r1 = sp.add_parser('rotate-expired')
    r1.set_defaults(cmd=cmd_rotate_expired)
    r2 = sp.add_parser('export-revisions')
    r2.add_argument('--out', help='output CSV file')
    r2.set_defaults(cmd=cmd_export_revisions)

    args = p.parse_args()
    if not hasattr(args, 'cmd'):
        p.print_help()
        return
    args.cmd(args)


if __name__ == '__main__':
    main()
