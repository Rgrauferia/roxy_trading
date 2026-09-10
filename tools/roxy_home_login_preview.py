"""Disposable, loopback-only login QA; never included in the production image.

Run: python -m tools.roxy_home_login_preview
Open: http://127.0.0.1:8768/lista#hoy
Synthetic username: loginqa
Synthetic password: Local-QA-only-2026

This fixture starts signed out, changes no existing Home data, and does not
inherit provider credentials. Its cookie name is separate from other previews.
"""
from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path


def main() -> None:
    import requests
    import uvicorn

    original_directory = Path.cwd()
    # Existing values are discarded only in this disposable preview process.
    for key in list(os.environ):
        if key.startswith(("ROXY_", "FAL_")) or "OPENAI" in key or "ELEVENLABS" in key or key.endswith("_API_KEY"):
            os.environ.pop(key)
    os.environ.update(
        ROXY_HOME_API_KEY=secrets.token_urlsafe(32),
        ROXY_STATE_SYNC_USERS="login-qa",
        ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED="0",
        ROXY_HOME_VIDEO_ENABLED="0",
        ROXY_HOME_RECIPE_VIDEO_ENABLED="0",
    )

    def no_external_requests(*_args, **_kwargs):
        raise requests.ConnectionError("External providers are disabled in the local login QA fixture.")

    requests.sessions.Session.request = no_external_requests
    with tempfile.TemporaryDirectory(prefix="roxy-login-qa-") as directory:
        try:
            os.chdir(directory)
            from roxy_os.home_accounts import HomeAccountStore
            from tools import roxy_home_service as service

            service.SESSION_COOKIE = "roxy_home_login_qa_session"

            def local_cookie(response, value):
                # Only this loopback fixture uses a non-Secure cookie over HTTP.
                # Production continues using Secure=True in the real service.
                response.set_cookie(service.SESSION_COOKIE, value, httponly=True,
                                    samesite="strict", path="/", max_age=3600)

            service._set_session_cookie = local_cookie
            HomeAccountStore("data/roxy_home_accounts.json").bootstrap(
                "login-qa", household_name="Hogar de prueba local",
                username="loginqa", display_name="Prueba de acceso",
                password="Local-QA-only-2026",
            )
            print(f"Disposable synthetic data only: {directory}", flush=True)
            print("Login QA: http://127.0.0.1:8768/lista#hoy", flush=True)
            print("Synthetic login only: loginqa / Local-QA-only-2026", flush=True)
            uvicorn.run(service.app, host="127.0.0.1", port=8768, access_log=False)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    main()
