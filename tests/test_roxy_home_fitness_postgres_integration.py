"""Real PostgreSQL tests, exclusively against a freshly created local cluster.

Run with psycopg[binary], cryptography and PostgreSQL initdb/pg_ctl installed:
    ROXY_FITNESS_TEST_PG_BIN=/path/to/postgres/bin python -m pytest -q -rs \
        tests/test_roxy_home_fitness_postgres_integration.py

No external DSN or product environment is read. Missing binaries/dependencies are
an explicit skip, not evidence that PostgreSQL has been verified. Every run uses
synthetic members, new TLS certificates and random temporary database passwords.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
from threading import Barrier
from urllib.parse import urlencode

import pytest

from roxy_os.fitness.repository import (
    FitnessConflict,
    FitnessConsentRequired,
    FitnessStorageUnavailable,
    PostgresFitnessRepository,
)


CONSENT = {"purpose": "fitness_preferences", "text_version": "fitness-preferences-v1", "granted": True}
PROFILE = {"timezone": "America/New_York", "age_band": "30_44", "primary_goal": "fitness_habit"}
ROOT = Path(__file__).resolve().parents[1]


def _postgres_binaries():
    configured = os.environ.get("ROXY_FITNESS_TEST_PG_BIN")
    paths = [Path(configured)] if configured else []
    executable = shutil.which("pg_ctl")
    if executable:
        paths.append(Path(executable).parent)
    for path in paths:
        if all((path / name).is_file() for name in ("initdb", "pg_ctl", "postgres")):
            return path.resolve()
    pytest.skip("Real PostgreSQL unavailable: install initdb/pg_ctl and set ROXY_FITNESS_TEST_PG_BIN")


def _certificates(directory):
    pytest.importorskip("cryptography", reason="Real PostgreSQL TLS tests need cryptography")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Roxy synthetic CA " + secrets.token_hex(4))])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=2))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = (x509.CertificateBuilder()
              .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
              .issuer_name(ca_name).public_key(server_key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
              .not_valid_after(now + timedelta(days=2))
              .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
              .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
              .sign(ca_key, hashes.SHA256()))
    (directory / "root.crt").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory / "server.crt").write_bytes(server.public_bytes(serialization.Encoding.PEM))
    key_path = directory / "server.key"
    key_path.write_bytes(server_key.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)


class LocalPostgres:
    def __init__(self, directory, binaries, driver):
        self.directory, self.binaries, self.driver = directory, binaries, driver
        self.data = directory / "data"
        self.passwords = {role: secrets.token_urlsafe(24) for role in ("fitness_owner", "fitness_runtime")}
        # Pass an isolated subprocess environment; PostgreSQL connection defaults
        # and service files from other products cannot select a different server.
        self.process_env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]

    def command(self, binary, *arguments):
        result = subprocess.run([str(self.binaries / binary), *map(str, arguments)],
                                env=self.process_env, capture_output=True, text=True, timeout=45)
        if result.returncode:
            # This cluster contains synthetic data only; never include credentials.
            raise RuntimeError(f"Isolated PostgreSQL {binary} failed: {result.stdout}\n{result.stderr}")
        return result.stdout

    def initialize(self):
        self.command("initdb", "-D", self.data, "-U", "fitness_bootstrap", "--auth-local=trust",
                     "--auth-host=scram-sha-256", "--encoding=UTF8", "--no-locale")
        _certificates(self.directory)
        (self.data / "postgresql.conf").write_text(
            "listen_addresses = '127.0.0.1'\n"
            f"port = {self.port}\n"
            f"unix_socket_directories = '{self.directory.as_posix()}'\n"
            "ssl = on\nssl_min_protocol_version = 'TLSv1.2'\n"
            f"ssl_cert_file = '{self.directory.as_posix()}/server.crt'\n"
            f"ssl_key_file = '{self.directory.as_posix()}/server.key'\n"
            "password_encryption = 'scram-sha-256'\n"
            "max_connections = 20\nshared_buffers = '16MB'\n"
        )
        (self.data / "pg_hba.conf").write_text(
            "local all fitness_bootstrap trust\n"
            "hostnossl all all 127.0.0.1/32 reject\n"
            "hostssl all all 127.0.0.1/32 scram-sha-256\n"
        )
        self.start()
        sql = self.driver.sql
        with self.admin() as conn:
            for role, password in self.passwords.items():
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                                     "NOINHERIT NOBYPASSRLS PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)))
            conn.execute("CREATE DATABASE fitness_test OWNER fitness_owner")
            conn.execute("REVOKE ALL ON DATABASE fitness_test FROM PUBLIC")
            conn.execute("GRANT CONNECT ON DATABASE fitness_test TO fitness_runtime")
        with self.connect("fitness_owner", autocommit=True) as conn:
            conn.execute((ROOT / "migrations/fitness/001_foundation.sql").read_text())
            conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            conn.execute("GRANT USAGE ON SCHEMA roxy_home_fitness TO fitness_runtime")
            conn.execute("GRANT SELECT ON roxy_home_fitness.schema_version TO fitness_runtime")
            conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON roxy_home_fitness.member_state, "
                         "roxy_home_fitness.idempotency TO fitness_runtime")

    def admin(self):
        return self.driver.connect(host=str(self.directory), port=self.port, user="fitness_bootstrap",
                                   dbname="postgres", sslmode="disable", autocommit=True, connect_timeout=5)

    def dsn(self, role="fitness_runtime", **overrides):
        parameters = {"hostaddr": "127.0.0.1", "sslmode": "verify-full",
                      "sslrootcert": str(self.directory / "root.crt"), "connect_timeout": "5",
                      "sslcert": str(self.directory / "absent-client.crt"),
                      "sslkey": str(self.directory / "absent-client.key"),
                      "sslcrl": str(self.directory / "absent-client.crl"), "gssencmode": "disable"}
        parameters.update(overrides)
        host = parameters.pop("host", "localhost")
        return f"postgresql://{role}:{self.passwords[role]}@{host}:{self.port}/fitness_test?{urlencode(parameters)}"

    def connect(self, role="fitness_runtime", **kwargs):
        return self.driver.connect(self.dsn(role), **kwargs)

    def repository(self, **overrides):
        return PostgresFitnessRepository(self.dsn(**overrides))

    def start(self):
        self.command("pg_ctl", "-D", self.data, "-l", self.directory / "postgres.log", "-w", "start")

    def stop(self):
        if (self.data / "postmaster.pid").exists():
            self.command("pg_ctl", "-D", self.data, "-m", "fast", "-w", "stop")

    @contextmanager
    def member(self, member_id, role="fitness_runtime"):
        with self.connect(role) as conn:
            conn.execute("SELECT set_config('roxy_home.member_id', %s, TRUE)", (member_id,))
            yield conn


@pytest.fixture(scope="module")
def postgres():
    binaries = _postgres_binaries()
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("Run isolated initdb as an unprivileged OS user, not root")
    driver = pytest.importorskip("psycopg", reason="Real PostgreSQL tests need psycopg[binary]")
    # A short socket path works on macOS; no existing data directory is accepted.
    with tempfile.TemporaryDirectory(prefix="roxy-fitness-pg-", dir="/tmp") as temporary:
        cluster = LocalPostgres(Path(temporary), binaries, driver)
        try:
            cluster.initialize()
            yield cluster
        finally:
            cluster.stop()


@pytest.fixture
def members(request):
    prefix = re.sub(r"[^A-Za-z0-9_.:@-]", "-", request.node.name)[:120]
    return f"{prefix}-a", f"{prefix}-b"


def _save(repository, member, profile=None):
    repository.set_consent(member, CONSENT, expected_version=0, idempotency_key="consent-0001")
    return repository.save_profile(member, profile or PROFILE, expected_version=1, idempotency_key="profile-0001")


def test_real_tls_validates_certificate_chain_and_hostname(postgres, members):
    with postgres.connect() as conn:
        ssl, version = conn.execute("SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()").fetchone()
        assert ssl is True and version in {"TLSv1.2", "TLSv1.3"}
        assert conn.pgconn.ssl_in_use and conn.info.get_parameters()["sslmode"] == "verify-full"
    assert postgres.repository().snapshot(members[0])["version"] == 0
    bad_hostname = postgres.dsn(host="wrong-host.invalid")
    with pytest.raises(postgres.driver.OperationalError, match="does not match host name"):
        postgres.driver.connect(bad_hostname)
    with pytest.raises(FitnessStorageUnavailable):
        postgres.repository(host="wrong-host.invalid", sslmode="disable").snapshot(members[0])
    unrelated = postgres.directory / "unrelated"
    unrelated.mkdir()
    _certificates(unrelated)
    with pytest.raises(postgres.driver.OperationalError, match="certificate verify failed"):
        postgres.driver.connect(postgres.dsn(sslrootcert=str(unrelated / "root.crt")))
    with pytest.raises(FitnessStorageUnavailable):
        postgres.repository(sslrootcert=str(unrelated / "root.crt")).snapshot(members[0])
    with pytest.raises(postgres.driver.OperationalError, match="no encryption"):
        postgres.driver.connect(postgres.dsn(sslmode="disable"))


def test_runtime_is_nonowner_without_bypass_ddl_or_owner_membership(postgres):
    with postgres.connect(autocommit=True) as conn:
        assert conn.execute("SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles "
                            "WHERE rolname = current_user").fetchone() == (False, False, False, False)
        rows = conn.execute("SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                            "pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE n.nspname = 'roxy_home_fitness' AND c.relname IN ('member_state', 'idempotency')").fetchall()
        assert len(rows) == 2
        assert all(row[1:] == (True, True, "fitness_owner") for row in rows)
        for statement in ("SET ROLE fitness_owner", "ALTER TABLE roxy_home_fitness.member_state DISABLE ROW LEVEL SECURITY",
                          "CREATE TABLE roxy_home_fitness.not_allowed (id int)",
                          "TRUNCATE roxy_home_fitness.member_state CASCADE",
                          "UPDATE roxy_home_fitness.schema_version SET version = 1"):
            with pytest.raises(postgres.driver.errors.InsufficientPrivilege):
                conn.execute(statement)
    with pytest.raises(FitnessStorageUnavailable):
        PostgresFitnessRepository(postgres.dsn("fitness_owner")).snapshot("synthetic-owner")


@pytest.mark.parametrize("table", ["member_state", "idempotency"])
def test_actual_rls_hides_other_member_and_rejects_cross_member_writes(postgres, members, table):
    repository = postgres.repository()
    for member in members:
        _save(repository, member)
    sql = postgres.driver.sql
    relation = sql.Identifier("roxy_home_fitness", table)
    with postgres.connect() as conn:
        assert conn.execute(sql.SQL("SELECT member_id FROM {}").format(relation)).fetchall() == []
    for role in ("fitness_runtime", "fitness_owner"):
        with postgres.member(members[0], role) as conn:
            assert conn.execute(sql.SQL("SELECT member_id FROM {}").format(relation)).fetchall() == [(members[0],)]
            assert conn.execute(sql.SQL("SELECT member_id FROM {} WHERE member_id = %s").format(relation), (members[1],)).fetchall() == []
            assert conn.execute(sql.SQL("UPDATE {} SET member_id = member_id WHERE member_id = %s").format(relation), (members[1],)).rowcount == 0
            assert conn.execute(sql.SQL("DELETE FROM {} WHERE member_id = %s").format(relation), (members[1],)).rowcount == 0
    with postgres.member(members[0]) as conn:
        with pytest.raises(postgres.driver.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute(sql.SQL("UPDATE {} SET member_id = %s WHERE member_id = %s").format(relation),
                             ("synthetic-unrelated-member", members[0]))
        with pytest.raises(postgres.driver.errors.InsufficientPrivilege):
            with conn.transaction():
                if table == "member_state":
                    conn.execute("INSERT INTO roxy_home_fitness.member_state (member_id) VALUES (%s)", ("synthetic-unrelated-member",))
                else:
                    conn.execute("INSERT INTO roxy_home_fitness.idempotency VALUES (%s, 'cross-member-key', %s, 1)",
                                 (members[1], "a" * 64))
    assert repository.snapshot(members[1])["version"] == 2


def test_consent_profile_export_idempotency_and_stale_version_with_real_commits(postgres, members):
    repository = postgres.repository()
    member, other = members
    assert repository.snapshot(member)["version"] == 0
    with pytest.raises(FitnessConsentRequired):
        repository.save_profile(member, PROFILE, expected_version=0, idempotency_key="no-consent-0001")
    with postgres.member(member) as conn:
        assert conn.execute("SELECT count(*) FROM roxy_home_fitness.member_state").fetchone()[0] == 0
    saved = _save(repository, member)
    retry = repository.save_profile(member, PROFILE, expected_version=1, idempotency_key="profile-0001")
    assert retry == {**saved, "idempotent_replay": True}
    with pytest.raises(FitnessConflict):
        repository.save_profile(member, {**PROFILE, "timezone": "UTC"}, expected_version=1, idempotency_key="profile-0001")
    with pytest.raises(FitnessConflict):
        repository.save_profile(member, PROFILE, expected_version=1, idempotency_key="profile-stale")
    assert repository.snapshot(other)["profile"] is None
    exported = postgres.repository().export_data(member)
    assert exported["data"] == saved and exported["scope"] == "authenticated_member_only"
    assert exported["contains_clinical_records"] is False


def test_revoke_and_delete_remove_payload_retain_version_and_preserve_other_member(postgres, members):
    repository = postgres.repository()
    for member in members:
        _save(repository, member)
    member, other = members
    before_other = repository.snapshot(other)
    revoked = repository.set_consent(member, {**CONSENT, "granted": False}, expected_version=2, idempotency_key="revoke-0001")
    assert revoked["version"] == 3 and revoked["profile"] is None and revoked["consent"]["granted"] is False
    with pytest.raises(FitnessConsentRequired):
        repository.save_profile(member, PROFILE, expected_version=3, idempotency_key="revoked-profile")
    with pytest.raises(FitnessConflict):
        repository.save_profile(member, PROFILE, expected_version=1, idempotency_key="profile-0001")
    deleted = repository.delete_data(member, expected_version=3, idempotency_key="delete-00001")
    assert deleted["version"] == 4 and deleted["profile"] is deleted["consent"] is None
    assert repository.delete_data(member, expected_version=3, idempotency_key="delete-00001")["idempotent_replay"] is True
    with pytest.raises(FitnessConflict):
        repository.set_consent(member, CONSENT, expected_version=0, idempotency_key="resurrect-0001")
    with postgres.member(member) as conn:
        assert conn.execute("SELECT version, profile, consent FROM roxy_home_fitness.member_state").fetchall() == [(4, None, None)]
        retained = conn.execute("SELECT request_key, request_hash, response_version FROM roxy_home_fitness.idempotency").fetchall()
        assert len(retained) == 1 and retained[0][0] == "delete-00001" and len(retained[0][1]) == 64 and retained[0][2] == 4
    assert repository.snapshot(other) == before_other


def test_real_advisory_lock_serializes_concurrent_first_insert_and_profile_update(postgres, members):
    repository = postgres.repository()
    barrier = Barrier(2)

    def first_write(index):
        barrier.wait(timeout=5)
        try:
            return repository.set_consent(members[0], CONSENT, expected_version=0, idempotency_key=f"first-write-{index}")["version"]
        except FitnessConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert set(pool.map(first_write, (1, 2))) == {1, "conflict"}

    def profile_write(index):
        barrier.wait(timeout=5)
        try:
            return repository.save_profile(members[0], PROFILE, expected_version=1, idempotency_key=f"profile-race-{index}")["version"]
        except FitnessConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert set(pool.map(profile_write, (1, 2))) == {2, "conflict"}
    assert repository.snapshot(members[0])["version"] == 2


def test_member_context_is_transaction_local_and_rollback_does_not_leak_it(postgres, members):
    for member in members:
        _save(postgres.repository(), member)
    with postgres.connect(autocommit=True) as conn:
        for member in members:
            with conn.transaction():
                conn.execute("SELECT set_config('roxy_home.member_id', %s, TRUE)", (member,))
                assert conn.execute("SELECT member_id FROM roxy_home_fitness.member_state").fetchall() == [(member,)]
            assert conn.execute("SELECT member_id FROM roxy_home_fitness.member_state").fetchall() == []
        with pytest.raises(RuntimeError):
            with conn.transaction():
                conn.execute("SELECT set_config('roxy_home.member_id', %s, TRUE)", (members[0],))
                raise RuntimeError("synthetic rollback")
        assert conn.execute("SELECT member_id FROM roxy_home_fitness.member_state").fetchall() == []


@pytest.mark.parametrize("setting", ["DISABLE ROW LEVEL SECURITY", "NO FORCE ROW LEVEL SECURITY"])
def test_real_schema_regression_is_rejected_before_member_read(postgres, members, setting):
    # Only the ephemeral owner role can regress this temporary test schema.
    with postgres.connect("fitness_owner", autocommit=True) as conn:
        conn.execute(f"ALTER TABLE roxy_home_fitness.member_state {setting}")
        try:
            with pytest.raises(FitnessStorageUnavailable):
                postgres.repository().snapshot(members[0])
        finally:
            conn.execute("ALTER TABLE roxy_home_fitness.member_state ENABLE ROW LEVEL SECURITY")
            conn.execute("ALTER TABLE roxy_home_fitness.member_state FORCE ROW LEVEL SECURITY")


def test_data_and_delete_tombstone_survive_actual_server_restart(postgres, members):
    repository = postgres.repository()
    for member in members:
        _save(repository, member)
    expected_profile = repository.snapshot(members[1])
    expected_deleted = repository.delete_data(members[0], expected_version=2, idempotency_key="delete-restart")
    postgres.stop()
    postgres.start()
    fresh_process_repository = postgres.repository()
    assert fresh_process_repository.snapshot(members[0]) == expected_deleted
    assert fresh_process_repository.snapshot(members[1]) == expected_profile
    with pytest.raises(FitnessConflict):
        fresh_process_repository.set_consent(members[0], CONSENT, expected_version=0, idempotency_key="stale-restart")
