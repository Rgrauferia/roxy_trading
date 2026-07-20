"""Small OAuth callback helper to test redirect-based OAuth locally.

Usage:
  export GITHUB_CLIENT_ID=...; export GITHUB_CLIENT_SECRET=...
  python tools/oauth_server.py --port 5000

It prints the authorization URL to open in your browser. When GitHub redirects
back to /callback, the server exchanges the code for a token and prints the
user info to the console.
"""
from __future__ import annotations

import argparse
import hmac
import html
import os
import secrets
from flask import Flask, request
import auth
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from durable_storage import atomic_write_text

app = Flask(__name__)

@app.route("/")
def index():
    # show a small page with link to start oauth
    port = os.environ.get("OAUTH_SERVER_PORT", "5000")
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    state = os.environ.get("OAUTH_TEST_STATE") or secrets.token_urlsafe(32)
    os.environ["OAUTH_TEST_STATE"] = state
    url = auth.start_oauth_flow("github", redirect_uri, state=state)
    return (
        f'<p>Open this URL to start GitHub OAuth: <a href="{html.escape(url, quote=True)}">Authorize</a></p>'
        f"<p>Callback URL: {html.escape(redirect_uri)}</p>"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400
    port = os.environ.get("OAUTH_SERVER_PORT", "5000")
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    req_state = request.args.get("state") or ""
    expected = os.environ.get("OAUTH_TEST_STATE") or ""
    if not expected or not hmac.compare_digest(req_state, expected):
        return "invalid state", 400
    try:
        token = auth.exchange_code_for_token("github", code, redirect_uri)
        info = auth.fetch_user_info("github", token)
    except Exception as e:
        return f"OAuth exchange failed: {e}", 500
    # print to console for developer convenience
    print("GitHub user:", info)
    # write a small file to signal completion for local UI polling
    try:
        out = {
            "login": info.get("login"),
            "id": info.get("id"),
            "name": info.get("name"),
            "access_token": token,
        }
        callback_path = Path("run/oauth_callback.json")
        atomic_write_text(json.dumps(out), callback_path)
    except Exception as _:
        pass
    return f"Signed in as {html.escape(str(info.get('login') or 'GitHub user'))} — you can close this window."

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args()
    os.environ["OAUTH_SERVER_PORT"] = str(args.port)
    print("Start local OAuth server. Open http://127.0.0.1:%d/ to begin." % args.port)
    app.run(host="127.0.0.1", port=args.port)
