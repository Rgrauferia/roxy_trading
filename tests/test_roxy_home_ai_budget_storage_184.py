"""Home-only usage accounting: synthetic state, no provider or live credentials."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import errno
import json
from pathlib import Path
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

import roxy_os.home_ai as module
import roxy_os.home_private_storage as private
import roxy_os.home_plants as plants
from roxy_os.home_ai import (
    HomeAIBudgetExceeded, HomeAIBudgetLedger, HomeAIBudgetStorageError,
    HomeAIConfig, HomeAIConfigurationError, RoxyHomeAI,
)


def ledger(tmp_path: Path, **limits) -> HomeAIBudgetLedger:
    return HomeAIBudgetLedger(tmp_path / "home-budget.json", request_limit=limits.get("requests", 100), output_token_limit=limits.get("tokens", 1000))


def payload(**changes):
    return {"date": date.today().isoformat(), "requests": 3, "output_tokens": 25, **changes}


def reserve_when_available(store):
    for _ in range(1000):
        try:
            return store.reserve_request()
        except HomeAIBudgetStorageError as exc:
            if exc.code != "pending_usage":
                raise
            time.sleep(.001)
    raise AssertionError("Synthetic reservation did not settle")


@pytest.mark.parametrize("raw", [
    b"", b"{", b"null", b"[]", b"true", b"42", b"\xff", b"{}",
    json.dumps(payload(date="2026-02-31")).encode(),
    json.dumps(payload(date="20260910")).encode(),
    json.dumps(payload(date=None)).encode(),
    json.dumps(payload(requests=-1)).encode(),
    json.dumps(payload(requests=True)).encode(),
    json.dumps(payload(requests="3")).encode(),
    json.dumps(payload(requests=3.1)).encode(),
    json.dumps(payload(output_tokens=None)).encode(),
    json.dumps(payload(output_tokens=-3)).encode(),
    json.dumps(payload(output_tokens=False)).encode(),
    json.dumps(payload(output_tokens=float("nan"))).encode(),
    json.dumps(payload(metadata={"cost": float("inf")})).encode(),
    ('{"date":"%s","requests":9,"requests":0,"output_tokens":0}' % date.today().isoformat()).encode(),
    json.dumps({"date": date.today().isoformat(), "requests": 5}).encode(),
])
@pytest.mark.parametrize("operation", ["reserve", "record", "snapshot"])
def test_corruption_blocks_without_changing_original_bytes_or_allowance(tmp_path, raw, operation):
    store = ledger(tmp_path); store.path.write_bytes(raw)
    action = {"reserve": store.reserve_request, "record": lambda: store.record_output_tokens(17), "snapshot": store.snapshot}[operation]
    with pytest.raises(HomeAIBudgetStorageError) as error:
        action()
    assert store.path.read_bytes() == raw
    assert str(tmp_path) not in str(error.value)
    assert "contador" in str(error.value)
    assert not private.initialized_marker(store.path).exists()


def test_valid_legacy_adoption_preserves_requests_tokens_and_extra_accounting(tmp_path):
    store = ledger(tmp_path)
    original = payload(costs={"spent_usd": 1.375, "currency": "USD"}, reservations=[{"id": "synthetic", "state": "reserved"}], output_token_details={"cached": 9})
    store.path.write_text(json.dumps(original))
    result = store.snapshot()
    assert {key: result[key] for key in original} == original
    assert json.loads(store.path.read_text()) == original
    assert private.initialized_marker(store.path).exists()
    assert store.reserve_request()["requests"] == 4
    assert store.record_output_tokens(8)["output_tokens"] == 33
    assert json.loads(store.path.read_text())["costs"] == original["costs"]


def test_new_ledger_initializes_zero_under_lock_and_protects_later_disappearance(tmp_path):
    store = ledger(tmp_path); assert not store.path.exists()
    initial = store.snapshot()
    assert initial["requests"] == initial["output_tokens"] == 0
    assert private.initialized_marker(store.path).exists()
    store.path.unlink()
    restarted = ledger(tmp_path)
    for operation in [restarted.snapshot, restarted.reserve_request, lambda: restarted.record_output_tokens(1)]:
        with pytest.raises(HomeAIBudgetStorageError, match="contador"):
            operation()
    assert not store.path.exists()


def test_read_legacy_before_file_disappears_does_not_allow_a_restart_reset(tmp_path):
    store = ledger(tmp_path); store.path.write_text(json.dumps(payload(requests=100)))
    store.snapshot(); store.path.unlink()
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        ledger(tmp_path).reserve_request()
    assert exc.value.code == "missing_initialized"


def test_exhausted_legacy_reservation_also_marks_prior_state_before_rejection(tmp_path):
    store = ledger(tmp_path); store.path.write_text(json.dumps(payload(requests=100)))
    with pytest.raises(HomeAIBudgetExceeded):
        store.reserve_request()
    assert private.initialized_marker(store.path).exists()
    store.path.unlink()
    with pytest.raises(HomeAIBudgetStorageError):
        ledger(tmp_path).reserve_request()


def test_valid_past_day_rolls_once_and_preserves_unrelated_cost_reservations(tmp_path):
    store = ledger(tmp_path)
    original = payload(date=(date.today() - timedelta(days=1)).isoformat(), requests=97, output_tokens=1700, cost_history={"prior_usd": 2.0}, reservations=[{"external_id": "keep"}])
    store.path.write_text(json.dumps(original))
    today = store.reserve_request()
    assert today["date"] == date.today().isoformat()
    assert today["requests"] == 1 and today["output_tokens"] == 0
    assert today["cost_history"] == original["cost_history"] and today["reservations"] == original["reservations"]
    store.record_output_tokens(0, reservation_id=today["reservation_id"])
    assert ledger(tmp_path).reserve_request()["requests"] == 2


def test_old_date_with_invalid_counters_is_not_a_legitimate_rollover(tmp_path):
    store = ledger(tmp_path)
    raw = json.dumps(payload(date=(date.today() - timedelta(days=1)).isoformat(), output_tokens="corrupt"))
    store.path.write_text(raw)
    with pytest.raises(HomeAIBudgetStorageError):
        store.reserve_request()
    assert store.path.read_text() == raw


def test_future_day_or_clock_rollback_cannot_grant_fresh_allowance(tmp_path):
    store = ledger(tmp_path)
    raw = json.dumps(payload(date=(date.today() + timedelta(days=1)).isoformat(), requests=100))
    store.path.write_text(raw)
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        store.snapshot()
    assert exc.value.code == "future_budget_date"
    assert store.path.read_text() == raw


def test_actual_day_transition_rolls_budget_without_changing_limits(tmp_path, monkeypatch):
    class ClockDate(date):
        current = date(2026, 9, 10)
        @classmethod
        def today(cls):
            return cls.current
    monkeypatch.setattr(module, "date", ClockDate)
    store = ledger(tmp_path, requests=2, tokens=30)
    store.reserve_request(); store.record_output_tokens(21); store.reserve_request(); store.record_output_tokens(0)
    with pytest.raises(HomeAIBudgetExceeded):
        store.reserve_request()
    ClockDate.current = date(2026, 9, 11)
    after = store.reserve_request()
    assert {key: after[key] for key in ["date", "requests", "output_tokens"]} == {"date": "2026-09-11", "requests": 1, "output_tokens": 0}
    assert store.snapshot()["request_limit"] == 2 and store.snapshot()["output_token_limit"] == 30
    ClockDate.current = date(2026, 9, 10)
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        store.reserve_request()
    assert exc.value.code == "future_budget_date"


def test_zero_and_usage_over_limit_are_preserved_not_truncated(tmp_path):
    store = ledger(tmp_path, tokens=10); store.reserve_request()
    assert store.record_output_tokens(0)["output_tokens"] == 0
    assert store.record_output_tokens(13)["output_tokens"] == 13
    with pytest.raises(HomeAIBudgetExceeded):
        store.reserve_request()
    assert store.snapshot()["output_tokens"] == 13
    no_requests = HomeAIBudgetLedger(tmp_path / "zero.json", request_limit=0, output_token_limit=20)
    with pytest.raises(HomeAIBudgetExceeded):
        no_requests.reserve_request()


@pytest.mark.parametrize("count", [True, False, -1, 1.1, "5", None, float("nan"), float("inf")])
def test_invalid_usage_never_refunds_truncates_or_changes_file(tmp_path, count):
    store = ledger(tmp_path); store.reserve_request(); before = store.path.read_bytes()
    with pytest.raises(ValueError):
        store.record_output_tokens(count)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("limit", [-1, True, 1.5, "5", None])
def test_invalid_limits_never_create_budget_files(tmp_path, limit):
    with pytest.raises(HomeAIConfigurationError):
        ledger(tmp_path, requests=limit)
    with pytest.raises(HomeAIConfigurationError):
        ledger(tmp_path, tokens=limit)
    assert not list(tmp_path.iterdir())


def test_threaded_instances_reserve_and_record_without_losing_updates(tmp_path):
    def work(_index):
        store = ledger(tmp_path, requests=50, tokens=10000)
        reserve_when_available(store); store.record_output_tokens(7)
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(work, range(40)))
    final = ledger(tmp_path).snapshot()
    assert final["requests"] == 40 and final["output_tokens"] == 280


def test_threaded_reservations_never_exceed_request_limit_at_rollover(tmp_path):
    store = ledger(tmp_path, requests=7)
    store.path.write_text(json.dumps(payload(date=(date.today() - timedelta(days=1)).isoformat(), requests=99)))
    def reserve(_index):
        try:
            local = ledger(tmp_path, requests=7)
            reserve_when_available(local); local.record_output_tokens(0); return True
        except HomeAIBudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=16) as pool:
        admitted = list(pool.map(reserve, range(32)))
    assert sum(admitted) == 7
    assert store.snapshot()["requests"] == 7


def test_processes_share_the_same_request_limit_and_token_totals(tmp_path):
    code = """
