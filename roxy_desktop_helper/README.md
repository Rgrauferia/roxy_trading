# Roxy Desktop Helper

Roxy Desktop Helper is the local bridge for future Mac-level assistance.

The web app can hear Roxy and understand the current Roxy Trading page, but a browser app cannot safely see the entire Mac, open local folders, or click other applications without a separate local helper and macOS permissions.

This first version is intentionally safe:

- Accepts local Roxy OS commands.
- Returns the Roxy OS response, plan, permission decision and prepared actions.
- Exposes a file safety check.
- Blocks real screen capture, system control, file reads and browser control by default.
- Exposes explicit endpoints for prepared local actions:
  - `POST /screen/summary`
  - `POST /browser/open`
  - `POST /file/read`

Run locally:

```bash
PYTHONPATH=. python3 -m roxy_desktop_helper.server
```

Or use the project script:

```bash
bash scripts/start_roxy_desktop_helper.sh
```

Health check:

```bash
curl http://127.0.0.1:8765/health
```

Optional local permissions are controlled by environment variables. Keep them off unless you are testing that exact capability:

```bash
export ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE=1
export ROXY_DESKTOP_ALLOW_BROWSER_OPEN=1
export ROXY_DESKTOP_ALLOW_FILE_READ=1
```

These flags do not enable destructive actions. Screen control, system writes, `sudo`, `rm -rf`, deploys and real-money operations remain blocked.

Command test:

```bash
curl -s http://127.0.0.1:8765/command \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"roberto","text":"Hola Roxy dime que estoy viendo en pantalla","context":{"page":"Dashboard","module":"acciones","symbol":"AAPL"}}'
```

Browser preparation test:

```bash
curl -s http://127.0.0.1:8765/browser/open \
  -H 'Content-Type: application/json' \
  -d '{"query":"precio de bitcoin hoy"}'
```

File read preparation test:

```bash
curl -s http://127.0.0.1:8765/file/read \
  -H 'Content-Type: application/json' \
  -d '{"path":"README.md"}'
```

Screen preparation test:

```bash
curl -s http://127.0.0.1:8765/screen/summary \
  -H 'Content-Type: application/json' \
  -d '{"context":{"page":"Dashboard","module":"acciones","symbol":"AAPL"}}'
```

Next controlled steps:

1. Add a signed local app wrapper.
2. Request macOS Screen Recording permission.
3. Request macOS Accessibility permission only for approved click/type actions.
4. Add explicit user confirmation for opening files, clicking, typing, sending messages and money-related actions.
5. Connect Streamlit/ElevenLabs to this helper only on `127.0.0.1`.
