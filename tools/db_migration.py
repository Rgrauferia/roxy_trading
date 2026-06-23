"""DB migration helpers for secrets/session schema.

This module provides a function to add missing columns to an existing
`sessions` table and to create the oauth_states table if missing. It's
intended to be safe to run during deployment.
"""
import sqlite3
import os
from typing import Optional


def migrate_sessions_schema(db_path: Optional[str] = None) -> None:
    db = db_path or os.path.join(os.getcwd(), "db", "roxy.db")
    conn = sqlite3.connect(db)
    try:
        cur = conn.cursor()
        # ensure sessions table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        if not cur.fetchone():
            # nothing to migrate
            return
        cur.execute("PRAGMA table_info(sessions)")
        cols = [r[1] for r in cur.fetchall()]
        if 'encrypted_token' not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN encrypted_token BLOB")
        if 'scopes' not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN scopes TEXT")
        if 'last_used' not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN last_used DATETIME")
        if 'refresh_token_hash' not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN refresh_token_hash TEXT")
        if 'refresh_expires_at' not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN refresh_expires_at DATETIME")
        if 'refresh_revoked' not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN refresh_revoked INTEGER DEFAULT 0")
        # ensure oauth_results exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='oauth_results'")
        if not cur.fetchone():
            cur.execute(
                "CREATE TABLE oauth_results (id INTEGER PRIMARY KEY AUTOINCREMENT, state TEXT NOT NULL UNIQUE, username TEXT, session_token TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
        # ensure oauth_states exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='oauth_states'")
        if not cur.fetchone():
            cur.execute(
                "CREATE TABLE oauth_states (id INTEGER PRIMARY KEY AUTOINCREMENT, state TEXT NOT NULL UNIQUE, redirect_uri TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, expires_at DATETIME)"
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument('--db', help='path to sqlite db', default=None)
    args = p.parse_args()
    migrate_sessions_schema(args.db)
    print('migration complete')
