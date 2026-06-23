# Roxy Voice Session Runbook

This runbook captures the local voice controls for Roxy session memory in Roxy Live.

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
