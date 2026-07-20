from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Mapping


API_BUDGET_VERSION = "roxy-api-budget/1.0.0"


@dataclass(frozen=True)
class ApiBudgetPolicy:
    provider: str
    requests_per_window: int
    window_seconds: int = 60
    enforcement: str = "protect"
    source: str = "roxy_operational_budget"
    cooldown_seconds: int = 60

    @property
    def env_key(self) -> str:
        slug = "".join(character if character.isalnum() else "_" for character in self.provider.upper())
        return f"ROXY_API_BUDGET_{slug}_PER_MINUTE"


_POLICIES = {
    policy.provider: policy
    for policy in (
        ApiBudgetPolicy("alpaca", 180),
        ApiBudgetPolicy("polygon", 4),
        ApiBudgetPolicy("finnhub", 50),
        ApiBudgetPolicy("finviz", 10),
        ApiBudgetPolicy("yfinance", 30),
        ApiBudgetPolicy("binanceus", 600),
        ApiBudgetPolicy("binance", 600),
        ApiBudgetPolicy("cryptocom", 60),
        ApiBudgetPolicy("coingecko", 20),
        ApiBudgetPolicy("rss_news", 30),
        ApiBudgetPolicy("elevenlabs", 10),
        ApiBudgetPolicy("tradier", 60),
        ApiBudgetPolicy("nasdaq", 20),
        ApiBudgetPolicy("stooq", 30),
    )
}


