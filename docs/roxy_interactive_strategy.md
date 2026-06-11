# Roxy Interactive Strategy

## Role

Roxy Interactive is the conversation and strategy brain for the assistant. It does not own the visual avatar, the broker execution layer, or the market data pipeline. Its job is to decide what Roxy should say, how cautious she should be, and which next action should be offered.

## Personality Contract

- Voice: feminine, calm, direct, conversational Spanish by default.
- Identity: professional synthetic assistant for Grau Service LLC / Roxy Trading.
- Style: explain first, recommend with context, avoid hype, avoid guaranteed outcomes.
- Trading safety: never imply certainty, never execute or approve sensitive actions without explicit user confirmation.
- News safety: if no live news source is connected, Roxy must say that instead of inventing headlines.
- Action safety: spoken commands like "buy now" or "send order" produce `action_confirmation_required`, not execution.

## Module Boundary

The strategy layer lives in `tools/roxy_interactive_brain.py`.

It returns a `RoxyBrainReply` object with:

- `reply`: speakable text.
- `intent`: detected user intent.
- `voice_style`: requested voice family, currently `female_es_latam`.
- `avatar_state`: visual state such as `ready`, `speaking`, or `blocked`.
- `emotion`: controlled expression such as `calm`, `warm`, `analytical`, `cautious`, or `serious`.
- `should_speak`: whether the UI should read it out loud.
- `needs_live_source`: whether the answer needs live data before it can be complete.
- `safety_level`: normal or guarded.
- `priority`: normal or high.
- `suggested_actions`: integration hints for the visual and operational tabs.

The current text-only bridge is `tools/voice_assistant.py`. The Streamlit voice panel can keep calling `generate_reply()` and will receive the brain's speakable answer.

For richer clients, use `generate_reply_state()` or the FastAPI endpoint `POST /v1/assist/state`. This returns the full state object so the UI can animate Roxy's face, speaking state, safety level, and next-action buttons without parsing text.

For real-time UI flows, use `POST /v1/assist/events`. It returns ordered events such as `transcript_received`, `thinking`, `reply_ready`, `speak`, `live_source_required`, and `action_confirmation_required`.

For a direct browser experience, run the voice service and open `/roxy-live`. That page provides microphone capture, text fallback, Roxy avatar, browser voice selection, voice rate/pitch controls, Roxy state chips, event trace, quick prompts, chat history, session-memory reload, browser text-to-speech, and conversation mode that resumes listening after Roxy finishes speaking.

Siri-style operation is available in Roxy Live with `Wake Roxy`. When active, the browser can keep listening and only sends a prompt after the wake word, for example: "Roxy, resume la oportunidad" or "Roxy, silencio". The browser still controls microphone permission and may pause recognition depending on Chrome/Edge policies.

Session memory is stored locally in `alerts/roxy_conversation_memory.json` when a `session_id` is supplied. The memory is intentionally small, capped by session, and redacts long tokens or key/secret-looking text before writing. Clients can read it through `GET /v1/assist/session/{session_id}`.

User preferences are stored locally in `alerts/roxy_user_profile.json`. Only safe preference fields are allowed: preferred name, language, tone, trading mode, default symbol, watchlist, and browser voice settings. Secrets and unknown keys are ignored.

Feedback learning is stored locally in `alerts/roxy_feedback.json`. Roxy Live can send "Sirvio" or "No sirvio" for the latest answer through `POST /v1/feedback`, and clients can inspect the aggregate with `GET /v1/feedback/summary`. Roxy can summarize this memory when asked what she learned from feedback. When an intent receives negative feedback, the strategy brain marks the next response for that same intent as feedback-adjusted and makes the answer more direct, separating reading, risk, and next step.

## Integration Points

- Visual tab: use `voice_style`, `intent`, `avatar_state`, `emotion`, and `suggested_actions` to animate avatar state, listening state, expression, and recommended buttons.
- Operational tab: consume guarded replies and require confirmation for broker actions.
- Knowledge/strategy tab: feed `alerts/roxy_ai_brief.json`, `alerts/roxy_ai_memory.json`, and future news objects into the brain.
- Local knowledge: Roxy can answer from approved project docs such as `MASTER_CONTEXT.md`, `README.md`, `README_UI.md`, `docs/ai_spec.md`, and this strategy contract.
- Source transparency: clients can call `GET /v1/knowledge/sources` or use the `Fuentes` button in Roxy Live to see which approved local docs are available.
- Visual identity: use `assets/roxy_avatar.jpg` as the source face. Reusable variants are `roxy_avatar_mini.jpg`, `roxy_avatar_icon.jpg`, `roxy_avatar_splash.jpg`, and `roxy_avatar_card.jpg`.

## Near-Term Roadmap

1. Add real-time speech pipeline: browser STT, server reply, browser or provider TTS.
2. Add conversation memory per session without storing secrets.
3. Add live news provider with source timestamps.
4. Add strict action confirmations for trading operations.
5. Add voice persona settings for Spanish female voice selection.
