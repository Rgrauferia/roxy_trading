import os
import sqlite3
import tempfile
from tools import db_migration


def test_migrate_sessions_adds_columns(tmp_path):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    try:
        cur = conn.cursor()
        # create a minimal sessions table missing the new columns
        cur.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT NOT NULL UNIQUE, username TEXT, provider TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, expires_at DATETIME)")
        conn.commit()
    finally:
        conn.close()

    # run migration
    db_migration.migrate_sessions_schema(str(db_file))

    # verify columns exist
    conn = sqlite3.connect(str(db_file))
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(sessions)")
        cols = [r[1] for r in cur.fetchall()]
        assert 'encrypted_token' in cols
        assert 'scopes' in cols
    finally:
        conn.close()
