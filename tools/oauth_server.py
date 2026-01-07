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
import os
from urllib.parse import urlencode
from flask import Flask, request, redirect
import auth
import json
from pathlib import Path

app = Flask(__name__)

@app.route("/")
def index():
    # show a small page with link to start oauth
    cfg = auth.get_provider_config("github")
    client_id = cfg.get("client_id")
    port = os.environ.get("OAUTH_SERVER_PORT", "5000")
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    url = auth.start_oauth_flow("github", redirect_uri)
    return f"<p>Open this URL to start GitHub OAuth: <a href=\"{url}\">Authorize</a></p><p>Callback URL: {redirect_uri}</p>"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400
    port = os.environ.get("OAUTH_SERVER_PORT", "5000")
    redirect_uri = f"http://127.0.0.1:{port}/callback"
        # validate state if present
        req_state = request.args.get("state")
        expected = os.environ.get("OAUTH_TEST_STATE")
        if expected and req_state != expected:
            return ("invalid state", 400)
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
        Path("run").mkdir(parents=True, exist_ok=True)
        Path("run/oauth_callback.json").write_text(json.dumps(out))
    except Exception as _:
        pass
    return f"Signed in as {info.get('login')} — you can close this window."

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args()
    os.environ["OAUTH_SERVER_PORT"] = str(args.port)
    print("Start local OAuth server. Open http://127.0.0.1:%d/ to begin." % args.port)
    app.run(host="127.0.0.1", port=args.port)
