"""Small admin API to export role audit data.

Protects endpoints with `ADMIN_TOKEN` environment variable or `config.ADMIN_TOKEN`.

Endpoints:
- GET /audit.csv -> CSV of role_audit table
- GET /audit/log -> raw logs/role_audit.log contents
"""
from __future__ import annotations

import os
from flask import Flask, request, Response, abort, jsonify
import storage
import io
import csv
from tradingview_webhooks import append_authenticated_tradingview_webhook, configured_tradingview_webhook_secret

app = Flask(__name__)


def _check_token():
    token = os.environ.get("ADMIN_TOKEN")
    try:
        from config import ADMIN_TOKEN as cfg_token
    except Exception:
        cfg_token = None
    if not token and cfg_token:
        token = cfg_token
    if not token:
        return False
    # require token via header `X-Admin-Token` only (avoid token-in-query leakage)
    h = request.headers.get("X-Admin-Token")
    return h == token


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "roxy-admin-api"})


@app.route("/tradingview/status")
def tradingview_status():
    configured = bool(configured_tradingview_webhook_secret())
    return jsonify(
        {
            "ok": True,
            "endpoint": "/tradingview/webhook",
            "auth": "configured" if configured else "missing",
            "paper_only": True,
            "real_orders_enabled": False,
        }
    )


@app.route("/audit.csv")
def audit_csv():
    if not _check_token():
        abort(403)
    rows = storage.list_role_audit(limit=1000)
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["id", "actor", "target_user", "old_role", "new_role", "ts"])
    for r in rows:
        w.writerow(r)
    return Response(output.getvalue(), mimetype="text/csv")


@app.route("/audit/log")
def audit_log():
    if not _check_token():
        abort(403)
    p = os.path.join("logs", "role_audit.log")
    if not os.path.exists(p):
        return Response("", mimetype="text/plain")
    with open(p, "r", encoding="utf-8") as fh:
        data = fh.read()
    return Response(data, mimetype="text/plain")


@app.route("/tradingview/webhook", methods=["POST"])
def tradingview_webhook():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "status": "INVALID_JSON", "detail": "Expected JSON object payload."}), 400
    result = append_authenticated_tradingview_webhook(payload, headers=request.headers)
    if result.get("ok"):
        return jsonify(result), 200
    status_code = 503 if result.get("status") == "MISSING_SECRET_CONFIG" else 403
    return jsonify(result), status_code


if __name__ == "__main__":
    port = int(os.environ.get("ADMIN_API_PORT", 8001))
    print(f"Starting admin API on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port)