import sys,time
from roxy_os.home_ai import HomeAIBudgetLedger, HomeAIBudgetExceeded, HomeAIBudgetStorageError
store=HomeAIBudgetLedger(sys.argv[1], request_limit=23, output_token_limit=10000)
accepted=0
for _ in range(15):
    try:
        for attempt in range(1000):
            try:
                store.reserve_request()
                break
            except HomeAIBudgetStorageError as exc:
                if exc.code!='pending_usage': raise
                time.sleep(.001)
        else: raise AssertionError('pending synthetic work')
    except HomeAIBudgetExceeded:
        continue
    accepted+=1
    store.record_output_tokens(11)
print(accepted)
"""
    def process(_index):
        return subprocess.run([sys.executable, "-c", code, str(tmp_path / "home-budget.json")], cwd=Path(__file__).resolve().parents[1], check=True, capture_output=True, text=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(process, range(4)))
    assert sum(int(result.stdout.strip()) for result in results) == 23
    final = ledger(tmp_path).snapshot()
    assert final["requests"] == 23 and final["output_tokens"] == 253


def test_no_fcntl_fails_closed_instead_of_running_unlocked(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "fcntl", None)
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        ledger(tmp_path).reserve_request()
    assert exc.value.code == "locking_unavailable"
    assert not list(tmp_path.iterdir())


def test_atomic_replace_failure_preserves_previous_usage_and_removes_temp(tmp_path, monkeypatch):
    store = ledger(tmp_path); store.reserve_request(); store.record_output_tokens(14)
    before = store.path.read_bytes()
    def fail_replace(_source, _target):
        raise OSError(errno.ENOSPC, "fixture disk full")
    monkeypatch.setattr(private.os, "replace", fail_replace)
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        store.record_output_tokens(10)
    assert not exc.value.committed
    assert store.path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_first_commit_leaves_marker_and_cannot_retry_as_empty(tmp_path, monkeypatch):
    store = ledger(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(private.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError(errno.ENOSPC, "fixture")))
        with pytest.raises(HomeAIBudgetStorageError):
            store.reserve_request()
    assert not store.path.exists() and private.initialized_marker(store.path).exists()
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        ledger(tmp_path).reserve_request()
    assert exc.value.code == "missing_initialized"


def test_post_replace_confirmation_error_keeps_committed_accounting(tmp_path, monkeypatch):
    store = ledger(tmp_path); store.reserve_request(); original = private._sync_directory; calls = 0
    def sync(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(errno.EIO, "fixture fsync")
        original(path)
    with monkeypatch.context() as patch:
        patch.setattr(private, "_sync_directory", sync)
        with pytest.raises(HomeAIBudgetStorageError) as exc:
            store.record_output_tokens(55)
    assert exc.value.committed is True
    assert ledger(tmp_path).snapshot()["output_tokens"] == 55


def test_private_permissions_are_enforced_for_budget_marker_and_lock(tmp_path):
    store = ledger(tmp_path); store.reserve_request()
    for path in [store.path, store.lock_path, private.initialized_marker(store.path)]:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    store.path.chmod(0o644); store.lock_path.chmod(0o644); store.snapshot()
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.lock_path.stat().st_mode) == 0o600


def test_read_permission_error_preserves_file_and_sanitizes_error(tmp_path, monkeypatch):
    store = ledger(tmp_path); store.reserve_request(); before = store.path.read_bytes(); original = Path.read_text
    def fail(path, *args, **kwargs):
        if path == store.path:
            raise PermissionError(f"fixture private path {store.path}")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", fail)
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        store.snapshot()
    assert str(store.path) not in str(exc.value)
    assert store.path.read_bytes() == before


def test_corrupt_budget_prevents_any_provider_call_and_failed_provider_keeps_reservation(tmp_path):
    calls = []
    def unavailable(**kwargs):
        calls.append(kwargs); raise RuntimeError("fixture provider failure")
    cfg = HomeAIConfig(api_key="synthetic-never-sent", budget_path=str(tmp_path / "ai.json"), daily_request_limit=1)
    ai = RoxyHomeAI(cfg, client=SimpleNamespace(responses=SimpleNamespace(create=unavailable)))
    ai.budget.path.write_bytes(b"{broken")
    with pytest.raises(HomeAIBudgetStorageError):
        ai.converse("synthetic", {})
    assert calls == []
    # Separate brand-new fixture, not automatic recovery of the corrupt ledger.
    cfg = HomeAIConfig(api_key="synthetic-never-sent", budget_path=str(tmp_path / "fresh.json"), daily_request_limit=1)
    ai = RoxyHomeAI(cfg, client=SimpleNamespace(responses=SimpleNamespace(create=unavailable)))
    with pytest.raises(RuntimeError, match="fixture provider"):
        ai.converse("synthetic", {})
    assert ai.budget.snapshot()["requests"] == 1
    with pytest.raises(HomeAIBudgetStorageError) as exc:
        ai.converse("synthetic retry", {})
    assert exc.value.code == "pending_usage"
    assert len(calls) == 1


def test_reservation_persistence_failure_stops_before_provider(tmp_path, monkeypatch):
    calls = []
    cfg = HomeAIConfig(api_key="synthetic-never-sent", budget_path=str(tmp_path / "ai.json"))
    ai = RoxyHomeAI(cfg, client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs))))
    monkeypatch.setattr(private.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError(errno.ENOSPC, "fixture")))
    with pytest.raises(HomeAIBudgetStorageError):
        ai.converse("synthetic", {})
    assert calls == []


def fake_ai(tmp_path, create):
    config = HomeAIConfig(api_key="synthetic-never-sent", budget_path=str(tmp_path / "home-budget.json"))
    return RoxyHomeAI(config, client=SimpleNamespace(responses=SimpleNamespace(create=create)))


def fake_response(count=25):
    return SimpleNamespace(output_text='{"answer":"synthetic"}', usage=SimpleNamespace(output_tokens=count))


def test_successful_provider_then_failed_settlement_blocks_spend_after_restart(tmp_path, monkeypatch):
    calls = []
    def create(**_request):
        calls.append(True)
        persisted = json.loads((tmp_path / "home-budget.json").read_text())
        assert persisted["requests"] == 1
        assert len(persisted["pending_request"]["id"]) == 32
        return fake_response(25)
    ai = fake_ai(tmp_path, create)
    original = private.os.replace; replacements = 0
    def replace(source, target):
        nonlocal replacements
        replacements += 1
        if replacements == 2:  # Reservation succeeded; settlement disk is full.
            raise OSError(errno.ENOSPC, "fixture settlement full")
        original(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(private.os, "replace", replace)
        with pytest.raises(HomeAIBudgetStorageError) as error:
            ai.converse("synthetic", {})
    assert not error.value.committed and calls == [True]
    old = json.loads(ai.budget.path.read_text())
    assert old["output_tokens"] == 0 and old["requests"] == 1
    reservation_id = old["pending_request"]["id"]
    restarted = fake_ai(tmp_path, create)
    with pytest.raises(HomeAIBudgetStorageError) as blocked:
        restarted.converse("not sent", {})
    assert blocked.value.code == "pending_usage" and len(calls) == 1
    # Only an authoritative known usage value settles the exact reservation.
    repaired = restarted.budget.record_output_tokens(25, reservation_id=reservation_id)
    assert repaired["output_tokens"] == 25 and repaired["requests"] == 1
    assert repaired["pending_request"] is None
    assert restarted.budget.reserve_request()["requests"] == 2


def test_uncertain_settlement_confirmation_is_idempotent_after_restart(tmp_path, monkeypatch):
    store = ledger(tmp_path); reserved = store.reserve_request(); original = private._sync_directory
    calls = 0
    def sync(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(errno.EIO, "fixture post-replace fsync")
        original(path)
    with monkeypatch.context() as patch:
        patch.setattr(private, "_sync_directory", sync)
        with pytest.raises(HomeAIBudgetStorageError) as error:
            store.record_output_tokens(55, reservation_id=reserved["reservation_id"])
    assert error.value.committed
    restarted = ledger(tmp_path)
    result = restarted.record_output_tokens(55, reservation_id=reserved["reservation_id"])
    assert result["output_tokens"] == 55 and result["pending_request"] is None
    assert result["requests"] == 1 and len(result["settled_requests"]) == 1
    before = restarted.path.read_bytes()
    with pytest.raises(HomeAIBudgetStorageError) as conflicting:
        restarted.record_output_tokens(1, reservation_id=reserved["reservation_id"])
    assert conflicting.value.code == "conflicting_settlement"
    assert restarted.path.read_bytes() == before


def test_duplicate_old_settlement_cannot_clear_another_pending_request(tmp_path):
    store = ledger(tmp_path)
    first = store.reserve_request()["reservation_id"]
    store.record_output_tokens(12, reservation_id=first)
    second = store.reserve_request()["reservation_id"]
    result = ledger(tmp_path).record_output_tokens(12, reservation_id=first)
    assert result["pending_request"]["id"] == second and result["output_tokens"] == 12
    assert result["requests"] == 2
    with pytest.raises(HomeAIBudgetStorageError) as error:
        ledger(tmp_path).record_output_tokens(0)
    assert error.value.code == "reservation_required"
    assert ledger(tmp_path).record_output_tokens(9, reservation_id=second)["output_tokens"] == 21


@pytest.mark.parametrize("reservation_id", ["", "a" * 32, 1, True, "A" * 32])
def test_unknown_reservation_cannot_refund_or_clear_pending(tmp_path, reservation_id):
    store = ledger(tmp_path); store.reserve_request(); before = store.path.read_bytes()
    with pytest.raises(HomeAIBudgetStorageError) as error:
        ledger(tmp_path).record_output_tokens(0, reservation_id=reservation_id)
    assert error.value.code == "unknown_reservation"
    assert store.path.read_bytes() == before


def test_pending_does_not_expire_at_midnight_and_settlement_keeps_original_day(tmp_path, monkeypatch):
    class ClockDate(date):
        current = date(2026, 9, 10)
        @classmethod
        def today(cls):
            return cls.current
    monkeypatch.setattr(module, "date", ClockDate)
    store = ledger(tmp_path)
    first = store.reserve_request()["reservation_id"]
    store.record_output_tokens(10, reservation_id=first)
    pending_id = store.reserve_request()["reservation_id"]
    ClockDate.current = date(2026, 9, 12)
    restarted = ledger(tmp_path)
    with pytest.raises(HomeAIBudgetStorageError) as blocked:
        restarted.reserve_request()
    assert blocked.value.code == "pending_usage"
    held = restarted.snapshot()
    assert held["date"] == "2026-09-10" and held["requests"] == 2 and held["output_tokens"] == 10
    settled = restarted.record_output_tokens(20, reservation_id=pending_id)
    assert settled["date"] == "2026-09-10" and settled["output_tokens"] == 30
    rolled = restarted.snapshot()
    assert rolled["date"] == "2026-09-12" and rolled["requests"] == rolled["output_tokens"] == 0
    assert rolled["settled_requests"][pending_id] == {"date": "2026-09-10", "output_tokens": 20}
    # A late duplicate acknowledgment must not charge the new day.
    assert restarted.record_output_tokens(20, reservation_id=pending_id)["output_tokens"] == 0
    assert restarted.reserve_request()["requests"] == 1


@pytest.mark.parametrize("usage", [None, {}, SimpleNamespace(), {"output_tokens": None}, {"output_tokens": True}, {"output_tokens": "25"}, {"output_tokens": -1}, {"output_tokens": 1.5}])
@pytest.mark.parametrize("caller", ["conversation", "image_import", "plant"])
def test_missing_or_malformed_usage_is_not_invented_as_zero(tmp_path, monkeypatch, usage, caller):
    calls = []
    def create(**_request):
        calls.append(True)
        return SimpleNamespace(output_text='{"answer":"synthetic"}', usage=usage)
    ai = fake_ai(tmp_path, create)
    monkeypatch.setattr(plants, "_decode_image", lambda _url: None)
    action = {
        "conversation": lambda: ai.converse("synthetic", {}),
        "image_import": lambda: ai.import_recipe("data:image/png;fixture", {}, source_type="image"),
        "plant": lambda: plants.HomePlantIdentifier(ai.config, ai.client).identify("data:image/png;fixture"),
    }[caller]
    with pytest.raises(HomeAIBudgetStorageError) as error:
        action()
    assert error.value.code == "usage_unavailable"
    snapshot = ledger(tmp_path).snapshot()
    assert snapshot["output_tokens"] == 0 and snapshot["requests"] == 1 and snapshot["pending_request"]
    with pytest.raises(HomeAIBudgetStorageError) as blocked:
        fake_ai(tmp_path, create).converse("not sent", {})
    assert blocked.value.code == "pending_usage" and calls == [True]


@pytest.mark.parametrize("caller", ["conversation", "image_import", "plant"])
def test_all_callers_persist_reservation_before_provider_and_settle_explicit_zero(tmp_path, monkeypatch, caller):
    calls = []
    def create(**request):
        persisted = json.loads((tmp_path / "home-budget.json").read_text())
        assert persisted["pending_request"] and persisted["requests"] == 1
        assert request["store"] is False
        assert request["model"] == "gpt-5.6-luna"
        assert request["max_output_tokens"] == (500 if caller == "plant" else 4000)
        calls.append(request)
        return fake_response(0)
    ai = fake_ai(tmp_path, create)
    monkeypatch.setattr(plants, "_decode_image", lambda _url: None)
    if caller == "conversation":
        ai.converse("synthetic", {})
    elif caller == "image_import":
        ai.import_recipe("data:image/png;fixture", {}, source_type="image")
    else:
        plants.HomePlantIdentifier(ai.config, ai.client).identify("data:image/png;fixture")
    assert len(calls) == 1
    snapshot = ledger(tmp_path).snapshot()
    assert snapshot["pending_request"] is None and snapshot["output_tokens"] == 0 and snapshot["requests"] == 1
    assert len(snapshot["settled_requests"]) == 1


@pytest.mark.parametrize("caller", ["conversation", "image_import", "plant"])
def test_provider_timeout_stays_pending_without_automatic_refund(tmp_path, monkeypatch, caller):
    def create(**_request):
        raise TimeoutError("Fixture network timeout may have incurred usage")
    ai = fake_ai(tmp_path, create)
    monkeypatch.setattr(plants, "_decode_image", lambda _url: None)
    with pytest.raises(TimeoutError):
        if caller == "conversation":
            ai.converse("synthetic", {})
        elif caller == "image_import":
            ai.import_recipe("data:image/png;fixture", {}, source_type="image")
        else:
            plants.HomePlantIdentifier(ai.config, ai.client).identify("data:image/png;fixture")
    snapshot = ledger(tmp_path).snapshot()
    assert snapshot["pending_request"] and snapshot["requests"] == 1 and snapshot["output_tokens"] == 0
    with pytest.raises(HomeAIBudgetStorageError) as error:
        ledger(tmp_path).reserve_request()
    assert error.value.code == "pending_usage"


def test_local_serialization_or_client_setup_error_does_not_create_pending(tmp_path):
    ai = fake_ai(tmp_path, lambda **_request: pytest.fail("Provider must not be called"))
    with pytest.raises(TypeError):
        ai.converse("synthetic", {"profile": {"invalid": object()}})
    with pytest.raises(TypeError):
        ai.import_recipe("data:image/png;fixture", {"profile": {"invalid": object()}}, source_type="image")
    ai.client = SimpleNamespace(responses=SimpleNamespace())
    with pytest.raises(AttributeError):
        ai.converse("synthetic", {})
    with pytest.raises(ValueError):
        plants.HomePlantIdentifier(ai.config, ai.client).identify("not a valid image")
    assert not ai.budget.path.exists()


def test_second_provider_is_blocked_while_first_is_in_flight(tmp_path):
    first_calls = []; second_calls = []
    second = fake_ai(tmp_path, lambda **_request: (second_calls.append(True), fake_response(8))[1])
    def create(**_request):
        first_calls.append(True)
        with pytest.raises(HomeAIBudgetStorageError) as error:
            second.converse("not sent concurrently", {})
        assert error.value.code == "pending_usage" and not second_calls
        return fake_response(12)
    first = fake_ai(tmp_path, create)
    first.converse("synthetic first", {})
    second.converse("synthetic after settlement", {})
    assert first_calls == [True] and second_calls == [True]
    assert ledger(tmp_path).snapshot()["output_tokens"] == 20


@pytest.mark.parametrize("changes", [
    {"pending_request": {"id": 11111111111111111111111111111111, "date": date.today().isoformat()}},
    {"requests": 0, "pending_request": {"id": "a" * 32, "date": date.today().isoformat()}},
    {"pending_request": {"id": "a" * 32, "date": "2001-01-01"}},
    {"settled_requests": []},
    {"settled_requests": {"a" * 32: {"date": date.today().isoformat(), "output_tokens": 55}}},
    {"requests": 0, "settled_requests": {"a" * 32: {"date": date.today().isoformat(), "output_tokens": 0}}},
    {"pending_request": {"id": "a" * 32, "date": date.today().isoformat()}, "settled_requests": {"a" * 32: {"date": date.today().isoformat(), "output_tokens": 0}}},
    {"settled_requests": {"a" * 32: {"date": (date.today() + timedelta(days=1)).isoformat(), "output_tokens": 0}}},
    {"settled_requests": {"a" * 32: {"date": date.today().isoformat(), "output_tokens": True}}},
])
def test_contradictory_pending_or_receipts_fail_closed(tmp_path, changes):
    store = ledger(tmp_path)
    raw = json.dumps(payload(**changes)); store.path.write_text(raw)
    with pytest.raises(HomeAIBudgetStorageError) as error:
        store.reserve_request()
    assert error.value.code == "invalid_structure" and store.path.read_text() == raw
