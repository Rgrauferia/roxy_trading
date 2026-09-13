"""Disposable loopback registration/onboarding QA, excluded from the Home image.

Run: python -m tools.roxy_home_onboarding_preview [--port 31750] [--live-recipes]
Open: http://127.0.0.1:31750/lista#hoy

Create a synthetic username/password in the real registration form, then press
the explicitly labelled local challenge button. Only this preview process mocks
Turnstile; production admission, CAPTCHA and rate-limit code are unchanged.
Accounts and all Home data live in a temporary directory removed on exit.
This verifies application flow, not the actual Turnstile provider or deployment.
--live-recipes permits only public MyPlate recipe GETs, preserving its limits.
"""
from __future__ import annotations

import argparse
import hmac
import os
from pathlib import Path
import re
import secrets
import tempfile


SYNTHETIC_TOKEN = "roxy-onboarding-local-test-token"
CHALLENGE_SCRIPT = r"""(() => {
  'use strict';
  const widgets = new Map();
  window.turnstile = {
    render(selector, options) {
      const mount = document.querySelector(selector);
      const notice = document.createElement('p');
      notice.textContent = 'QA local: comprobación simulada. No valida el proveedor real.';
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'secondary full';
      button.textContent = 'Resolver comprobación local de prueba';
      const id = 'local-qa-' + widgets.size;
      button.addEventListener('click', () => {
        button.disabled = true;
        button.textContent = 'Comprobación local resuelta';
        options.callback('roxy-onboarding-local-test-token');
      });
      mount.replaceChildren(notice, button);
      widgets.set(id, { button, options });
      return id;
    },
    reset(id) {
      const widget = widgets.get(id);
      if (!widget) return;
      widget.options.callback('');
      widget.button.disabled = false;
      widget.button.textContent = 'Resolver comprobación local de prueba';
    }
  };
})();
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=31750)
    parser.add_argument("--live-recipes", action="store_true",
                        help="Allow only public recipe GETs to MyPlate; offline by default.")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port between 1024 and 65535.")

    import httpx
    import requests
    import uvicorn
    from fastapi.responses import Response
    from fastapi.routing import APIRoute

    original_directory = Path.cwd()
    # Do not inherit credentials, storage paths or configuration from any Roxy.
    # HOME is preserved as an OS setting; no user profile/secrets are read here.
    retained = {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE",
                "TZ", "TMPDIR", "TMP", "TEMP", "SYSTEMROOT", "WINDIR",
                "VIRTUAL_ENV", "PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING"}
    for name in list(os.environ):
        if name not in retained:
            os.environ.pop(name)
    os.environ.update(
        ROXY_HOME_API_KEY=secrets.token_urlsafe(32),
        ROXY_STATE_SYNC_USERS="onboarding-local-qa",
        ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED="0",
        ROXY_HOME_VIDEO_ENABLED="0",
        ROXY_HOME_RECIPE_VIDEO_ENABLED="0",
    )

    original_request = requests.sessions.Session.request

    def preview_requests(session, method, url, **kwargs):
        recipe_url = re.fullmatch(
            r"https://myplate\.food/api/v1/recipes(?:/[a-z0-9]+(?:-[a-z0-9]+)*)?", str(url))
        params = kwargs.get("params") or {}
        if (not args.live_recipes or str(method).upper() != "GET" or not recipe_url
                or not isinstance(params, dict) or set(params) - {"limit", "offset", "q", "category"}):
            raise requests.ConnectionError("External providers are disabled in onboarding QA.")
        # Public recipe reads carry no account/auth/cookie state and cannot redirect
        # to another endpoint. Existing adapter rate limits remain authoritative.
        session.trust_env = False
        session.auth = None
        session.cookies.clear()
        session.headers.clear()
        return original_request(session, "GET", url, params=params,
                                timeout=kwargs.get("timeout", (3, 5)),
                                stream=kwargs.get("stream", True), allow_redirects=False,
                                headers={"Accept": "application/json", "User-Agent": "RoxyHome/recipe-reader"})

    def no_httpx(*_args, **_kwargs):
        raise httpx.ConnectError("External providers are disabled in onboarding QA.")

    async def no_async_httpx(*_args, **_kwargs):
        raise httpx.ConnectError("External providers are disabled in onboarding QA.")

    requests.sessions.Session.request = preview_requests
    httpx.Client.send = no_httpx
    httpx.AsyncClient.send = no_async_httpx

    with tempfile.TemporaryDirectory(prefix="roxy-onboarding-qa-") as directory:
        try:
            os.chdir(directory)
            from tools import roxy_home_service as service
            from roxy_os.home_demo import DEMO_NOTICE_VERSION, TRIAL_AI_DAILY_LIMIT, TRIAL_DAYS

            service.SESSION_COOKIE = "roxy_home_onboarding_qa_session"
            service.registration_config = lambda: {
                "enabled": True, "site_key": "local-preview-only",
                "trial_days": TRIAL_DAYS, "ai_daily_limit": TRIAL_AI_DAILY_LIMIT,
                "notice_version": DEMO_NOTICE_VERSION,
            }
            service.verify_signup_token = lambda token: hmac.compare_digest(token.encode(), SYNTHETIC_TOKEN.encode())

            def local_cookie(response, value):
                # Production Secure cookies are unchanged. HTTP is loopback only.
                response.set_cookie(service.SESSION_COOKIE, value, httponly=True,
                                    samesite="strict", path="/", max_age=3600)

            service._set_session_cookie = local_cookie

            def preview_document():
                html = (service.ASSETS_DIR / "roxy_list.html").read_text(encoding="utf-8")
                html = html.replace("<head>", '<head>\n  <script src="/qa-onboarding-challenge.js" defer></script>', 1)
                headers = dict(service.shopping_page().headers)
                headers.pop("content-length", None)
                return Response(html, media_type="text/html", headers=headers)

            # Prepend these two HTML routes only inside this disposable process.
            service.app.router.routes[0:0] = [
                APIRoute(path, preview_document, methods=["GET", "HEAD"], include_in_schema=False)
                for path in ("/home", "/lista")
            ]

            @service.app.get("/qa-onboarding-challenge.js", include_in_schema=False)
            def local_challenge():
                return Response(CHALLENGE_SCRIPT, media_type="application/javascript",
                                headers={"Cache-Control": "no-store"})

            @service.app.middleware("http")
            async def require_loopback(request, call_next):
                if request.url.hostname not in {"127.0.0.1", "localhost"}:
                    return Response("Loopback QA only", status_code=403)
                return await call_next(request)

            print(f"Temporary synthetic Home data only: {directory}", flush=True)
            print(f"Registration QA: http://127.0.0.1:{args.port}/lista#hoy", flush=True)
            source = "Only public MyPlate recipe GETs allowed." if args.live_recipes else "No outbound provider HTTP."
            print(f"Turnstile is simulated locally. {source} Production signup remains unchanged.", flush=True)
            uvicorn.run(service.app, host="127.0.0.1", port=args.port, access_log=False)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    main()