def _provider(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def api_budget_policy(provider: str, env: Mapping[str, str] | None = None) -> ApiBudgetPolicy:
    key = _provider(provider)
    if key not in _POLICIES:
        raise KeyError(f"Unknown API budget provider: {provider}")
    base = _POLICIES[key]
    values = env if env is not None else os.environ
    raw = str(values.get(base.env_key, "")).strip()
    if not raw:
        return base
    try:
        requested = int(raw)
    except ValueError:
        return base
    return ApiBudgetPolicy(
        provider=base.provider,
        requests_per_window=max(1, min(100_000, requested)),
        window_seconds=base.window_seconds,
        enforcement=base.enforcement,
        source=base.source,
    )


def api_budget_contract(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    values = env if env is not None else os.environ
    policies = [api_budget_policy(provider, values) for provider in sorted(_POLICIES)]
    return {
        "version": API_BUDGET_VERSION,
        "mode": api_budget_mode(values),
        "policy_count": len(policies),
        "policies": [
            asdict(policy)
            | {
                "env_key": policy.env_key,
                "override_state": _api_budget_override_state(_POLICIES[policy.provider], values),
            }
            for policy in policies
        ],
        "disclaimer": "Operational safety budgets; provider plan limits remain authoritative and may differ.",
    }


def _api_budget_override_state(policy: ApiBudgetPolicy, env: Mapping[str, str]) -> str:
    raw = str(env.get(policy.env_key, "")).strip()
    if not raw:
        return "default"
    try:
        requested = int(raw)
    except ValueError:
        return "invalid"
    return "clamped" if requested < 1 or requested > 100_000 else "applied"


def api_budget_issues(env: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    values = env if env is not None else os.environ
    issues: list[dict[str, str]] = []
    for policy in _POLICIES.values():
        state = _api_budget_override_state(policy, values)
        if state in {"invalid", "clamped"}:
            issues.append({"provider": policy.provider, "env_key": policy.env_key, "state": state})
    raw_mode = str(values.get("ROXY_API_BUDGET_MODE", "")).strip().lower()
    if raw_mode and raw_mode not in {"observe", "protect", "enforce"}:
        issues.append({"provider": "all", "env_key": "ROXY_API_BUDGET_MODE", "state": "invalid"})
    return sorted(issues, key=lambda row: row["provider"])


def api_budget_mode(env: Mapping[str, str] | None = None) -> str:
    values = env if env is not None else os.environ
    mode = str(values.get("ROXY_API_BUDGET_MODE", "protect")).strip().lower()
    return mode if mode in {"observe", "protect", "enforce"} else "protect"


class ApiBudgetBlockedError(RuntimeError):
    def __init__(self, provider: str, reason: str, retry_after_seconds: int) -> None:
        self.provider = provider
        self.reason = reason
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        super().__init__(
            f"API budget blocked {provider}: {reason}; retry after {self.retry_after_seconds}s"
        )


class ApiUsageLedger:
    """Cross-process, secret-free API usage telemetry backed by SQLite."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=3)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=3000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS api_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                operation TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                latency_ms REAL,
                status TEXT NOT NULL,
                http_status INTEGER,
                rate_limited INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS api_budget_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                operation TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                retry_after_seconds INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_budget_blocks_provider_time "
            "ON api_budget_blocks(provider, occurred_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_usage_provider_time "
            "ON api_usage_events(provider, occurred_at)"
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return connection

    def record(
        self,
        *,
        provider: str,
        operation: str,
        status: str,
        latency_ms: float | None = None,
        http_status: int | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        provider_key = _provider(provider)
        operation_key = str(operation or "request").strip().lower()[:80] or "request"
        normalized_status = str(status or "UNKNOWN").strip().upper()[:24]
        timestamp = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        rate_limited = int(http_status == 429 or normalized_status == "RATE_LIMITED")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO api_usage_events "
                "(provider, operation, occurred_at, latency_ms, status, http_status, rate_limited) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    provider_key,
                    operation_key,
                    timestamp,
                    round(float(latency_ms), 1) if latency_ms is not None else None,
                    normalized_status,
                    int(http_status) if http_status is not None else None,
                    rate_limited,
                ),
            )
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            connection.execute("DELETE FROM api_usage_events WHERE occurred_at < ?", (cutoff,))
            connection.execute("DELETE FROM api_budget_blocks WHERE occurred_at < ?", (cutoff,))

    def admission(
        self,
        provider: str,
        *,
        now: datetime | None = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        policy = api_budget_policy(provider, env)
        mode = api_budget_mode(env)
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if mode == "observe" or not self.path.exists():
            return {"allowed": True, "mode": mode, "reason": "observe", "retry_after_seconds": 0}
        with self._connect() as connection:
            latest_rate_limit = connection.execute(
                "SELECT MAX(occurred_at) FROM api_usage_events WHERE provider = ? AND rate_limited = 1",
                (policy.provider,),
            ).fetchone()[0]
        if latest_rate_limit:
            try:
                limited_at = datetime.fromisoformat(str(latest_rate_limit)).astimezone(timezone.utc)
                remaining = policy.cooldown_seconds - int((current - limited_at).total_seconds())
            except (TypeError, ValueError):
                remaining = 0
            if remaining > 0:
                return {
                    "allowed": False,
                    "mode": mode,
                    "reason": "rate_limit_cooldown",
                    "retry_after_seconds": remaining,
                }
        if mode == "enforce":
            usage = self.provider_summary(policy.provider, now=current, env=env)
            if int(usage.get("requests") or 0) >= policy.requests_per_window:
                return {
                    "allowed": False,
                    "mode": mode,
                    "reason": "operational_budget",
                    "retry_after_seconds": policy.window_seconds,
                }
        return {"allowed": True, "mode": mode, "reason": "within_budget", "retry_after_seconds": 0}

    def record_block(
        self,
        *,
        provider: str,
        operation: str,
        reason: str,
        retry_after_seconds: int,
        occurred_at: datetime | None = None,
    ) -> None:
        timestamp = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO api_budget_blocks "
                "(provider, operation, occurred_at, reason, retry_after_seconds) VALUES (?, ?, ?, ?, ?)",
                (
                    _provider(provider),
                    str(operation or "request").strip().lower()[:80] or "request",
                    timestamp,
                    str(reason or "blocked")[:40],
                    max(1, int(retry_after_seconds)),
                ),
            )

    def provider_summary(
        self,
        provider: str,
        *,
        now: datetime | None = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        policy = api_budget_policy(provider, env)
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        since = (current - timedelta(seconds=policy.window_seconds)).isoformat()
        if not self.path.exists():
            row = (0, 0, 0, None, None)
            history_row = (0, 0, 0, None)
            block_row = (0, 0)
        else:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(rate_limited), 0),
                           COALESCE(SUM(CASE WHEN status NOT IN ('OK', 'SUCCESS') THEN 1 ELSE 0 END), 0),
                           AVG(latency_ms), MAX(occurred_at)
                    FROM api_usage_events
                    WHERE provider = ? AND occurred_at >= ?
                    """,
                    (policy.provider, since),
                ).fetchone() or (0, 0, 0, None, None)
                history_since = (current - timedelta(hours=24)).isoformat()
                history_row = connection.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(rate_limited), 0),
                           COALESCE(SUM(CASE WHEN status NOT IN ('OK', 'SUCCESS') THEN 1 ELSE 0 END), 0),
                           MAX(occurred_at)
                    FROM api_usage_events
                    WHERE provider = ? AND occurred_at >= ?
                    """,
                    (policy.provider, history_since),
                ).fetchone() or (0, 0, 0, None)
                blocks_since = connection.execute(
                    "SELECT COUNT(*) FROM api_budget_blocks WHERE provider = ? AND occurred_at >= ?",
                    (policy.provider, since),
                ).fetchone()[0]
                blocks_24h_since = (current - timedelta(hours=24)).isoformat()
                blocks_24h = connection.execute(
                    "SELECT COUNT(*) FROM api_budget_blocks WHERE provider = ? AND occurred_at >= ?",
                    (policy.provider, blocks_24h_since),
                ).fetchone()[0]
                block_row = (blocks_since, blocks_24h)
        count, rate_limited, errors, average_latency, latest = row
        requests_24h, rate_limited_24h, errors_24h, latest_24h = history_row
        blocks, blocks_24h = block_row
        remaining = max(0, policy.requests_per_window - int(count))
        utilization = int(count) / policy.requests_per_window
        state = (
            "RATE_LIMITED"
            if int(rate_limited)
            else "ERROR"
            if int(errors)
            else "NEAR_LIMIT"
            if utilization >= 0.85
            else "OK"
        )
        return {
            "provider": policy.provider,
            "state": state,
            "requests": int(count),
            "budget": policy.requests_per_window,
            "remaining": remaining,
            "utilization": round(utilization, 4),
            "rate_limited": int(rate_limited),
            "errors": int(errors),
            "average_latency_ms": round(float(average_latency), 1) if average_latency is not None else None,
            "latest_at": latest,
            "requests_24h": int(requests_24h),
            "rate_limited_24h": int(rate_limited_24h),
            "errors_24h": int(errors_24h),
            "latest_24h_at": latest_24h,
            "window_seconds": policy.window_seconds,
            "enforcement": policy.enforcement,
            "blocks": int(blocks),
            "blocks_24h": int(blocks_24h),
        }

    def summary(self, *, now: datetime | None = None, env: Mapping[str, str] | None = None) -> dict[str, Any]:
        rows = [self.provider_summary(provider, now=now, env=env) for provider in sorted(_POLICIES)]
        return {
            "version": API_BUDGET_VERSION,
            "mode": api_budget_mode(env),
            "providers": rows,
            "request_count": sum(int(row["requests"]) for row in rows),
            "rate_limited_count": sum(int(row["rate_limited"]) for row in rows),
            "error_count": sum(int(row["errors"]) for row in rows),
            "near_limit_count": sum(row["state"] == "NEAR_LIMIT" for row in rows),
            "request_count_24h": sum(int(row["requests_24h"]) for row in rows),
            "rate_limited_count_24h": sum(int(row["rate_limited_24h"]) for row in rows),
            "error_count_24h": sum(int(row["errors_24h"]) for row in rows),
            "block_count": sum(int(row["blocks"]) for row in rows),
            "block_count_24h": sum(int(row["blocks_24h"]) for row in rows),
        }

    def prune(self, *, before: datetime) -> int:
        if not self.path.exists():
            return 0
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM api_usage_events WHERE occurred_at < ?",
                (before.astimezone(timezone.utc).isoformat(),),
            )
            return max(0, int(cursor.rowcount or 0))


def default_api_usage_path(base_dir: str | Path = ".") -> Path:
    configured = str(os.environ.get("ROXY_API_USAGE_DB", "")).strip()
    return Path(configured).expanduser() if configured else Path(base_dir) / "data" / "roxy_api_usage.sqlite"


def api_telemetry_enabled(env: Mapping[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    explicit = str(values.get("ROXY_API_TELEMETRY_ENABLED", "")).strip().lower()
    if explicit:
        return explicit in {"1", "true", "yes", "on"}
    return "PYTEST_CURRENT_TEST" not in values


@dataclass
class ApiCallObservation:
    status: str = "OK"
    http_status: int | None = None

    def set_http_status(self, value: Any) -> None:
        try:
            self.http_status = int(value)
        except (TypeError, ValueError):
            self.http_status = None
        if self.http_status == 429:
            self.status = "RATE_LIMITED"
        elif self.http_status is not None and self.http_status >= 400:
            self.status = "ERROR"


@contextmanager
def observe_api_call(
    provider: str,
    operation: str,
    *,
    path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
):
    """Record one real outbound call without changing its exception behavior."""
    observation = ApiCallObservation()
    if not api_telemetry_enabled(env):
        yield observation
        return
    started = time.perf_counter()
    ledger_path = Path(path) if path is not None else default_api_usage_path(Path(__file__).resolve().parents[1])
    ledger = ApiUsageLedger(ledger_path)
    try:
        admission = ledger.admission(provider, env=env)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        admission = {"allowed": True, "reason": "telemetry_unavailable", "retry_after_seconds": 0}
    if not admission.get("allowed"):
        retry_after = max(1, int(admission.get("retry_after_seconds") or 1))
        reason = str(admission.get("reason") or "blocked")
        try:
            ledger.record_block(
                provider=provider,
                operation=operation,
                reason=reason,
                retry_after_seconds=retry_after,
            )
        except (OSError, sqlite3.Error, ValueError, TypeError):
            pass
        raise ApiBudgetBlockedError(provider, reason, retry_after)
    try:
        yield observation
    except Exception as exc:
        observation.set_http_status(getattr(exc, "code", None) or getattr(exc, "status_code", None))
        if observation.status == "OK":
            observation.status = "ERROR"
        raise
    finally:
        try:
            ledger.record(
                provider=provider,
                operation=operation,
                status=observation.status,
                http_status=observation.http_status,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except (OSError, sqlite3.Error, ValueError, TypeError):
            # Telemetry must never break market data, identity, news or voice.
            pass
