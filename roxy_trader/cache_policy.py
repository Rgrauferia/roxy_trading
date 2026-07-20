"""Versioned cache freshness policy shared by Roxy data consumers."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from typing import Mapping


CACHE_POLICY_VERSION = "roxy-cache/1.0.0"


@dataclass(frozen=True)
class CachePolicy:
    key: str
    data_class: str
    default_seconds: int
    minimum_seconds: int
    maximum_seconds: int
    stale_multiplier: float = 2.0
    failure_mode: str = "recompute_or_explicit_error"

    @property
    def env_key(self) -> str:
        suffix = re.sub(r"[^A-Z0-9]+", "_", self.key.upper()).strip("_")
        return f"ROXY_CACHE_TTL_{suffix}"


_POLICIES = {
    policy.key: policy
    for policy in (
        CachePolicy("stock_quote", "market_quote", 1, 1, 5, 1.0, "never_serve_unlabeled_stale"),
        CachePolicy("stock_plan", "derived_market_plan", 3, 1, 10, 1.0, "never_serve_unlabeled_stale"),
        CachePolicy("live_price", "market_quote", 5, 1, 15, 1.0, "never_serve_unlabeled_stale"),
        CachePolicy("crypto_market", "exchange_candles", 5, 1, 15, 1.0, "never_serve_unlabeled_stale"),
        CachePolicy("local_health", "local_service_health", 6, 1, 30, 1.5),
        CachePolicy("opportunity", "derived_opportunity", 10, 5, 60, 1.0, "mark_wait_if_stale"),
        CachePolicy("webhook", "external_confirmation", 15, 1, 60, 1.0, "mark_unconfirmed_if_stale"),
        CachePolicy("deriv_contract", "contract_catalog", 15, 5, 120, 2.0),
        CachePolicy("chart", "market_candles", 20, 5, 120, 1.5, "label_provider_age"),
        CachePolicy("voice_session", "signed_session", 45, 15, 60, 1.0, "request_new_session"),
        CachePolicy("email_metadata", "personal_email_metadata", 30, 10, 120, 1.0, "explicit_provider_state"),
        CachePolicy("market_screen", "market_screener", 45, 10, 180, 1.5, "label_delayed"),
        CachePolicy("finviz", "external_screener", 45, 15, 300, 2.0, "label_delayed"),
        CachePolicy("memory", "local_analytics", 60, 10, 300, 3.0),
        CachePolicy("paper_reconcile", "paper_results", 60, 10, 300, 2.0),
        CachePolicy("academy_market", "educational_market_example", 60, 15, 300, 2.0, "label_delayed"),
        CachePolicy("mini_chart", "historical_chart", 300, 30, 900, 2.0, "label_provider_age"),
        CachePolicy("backtest_summary", "historical_analytics", 300, 30, 1800, 4.0),
        CachePolicy("news", "news_feed", 300, 60, 900, 2.0, "serve_stale_labeled"),
        CachePolicy("company_profile", "fundamental_profile", 21_600, 900, 86_400, 4.0, "serve_stale_labeled"),
        CachePolicy("asset_identity_ui", "asset_identity", 86_400, 3600, 604_800, 7.0, "use_financial_fallback"),
        CachePolicy("asset_identity_disk", "asset_identity", 1_209_600, 86_400, 2_592_000, 2.0, "use_financial_fallback"),
    )
}


def cache_policy(key: str) -> CachePolicy:
    normalized = str(key or "").strip().lower()
    try:
        return _POLICIES[normalized]
    except KeyError as exc:
        raise KeyError(f"Unknown Roxy cache policy: {key!r}") from exc


def _parse_override(policy: CachePolicy, env: Mapping[str, str]) -> tuple[int, str]:
    raw = str(env.get(policy.env_key, "")).strip()
    if not raw:
        return policy.default_seconds, "default"
    try:
        requested = int(raw)
    except (TypeError, ValueError):
        return policy.default_seconds, "invalid"
    effective = min(policy.maximum_seconds, max(policy.minimum_seconds, requested))
    return effective, "override" if effective == requested else "clamped"


def cache_ttl(key: str, env: Mapping[str, str] | None = None) -> int:
    policy = cache_policy(key)
    effective, _state = _parse_override(policy, env if env is not None else os.environ)
    return effective


def cache_age_status(key: str, age_seconds: float | int | None, env: Mapping[str, str] | None = None) -> str:
    if age_seconds is None:
        return "NO_DATA"
    policy = cache_policy(key)
    ttl = cache_ttl(key, env)
    age = max(0.0, float(age_seconds))
    if age <= ttl:
        return "FRESH"
    if age <= ttl * max(1.0, float(policy.stale_multiplier)):
        return "STALE"
    return "EXPIRED"


def cache_policy_contract(env: Mapping[str, str] | None = None) -> dict[str, object]:
    values = env if env is not None else os.environ
    rows = []
    for key in sorted(_POLICIES):
        policy = _POLICIES[key]
        effective, override_state = _parse_override(policy, values)
        row = asdict(policy)
        row.update(
            {
                "env_key": policy.env_key,
                "effective_seconds": effective,
                "override_state": override_state,
            }
        )
        rows.append(row)
    return {"version": CACHE_POLICY_VERSION, "policies": rows}


def cache_policy_issues(env: Mapping[str, str] | None = None) -> list[dict[str, object]]:
    return [
        row
        for row in cache_policy_contract(env)["policies"]  # type: ignore[index]
        if row["override_state"] in {"invalid", "clamped"}
    ]
