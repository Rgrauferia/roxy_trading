# Authentication and administrative access

The active Streamlit gate supports local accounts, Google/Apple OAuth when their provider configuration is present, and passkeys. An unauthenticated browser session cannot reach the Dashboard; it remains on the sign-in/register surface.

Local account security contract:

- Passwords require at least 10 characters. New PBKDF2-SHA256 hashes use 600,000 iterations; legacy 160,000-iteration hashes are upgraded after the next successful login.
- Five failed attempts within 15 minutes lock that normalized identity for 15 minutes. The attempt table stores only a SHA-256 identity key.
- Remembered sessions expire after 30 days by default and are revoked server-side on logout or expiration. Override the lifetime with `ROXY_SESSION_MAX_AGE_SECONDS` when deployment policy requires it.
- User JSON backups and the SQLite database are owner-only (`0600`); JSON writes use a lock, `fsync` and atomic replacement.
- Authenticated local users can change their password from the sidebar under `Seguridad de cuenta`; a successful change rotates the remembered session and revokes the previous token. Email-based recovery is explicitly shown as unconfigured until a delivery provider is connected.
- Legacy plaintext session values are migrated to SHA-256 immediately when account storage is loaded. The `Diagnostico` page audits JSON/SQLite permissions, the persistent throttle and plaintext-token count without exposing account identifiers or secret material.

For a local administrator recovery, run the prompt-based command below. The password is read with `getpass`, never accepted as a command-line argument, and all remembered sessions are revoked:

```bash
PYTHONPATH=. .venv/bin/python tools/reset_local_password.py USERNAME
```

GitHub OAuth code remains as a developer helper for local integration work, but it is not part of the active production login surface. Do not describe it as connected until the callback is wired into the canonical account/session flow.

The API development login is fail-closed. `/api/auth/mock-login` returns `404` unless `ROXY_ENABLE_MOCK_LOGIN=1`, `ROXY_ENV` is a development/test value, and the caller is loopback. Admin endpoints return `403` when `ADMIN_TOKEN`, `ADMIN_USERS`, and `ADMIN_ORGS` are absent; the optional `ROXY_ALLOW_INSECURE_DEV_ADMIN=1` bypass is likewise restricted to development/test plus loopback. Secret names, metadata, revisions, values, and API-key management all require admin authorization.

The voice API allows unauthenticated requests only from loopback when `VOICE_API_KEY` is absent; non-loopback callers receive `503`. This preserves the localhost-only LaunchAgent workflow but is not a multi-device security configuration. The managed service defaults to `ROXY_VOICE_BIND_HOST=127.0.0.1` and port `8010`. Remote use requires a non-loopback bind, `VOICE_API_KEY`, an explicit `ROXY_STATE_SYNC_USERS` allowlist and HTTPS (`ROXY_VOICE_PUBLIC_BASE_URL=https://...` or reviewed TLS termination with `ROXY_VOICE_TLS_TERMINATED=true`); port 8010 must not be exposed directly. AI signal, A/B execution and automation routes always require admin/API-key authentication and enforce `ai:signal`, `ab:execute` and `auto:execute` scopes for managed keys.

The admin OAuth bridge encrypts its one-time Roxy session result with Fernet before storing it in `oauth_results`. `check_state` verifies the signed state, decrypts once, deletes the row, and returns the token. Existing plaintext rows are migrated when a valid Fernet key is available; any remaining legacy plaintext is reported as an authentication-security error.

Audit logs:

- Role changes are recorded in the database `role_audit` table and appended to `logs/role_audit.log` (tab-separated: timestamp,actor,target_user,old_role,new_role).
- Administrative exports are available through the separately protected admin API described below.

Local testing tips:

1. Ensure Flask is installed to run `tools/oauth_server.py` for redirect-flow testing:

```bash
source .venv/bin/activate
pip install Flask
python tools/oauth_server.py --port 5000
```

2. Open `http://127.0.0.1:5000/` to start the developer-only redirect flow. The helper generates and validates an OAuth `state`, and writes a callback file with owner-only permissions. The active Streamlit gate does not consume this file automatically.

The admin API redirect flow is separate: it requires a non-expired, one-time server state and the server-stored redirect URI. Provider tokens remain encrypted; only a one-time Roxy session result is exposed to the signed polling route.
 
Admin API
---------

- A small admin API is available at `tools/admin_api.py` which exposes audit exports. It is protected by the `ADMIN_TOKEN` (env var or `config.ADMIN_TOKEN`).

Run locally:

```bash
export ADMIN_TOKEN=your_token_here
python tools/admin_api.py
```

Then fetch the CSV:

```bash
curl -H "X-Admin-Token: $ADMIN_TOKEN" http://127.0.0.1:8001/audit.csv -o role_audit.csv
```

TradingView webhook endpoint:

`tools/admin_api.py` also exposes `POST /tradingview/webhook` for webhook bridges. It is protected by `TRADINGVIEW_WEBHOOK_SECRET`, not by `ADMIN_TOKEN`, so TradingView alerts can be scoped to signal ingestion only.

```bash
export TRADINGVIEW_WEBHOOK_SECRET='use-a-long-random-secret'
make tradingview-bridge
curl -X POST http://127.0.0.1:8001/tradingview/webhook \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Secret: $TRADINGVIEW_WEBHOOK_SECRET" \
  -d '{"symbol":"NASDAQ:AAPL","timeframe":"15","signal":"BUY","price":185.25}'
```

TradingView can also send the same secret as `"passphrase"` in the JSON payload. Roxy redacts secret-like fields before writing `alerts/tradingview_webhooks.jsonl`. The endpoint records analysis confirmations only and does not enable broker execution.

Public TradingView webhook URL:

TradingView must call a public HTTPS URL, but Roxy's dashboard remains fixed at `http://localhost:3000` and the webhook bridge remains local at `http://127.0.0.1:8001`. Use a tunnel such as `cloudflared tunnel --url http://127.0.0.1:8001` or `ngrok http 8001`, then set:

```bash
export TRADINGVIEW_PUBLIC_WEBHOOK_URL='https://your-public-url.example/tradingview/webhook'
make tradingview-tunnel-check
```

The public URL is used only for TradingView signal ingestion. It does not enable live orders.
