"""Fail-closed admission policy for Home's public, five-day pilot."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import requests

TRIAL_DAYS = 5
TRIAL_AI_DAILY_LIMIT = 5
TRIAL_MEMBER_LIMIT = 6
DEMO_NOTICE_VERSION = "2026-09-06"


def registration_config() -> dict:
    site_key = os.getenv("ROXY_HOME_TURNSTILE_SITE_KEY", "").strip()
    secret = os.getenv("ROXY_HOME_TURNSTILE_SECRET_KEY", "").strip()
    hosts = {s.strip().lower() for s in os.getenv("ROXY_HOME_SIGNUP_HOSTS", "").split(",") if s.strip()}
    # The provider's published test credentials must never enable production.
    test_keys = any(key.startswith(("1x00000000000000000000", "2x00000000000000000000", "3x00000000000000000000")) for key in (site_key, secret))
    ready = bool(site_key and secret and hosts and not test_keys)
    enabled = os.getenv("ROXY_HOME_PUBLIC_SIGNUP_ENABLED", "0") == "1" and ready
    return {"enabled": enabled, "site_key": site_key if enabled else "", "trial_days": TRIAL_DAYS,
            "ai_daily_limit": TRIAL_AI_DAILY_LIMIT, "notice_version": DEMO_NOTICE_VERSION}


def verify_signup_token(token: str) -> bool:
    if not registration_config()["enabled"] or not 1 <= len(token) <= 2048:
        return False
    try:
        response = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                                 json={"secret": os.environ["ROXY_HOME_TURNSTILE_SECRET_KEY"], "response": token},
                                 timeout=10)
        response.raise_for_status()
        result = response.json()
        hosts = {s.strip().lower() for s in os.environ["ROXY_HOME_SIGNUP_HOSTS"].split(",") if s.strip()}
        issued = datetime.fromisoformat(str(result.get("challenge_ts") or "").replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - issued).total_seconds()
        return (result.get("success") is True and result.get("hostname", "").lower() in hosts
                and result.get("action") == "home_signup" and 0 <= age <= 300)
    except (requests.RequestException, ValueError, TypeError, AttributeError, KeyError):
        return False


def trial_access_mode(method: str, path: str) -> str:
    """Only reviewed routes are allowed. New paid routes default to unavailable.

    A request quota supplements, never replaces/increases, the Home AI ledger.
    No image/video generation, voice sessions, commerce feeds or device control.
    """
    if (method, path) in {("GET", "/api/fitness/v1/status"), ("GET", "/api/fitness/v1/me/profile"), ("GET", "/api/fitness/v1/me/data"), ("PATCH", "/api/fitness/v1/me/profile"), ("POST", "/api/fitness/v1/me/consents"), ("DELETE", "/api/fitness/v1/me/data"), ("POST", "/api/fitness/v1/plans/preview")}:
        # Preference foundation only; no workouts, AI calls or commercial writes.
        return "local"
    if method == "GET" and re.fullmatch(r"/api/fitness/v1/exercises(?:/wger-[A-Za-z0-9-]+)?", path):
        # Licensed bundled education, never a provider call or workout activation.
        return "local"
    if path in {"/v1/home-account/me", "/v1/home-account/preferences", "/v1/home-account/members"}:
        return "local"
    if method == "GET" and path in {"/v1/home-food/recipe-photo", "/v1/home-food/recipe-photo-info"}:
        return "local"
    if method == "GET" and re.fullmatch(r"/v1/home-food/[^/]+/providers/recipes/status", path):
        # Configuration summary only; provider search/detail remain unavailable.
        return "local"
    if method == "GET" and re.fullmatch(r"/v1/home-food/[^/]+/drinks(?:/[a-z0-9]+(?:-[a-z0-9]+)*)?", path):
        # Bundled licensed drinks; no provider calls or household writes.
        return "local"
    if method == "GET" and re.fullmatch(
            r"/v1/home-food/[^/]+/myplate-recipes(?:/[a-z0-9]+(?:-[a-z0-9]+)*)?", path):
        # Free live source reads, independently rate-limited. No AI or imports.
        return "local"
    if method == "GET" and re.fullmatch(
            r"/v1/home-food/[^/]+/open-recipes(?:/summaries|/detail/[A-Za-z0-9][A-Za-z0-9_-]{0,127})?", path):
        # Bundled licensed originals: no API key, spend, AI or household writes.
        return "local"
    if re.fullmatch(r"/v1/assistant/command/[^/]+", path) and method == "POST":
        return "ai"
    if method == "GET" and re.fullmatch(r"/v1/(?:shopping|home-food|home-daily|home-weather|home-plants|home-calendar|home-design|home-commerce)/[^/]+", path):
        return "local"
    if path == "/v1/home-family" or re.fullmatch(r"/v1/home-family/(?:location|profile|places(?:/[^/]+)?|members/[^/]+/history|connections/[^/]+)", path):
        return "local"
    if re.fullmatch(r"/v1/shopping/[^/]+(?:/[^/]+)?", path):
        return "local"
    if re.fullmatch(r"/v1/home-food/[^/]+/(?:recipes|substitutions|food-safety|recipe-imports)", path) and method == "POST":
        return "ai"
    if re.fullmatch(r"/v1/home-food/[^/]+/(?:profile|pantry|pets|pets/[^/]+/(?:habitat|medical-history|care-log|products/[^/]+/shopping)|recipe-imports/commit|recipes/[^/]+(?:/(?:scale|shopping-preview|shopping-commit|cooking-sessions))?|weekly-plans(?:/[^/]+/(?:shopping-commit|meal|day))?|cooking-sessions/[^/]+(?:/timers(?:/[^/]+)?)?)", path):
        return "local"
    if re.fullmatch(r"/v1/home-calendar/[^/]+/(?:drafts(?:/confirm)?|events/[^/]+)", path):
        return "local"
    if re.fullmatch(r"/v1/home-commerce/[^/]+/profile", path):
        return "local"
    return "unavailable"
