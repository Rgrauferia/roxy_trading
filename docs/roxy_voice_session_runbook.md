# Roxy Voice Session Runbook

This runbook captures the local voice controls for Roxy session memory in Roxy Live.

## ElevenLabs Roxy Trading Agent

The production voice assistant uses the existing ElevenLabs agent:

- Agent ID: `agent_6101kwchebzdf91rfk9757wq0mk4`
- Server-only env vars: `ELEVENLABS_AGENT_ID`, `ELEVENLABS_API_KEY`
- Local setup helper: `python3 scripts/configureElevenLabsLocal.py`
- Safe diagnostic: `python3 scripts/checkElevenLabsRoxy.py`

The API key must stay in server-side environment variables only. Never paste or expose the real key in frontend code, logs, screenshots, or committed files.

## Wake Voice Behavior

Roxy listens for:

- `Hola Roxy`
- `Hello Roxy`
- `Hey Roxy`
- `Roxy abre`
- `Roxy escucha`
- `Roxy habla`

Browser security still requires microphone permission. On iPhone, Safari, Chrome, and desktop browsers, the user may need to tap the floating Roxy avatar once and accept microphone access before the wake phrase can work.

Expected local status states:

- `Di: Hola Roxy`: microphone access is ready and wake listening is armed.
- `Toca una vez y di Hola Roxy`: the browser needs a user gesture before mic access.
- `Toca la pantalla y acepta el microfono`: mic permission was blocked or not granted.
- `Modo directo listo`: the app can attempt the public agent ID fallback.
- `Roxy hablando con voz temporal`: ElevenLabs did not connect yet, but the browser audio path works through the temporary Web Speech voice.

## Temporary Browser Voice Test

While ElevenLabs authentication is being fixed, Roxy has a browser-native voice fallback. Open the app, tap the floating Roxy assistant once, and the browser should speak a short Spanish greeting. This does not use the ElevenLabs API key and does not send secrets to the frontend.

If you do not hear it:

- make sure the iPhone/Mac is not muted
- tap directly on the Roxy floating avatar once
- allow microphone if the browser asks
- on iPhone, try Safari first because browser voices depend on the device
- reload the page after a new Render deploy

## Diagnosing ElevenLabs Auth

Run:

```bash
python3 scripts/checkElevenLabsRoxy.py
```

Expected success:

```text
[OK] Signed URL
[OK] Conversation token
```

If the script returns `401`, the code can mount the widget but ElevenLabs rejected the server credential. Check:

- the key is active and not revoked
- the key belongs to the same ElevenLabs workspace/account that owns the agent
- Render has the updated env var
- Render was manually redeployed after changing the env var
- the agent ID matches `agent_6101kwchebzdf91rfk9757wq0mk4`

The frontend falls back to `agentId` when signed URLs/tokens fail, but the private, production-ready flow requires the diagnostic to return `OK`.

## What These Commands Do

Session voice commands help Roxy keep conversational context across voice turns:

- list saved sessions
- switch to a named session
- resume the most recent saved session
- hydrate the active context chip with symbol, intent, market, timeframe, and handoff state when available

They do not call the broker, create orders, approve trades, or bypass confirmation.

## Commands

| Goal | Spanish | English |
| --- | --- | --- |
| List saved sessions | `Roxy, sesiones` | `Roxy, sessions` |
| List saved sessions | `Roxy, lista de sesiones` | `Roxy, list sessions` |
| Switch to a session | `Roxy, cambia a sesion scalping` | `Roxy, switch session to scalping` |
| Switch to a session | `Roxy, usa sesion earnings` | `Roxy, use session earnings` |
| Resume latest session | `Roxy, ultima sesion` | `Roxy, resume last session` |
| Resume latest session | `Roxy, retoma ultima sesion` | `Roxy, latest session` |
| Hear current context | `Roxy, contexto actual` | `Roxy, current context` |
| Hear a saved-session brief | `Roxy, resumen de sesion` | `Roxy, session brief` |

## Expected Behavior

When Roxy lists sessions, she should read a compact summary with recent session IDs, turn counts, last topic, and active trading context when available.

When Roxy switches or resumes a session, she should:

- update the browser `Session ID` field
- save the local browser setting
- request compact context from the backend
- update the `Context` chip and suggested actions
- include an `Abrir Roxy Trade` handoff link only when the saved context has a local trade dashboard URL

## Safety Contract

Session commands are memory and navigation controls only.

- No broker endpoint is called.
- No order ticket is submitted.
- No stop loss, take profit, or position size is acted on.
- Any trade still requires the normal preflight, ticket review, and explicit user confirmation.

If Roxy cannot load sessions, she should report the failure locally and remain usable.
