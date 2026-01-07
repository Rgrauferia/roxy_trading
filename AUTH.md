Authentication and Admin Promotion

- The app supports GitHub OAuth via device flow and redirect flow.
- For admin auto-promotion based on organization membership, set `ADMIN_ORGS` in `config.py` as a comma-separated list of GitHub organizations (e.g. "myorg,anotherorg").
- OAuth flows request the `read:org` scope so the app can verify organization membership; ensure your OAuth client (app) is configured to allow this scope and that `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` are set in the environment or `config.py`.
- A bootstrap `ADMIN_TOKEN` in `config.py` can be used to promote the first admin in the sidebar. In production prefer org-based promotion and rotate the `ADMIN_TOKEN` regularly.

Audit logs:

- Role changes are recorded in the database `role_audit` table and appended to `logs/role_audit.log` (tab-separated: timestamp,actor,target_user,old_role,new_role).
- Admins can review recent role changes in the Streamlit admin sidebar and export a CSV for compliance.

Local testing tips:

1. Ensure Flask is installed to run `tools/oauth_server.py` for redirect-flow testing:

```bash
source .venv/bin/activate
pip install Flask
python tools/oauth_server.py --port 5000
```

2. Start Streamlit and use the sidebar to begin the redirect flow or device flow. After authorizing in GitHub, the server will write `run/oauth_callback.json` and Streamlit can pick it up.
 
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
