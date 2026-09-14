"""Loopback-only Home QA with a real, private, synthetic PostgreSQL cluster.

Not included in the production image. Reuses the real PostgreSQL test harness,
not a repository double. No remote DSN or product credentials are accepted.
Both SQL and household files remain on disk after shutdown for review/restart.

Run with the Home QA venv (pytest, psycopg, cryptography and Home requirements):
    python -m tools.roxy_home_fitness_plan_preview --pg-bin /path/to/pg/bin
Use the printed --state-dir on a later run to preserve the same synthetic data.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MARKER = "roxy-home-fitness-synthetic-preview-v1"


def _private_json(path: Path, payload: dict) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(payload, handle)


def _harness():
    # The QA harness owns initdb, TLS and separate owner/runtime roles. Importing
    # it does not start a server, load product variables or execute its tests.
    spec = importlib.util.spec_from_file_location(
        "roxy_home_local_postgres_qa", ROOT / "tests/test_roxy_home_fitness_postgres_integration.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_migrations(cluster) -> list[str]:
    journal = cluster.directory / "preview-migrations.json"
    applied = json.loads(journal.read_text()) if journal.exists() else ["001_foundation.sql"]
    with cluster.connect("fitness_owner", autocommit=True) as connection:
        for migration in sorted((ROOT / "migrations/fitness").glob("[0-9][0-9][0-9]_*.sql")):
            if migration.name not in applied:
                connection.execute(migration.read_text())
                applied.append(migration.name)
                journal.write_text(json.dumps(applied))
                journal.chmod(0o600)
        # Explicit grants for the existing member tables. Later migrations may
        # add member-owned tables; grant DML only where FORCE RLS is active.
        tables = connection.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='roxy_home_fitness' AND c.relkind='r' "
            "AND c.relrowsecurity AND c.relforcerowsecurity"
        ).fetchall()
        for (name,) in tables:
            connection.execute(cluster.driver.sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON roxy_home_fitness.{} TO fitness_runtime"
            ).format(cluster.driver.sql.Identifier(name)))
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged loopback port.")
    binaries = args.pg_bin.resolve()
    if not all((binaries / name).is_file() for name in ("postgres", "initdb", "pg_ctl")):
        parser.error("--pg-bin needs real PostgreSQL server binaries.")
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError:
            parser.error("The requested preview port is already in use.")

    # Discard inherited providers and PostgreSQL defaults only in this process.
    # A later local DSN is created exclusively from this cluster's random roles.
    for key in list(os.environ):
        if key.startswith(("ROXY_", "PG", "FAL_")) or "OPENAI" in key or "ELEVENLABS" in key or key.endswith("_API_KEY"):
            os.environ.pop(key)

    import psycopg
    import requests
    import uvicorn

    from tools.roxy_home_login_preview import preview_transport
    requests.sessions.Session.request = preview_transport(requests.sessions.Session.request, {})

    state = args.state_dir.resolve() if args.state_dir else Path(tempfile.mkdtemp(prefix="roxy-home-fitness-207-", dir="/tmp"))
    metadata_path = state / "synthetic-preview.json"
    if args.state_dir:
        if not metadata_path.is_file() or metadata_path.is_symlink():
            parser.error("Only a state directory created by this helper may be resumed.")
        stat = metadata_path.stat()
        if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            parser.error("The synthetic state needs owner-only permissions.")
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("kind") != MARKER:
            parser.error("This directory is not a synthetic Home fitness preview.")
    else:
        state.chmod(0o700)
        metadata = {"kind": MARKER, "session_key": secrets.token_urlsafe(32)}

    harness = _harness()
    database_directory = state / "postgres"
    database_directory.mkdir(mode=0o700, exist_ok=True)
    cluster = harness.LocalPostgres(database_directory, binaries, psycopg)
    original_directory = Path.cwd()
    started_here = False
    try:
        if args.state_dir:
            cluster.passwords = metadata["passwords"]
            cluster.port = metadata["postgres_port"]
            if (cluster.data / "postmaster.pid").exists():
                parser.error("This synthetic cluster is already running; stop its existing preview first.")
            harness._certificates(database_directory)
            cluster.start()
            started_here = True
        else:
            started_here = True
            cluster.initialize()
            metadata.update(passwords=cluster.passwords, postgres_port=cluster.port)
            _private_json(metadata_path, metadata)
        migrations = _apply_migrations(cluster)
        app_data = state / "home"
        app_data.mkdir(mode=0o700, exist_ok=True)
        os.chdir(app_data)
        os.environ.update(
            ROXY_HOME_API_KEY=metadata["session_key"],
            ROXY_STATE_SYNC_USERS="login-qa",
            ROXY_HOME_FITNESS_DATABASE_URL=cluster.dsn(),
            ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED="0",
            ROXY_HOME_VIDEO_ENABLED="0",
            ROXY_HOME_RECIPE_VIDEO_ENABLED="0",
        )
        from roxy_os.home_accounts import HomeAccountStore
        from tools import roxy_home_service as service

        service.SESSION_COOKIE = f"roxy_home_fitness_qa_session_{args.port}"

        def local_cookie(response, value):
            response.set_cookie(service.SESSION_COOKIE, value, httponly=True,
                                samesite="strict", path="/", max_age=3600)

        service._set_session_cookie = local_cookie
        store = HomeAccountStore("data/roxy_home_accounts.json")
        if not Path("data/roxy_home_accounts.json").exists():
            store.bootstrap("login-qa", household_name="Casa sintética · Ejercicio",
                            username="loginqa", display_name="Casa de prueba",
                            password="Local-QA-only-2026")

        print(f"Synthetic Home + real PostgreSQL only: {state}", flush=True)
        print("Applied local migrations: " + ", ".join(migrations), flush=True)
        print(f"Open: http://127.0.0.1:{args.port}/lista#ejercicio", flush=True)
        print("Synthetic login: loginqa / Local-QA-only-2026", flush=True)
        print("Data remains on disk after shutdown. Resume with --state-dir " + str(state), flush=True)
        uvicorn.run(service.app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        os.chdir(original_directory)
        if started_here:
            cluster.stop()


if __name__ == "__main__":
    main()
