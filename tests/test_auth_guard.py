import stat

from roxy_trader.auth_guard import AuthAttemptGuard


def test_auth_attempt_guard_locks_persistently_and_recovers(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    guard = AuthAttemptGuard(
        db_path,
        max_failures=3,
        window_seconds=60,
        lock_seconds=120,
        clock=lambda: 1_000.0,
    )

    assert guard.record_failure("Alice@example.test", now=1_000).allowed is True
    assert guard.record_failure(" alice@EXAMPLE.test ", now=1_001).allowed is True
    blocked = guard.record_failure("alice@example.test", now=1_002)

    assert blocked.allowed is False
    assert blocked.failures == 3
    assert blocked.retry_after_seconds == 120
    reopened = AuthAttemptGuard(db_path, max_failures=3, window_seconds=60, lock_seconds=120)
    assert reopened.status("ALICE@example.test", now=1_050).allowed is False
    assert reopened.status("alice@example.test", now=1_123).allowed is True
    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600


def test_auth_attempt_guard_clear_and_identifier_privacy(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    guard = AuthAttemptGuard(db_path, max_failures=2)
    guard.record_failure("private@example.test", now=1_000)
    guard.clear("PRIVATE@example.test")

    assert guard.status("private@example.test", now=1_001).failures == 0
    assert "private@example.test" not in db_path.read_bytes().decode("utf-8", errors="ignore")


def test_auth_attempt_guard_resets_expired_failure_window(tmp_path):
    guard = AuthAttemptGuard(
        tmp_path / "auth.sqlite3",
        max_failures=5,
        window_seconds=30,
        lock_seconds=60,
    )
    guard.record_failure("alice", now=100)
    guard.record_failure("alice", now=110)

    assert guard.status("alice", now=131).failures == 0
    assert guard.record_failure("alice", now=132).failures == 1
