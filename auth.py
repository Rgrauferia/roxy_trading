"""OAuth scaffold for future integration.

This module provides placeholder functions and notes for integrating
OAuth-based authentication (GitHub, Google) into the Streamlit app.

To implement:
- Choose a provider (GitHub, Google) and create OAuth client credentials.
- Store client id/secret in env vars (e.g. `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`).
- Use a library such as `authlib` or `requests-oauthlib` to perform the flow.
- Exchange code for token on a secure server endpoint; store user info in session.

Current functions are stubs returning `None` or raising `NotImplementedError`.
"""
from __future__ import annotations

import os
from typing import Optional, Dict
import time
import requests
from dataclasses import dataclass


def get_provider_config(provider: str) -> Dict[str, str]:
    if provider.lower() == "github":
        return {
            "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "user_api": "https://api.github.com/user",
        }
    raise NotImplementedError("Only GitHub scaffold provided")


def start_oauth_flow(provider: str, redirect_uri: str) -> str:
    """Return an authorization URL to redirect the user to.

    In Streamlit, you would open this URL in the browser.
    """
    cfg = get_provider_config(provider)
    if not cfg.get("client_id"):
        raise RuntimeError("OAuth client_id not configured in env vars")
    # Build the authorize URL with state (left as an exercise)
    # Request user and org read scopes so we can check org membership for admin auto-promotion
    scope = "read:user read:org"
    from urllib.parse import urlencode
    # include a state parameter to mitigate CSRF in redirect flows
    state = os.environ.get("OAUTH_TEST_STATE") or ""
    params = {"client_id": cfg['client_id'], "redirect_uri": redirect_uri, "scope": scope}
    if state:
        params["state"] = state
    return f"{cfg['authorize_url']}?{urlencode(params)}"


def exchange_code_for_token(provider: str, code: str, redirect_uri: str) -> Optional[str]:
    """Exchange authorization code for access token.

    Implement using `requests` or `authlib` on a secure endpoint.
    """
    cfg = get_provider_config(provider)
    client_id = cfg.get("client_id")
    client_secret = cfg.get("client_secret")
    token_url = cfg.get("token_url")
    if not (client_id and client_secret and token_url):
        raise RuntimeError("OAuth client credentials not configured in env vars")

    headers = {"Accept": "application/json"}
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    r = requests.post(token_url, data=data, headers=headers, timeout=10)
    r.raise_for_status()
    jd = r.json()
    token = jd.get("access_token")
    return token


def fetch_user_info(provider: str, access_token: str) -> Dict[str, str]:
    """Fetch basic user profile information from provider using `access_token`."""
    cfg = get_provider_config(provider)
    user_api = cfg.get("user_api")
    if not user_api:
        raise RuntimeError("Provider user API not configured")
    headers = {"Authorization": f"token {access_token}", "Accept": "application/json"}
    r = requests.get(user_api, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


@dataclass
class DeviceFlowResult:
    user: str
    access_token: str


def github_device_flow(timeout: int = 300, interval: int = 5) -> DeviceFlowResult:
    """Perform GitHub OAuth device flow. Requires `GITHUB_CLIENT_ID` env var.

    Returns a DeviceFlowResult with username and access_token.
    """
    cfg = get_provider_config("github")
    client_id = cfg.get("client_id")
    if not client_id:
        raise RuntimeError("GITHUB_CLIENT_ID not configured in environment")

    # Backwards-compatible wrapper: start flow then poll for completion
    df = github_start_device_flow()
    return github_poll_device_flow(df["device_code"], timeout=timeout, interval=interval)


def github_start_device_flow() -> Dict[str, str]:
    """Start GitHub device flow and return device/user codes and verification URI.

    Returns dict with keys: `device_code`, `user_code`, `verification_uri`, `verification_uri_complete`.
    """
    cfg = get_provider_config("github")
    client_id = cfg.get("client_id")
    if not client_id:
        raise RuntimeError("GITHUB_CLIENT_ID not configured in environment")

    # request device code with org read scope included
    r = requests.post(
        "https://github.com/login/device/code",
        data={"client_id": client_id, "scope": "read:user read:org"},
        headers={"Accept": "application/json"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "device_code": data["device_code"],
        "user_code": data["user_code"],
        "verification_uri": data.get("verification_uri"),
        "verification_uri_complete": data.get("verification_uri_complete"),
    }


def github_poll_device_flow(device_code: str, timeout: int = 300, interval: int = 5) -> DeviceFlowResult:
    """Poll GitHub for device flow completion and return `DeviceFlowResult`.

    Raises RuntimeError on timeout or on other device-flow errors.
    """
    cfg = get_provider_config("github")
    client_id = cfg.get("client_id")
    if not client_id:
        raise RuntimeError("GITHUB_CLIENT_ID not configured in environment")

    token = None
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(interval)
        tr = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        tr.raise_for_status()
        td = tr.json()
        if td.get("access_token"):
            token = td.get("access_token")
            break
        if td.get("error") == "authorization_pending":
            continue
        if td.get("error"):
            raise RuntimeError(f"Device flow error: {td.get('error_description') or td.get('error')}")

    if not token:
        raise RuntimeError("Device flow timed out")

    # fetch user info
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    ur = requests.get("https://api.github.com/user", headers=headers, timeout=10)
    ur.raise_for_status()
    info = ur.json()
    username = info.get("login")
    return DeviceFlowResult(user=username, access_token=token)


def get_user_orgs(access_token: str) -> list[str]:
    """Return list of organization logins for the authenticated user."""
    if not access_token:
        return []
    headers = {"Authorization": f"token {access_token}", "Accept": "application/json"}
    r = requests.get("https://api.github.com/user/orgs", headers=headers, timeout=10)
    if r.status_code != 200:
        return []
    js = r.json()
    return [o.get("login") for o in js if o.get("login")]
