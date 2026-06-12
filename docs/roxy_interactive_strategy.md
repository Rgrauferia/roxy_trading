# Roxy Interactive Strategy

## Role

Roxy Interactive is the conversation and strategy brain for the assistant. It does not own the visual avatar, the broker execution layer, or the market data pipeline. Its job is to decide what Roxy should say, how cautious she should be, and which next action should be offered.

## Personality Contract

- Voice: feminine, calm, direct, conversational Spanish by default.
- Languages: Spanish and English are supported. Roxy detects the prompt language, can honor the saved profile language, and returns a `language` field so voice clients choose the right speech engine.
- Identity: professional synthetic assistant for Grau Service LLC / Roxy Trading.
- Style: explain first, recommend with context, avoid hype, avoid guaranteed outcomes.
- Trading safety: never imply certainty, never execute or approve sensitive actions without explicit user confirmation.
- News safety: if no live news source is connected, Roxy must say that instead of inventing headlines.
- News impact safety: Roxy can analyze a pasted headline or local brief item, but she must label it as decision support and ask for source, timestamp, and price-volume confirmation.
- Action safety: spoken commands like "buy now" or "send order" produce `action_confirmation_required`, not execution.

## Module Boundary

The strategy layer lives in `tools/roxy_interactive_brain.py`.

It returns a `RoxyBrainReply` object with:

- `reply`: speakable text.
- `intent`: detected user intent.
- `language`: `es` or `en`.
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

Every structured `POST /v1/assist/state` response includes `turn_id`, `server_latency_ms`, and `response_source`. Roxy Live displays the latency chip so voice work can watch response speed while preserving the same safety contract.

For lower-latency clients, `POST /v1/assist/stream` returns Server-Sent Events in order: `transcript_received`, `thinking`, `reply_ready`, optional `speak`, and `done`. This lets the visual avatar react immediately while the brain prepares the final answer. Roxy Live attempts this stream first and falls back to `POST /v1/assist/state` if browser streaming is unavailable.

The `Parar` control in Roxy Live cancels microphone listening, speech synthesis, and the active assist HTTP request through `AbortController`. Starting a new prompt also aborts any previous unfinished assist turn so late responses cannot overwrite the current conversation state.

The `Hablar` control also acts as a barge-in control. If Roxy is speaking or still waiting on an assist response, starting a new listening turn cancels browser speech synthesis and the active assist HTTP request before opening the microphone.

Roxy Live applies a client-side timeout to active assist requests. If the service stalls, the browser aborts the request, shows a timeout event, and returns Roxy to a ready state so the user can retry without refreshing the page.

For market regime questions, Roxy uses the `market_summary` intent. It reads local brief fields such as `alert_gate_summary`, `daily_opportunity_plan`, opportunities, and crypto scan candidates to classify the current local read as bullish watch, bearish watch, sideways/wait, or unclear/wait. This is decision support only; it does not execute trades.

For data freshness prompts such as "frescura de datos" or "source status", Roxy uses the `data_freshness` intent. It reads `daily_opportunity_plan.generated_at`, top-level brief timestamps, or the brief file modified time, then labels the local read as fresh, usable but aging, or stale. Stale data sets `needs_live_source=true` and should force a scan refresh before ranking, sizing, alerts, or trade decisions.

For go/no-go prompts such as "puedo operar ahora" or "should I trade", Roxy uses the `trade_readiness` intent. It combines data freshness, the selected/top-ranked opportunity, entry/stop/risk completeness, readiness, missing confirmations, and action state into `BLOCKED`, `WAIT`, or `PREPARE ONLY`. This is a decision-support gate only and never permission to execute.

When the user asks for an opportunity without naming a symbol, Roxy ranks local rows instead of taking the first file row. Ranking favors actionable signals such as ALERT/BUY/SELL, higher readiness/probability, complete entry/stop/risk data, and penalizes missing confirmations. If the user names a symbol, that symbol still takes priority.

For top-opportunity comparison questions such as "top oportunidades" or "compare opportunities", Roxy uses the `opportunity_compare` intent. It reads the ranked local rows, explains the top three setups with action, decision, readiness, entry, stop, risk, reason, and missing confirmations, then labels the answer as decision support, not execution.

For monitoring-plan prompts such as "plan de monitoreo" or "monitoring plan for SPY", Roxy uses the `monitoring_plan` intent. It picks the named symbol or the current top-ranked local opportunity, then explains what to watch, what invalidates the idea, which confirmations are still missing, and the entry/stop/risk frame. This is a monitoring plan only; checklist and sizing remain separate guarded steps.

For alert-draft prompts such as "prepara alerta" or "set alert for SPY", Roxy uses the `alert_plan` intent. It drafts the alert condition, downgrade/cancel condition, and message from the selected local opportunity. It does not send a notification or create an order; the operational flow must confirm and activate the alert.

For entry, stop, target, and risk questions, Roxy uses the `opportunity_risk` intent. It reads the selected local opportunity from `daily_opportunity_plan`, `opportunities`, or `crypto_scan_candidates` and explains entry, stop, risk percentage, targets, trigger, invalidation, missing checklist items, readiness, probability, and quality. It must end with a no-execution guardrail.

For entry validation questions, Roxy uses the `entry_checklist` intent. It classifies a local opportunity as `READY TO PREPARE`, `WAIT`, or `BLOCKED` based on entry, stop, risk, trigger, readiness, and missing confirmations. Even a ready result remains preparation only; execution requires explicit confirmation in the operational flow.

For position sizing questions, Roxy uses the `position_size` intent. It combines local entry/stop data with account equity supplied in the prompt or local brief account fields, uses an explicit risk percent when provided, otherwise defaults to 0.5% account risk, and returns quantity, notional, and risk used. This is sizing math only and never an execution order.

For executive voice updates, Roxy uses the `daily_briefing` intent. It combines the local market regime, top watch opportunity, entry/stop/risk, missing checklist items, alert count, policy, and generated timestamp into one short speakable briefing in Spanish or English. It is a briefing only, not a trading approval.

For headline analysis, Roxy uses the `news_impact` intent. It can read a pasted headline such as `news impact: ...` / `analiza impacto de noticia: ...`, or the first `news` / `market_news` item in the local brief. The response classifies a conservative tone as bullish, bearish, or neutral, explains likely market impact, asks the user to verify source and timestamp, and refuses to treat the headline as a standalone trade signal. If no headline or local news item exists, Roxy returns `news_impact_unavailable` with `needs_live_source=true`.

For a direct browser experience, run the voice service and open `/roxy-live`. That page provides microphone capture, text fallback, Roxy avatar, browser voice selection, voice rate/pitch controls, Roxy state chips, event trace, quick prompts, chat history, session-memory reload, browser text-to-speech, and conversation mode that resumes listening after Roxy finishes speaking. It also renders `suggested_actions` from each brain response as safe next-step buttons, such as checklist, sizing, monitoring, alert draft, go/no-go, market summary, or session recap.

When a structured response returns `language: "en"` or `language: "es"`, Roxy Live updates its language selector and selects a compatible browser voice before the next listening turn. This keeps browser speech recognition, browser TTS diagnostics, and the inline profile aligned with the language Roxy just used.

Siri-style operation is available in Roxy Live with `Wake Roxy`. When active, the browser can keep listening and only sends a prompt after the wake word, for example: "Roxy, resume la oportunidad" or "Roxy, silencio". The browser still controls microphone permission and may pause recognition depending on Chrome/Edge policies.

In conversation or wake mode, browser microphone errors such as `no-speech` or `aborted` are treated as recoverable. Roxy Live returns the avatar to ready, records a retry event, and schedules listening again instead of blocking the assistant.

Roxy Live suppresses duplicate final speech transcripts that arrive within a short window. This prevents Chrome or Edge from sending the same voice turn twice during continuous conversation or wake-word listening.

Session memory is stored locally in `alerts/roxy_conversation_memory.json` when a `session_id` is supplied. The memory is intentionally small, capped by turns per session and by total recent sessions, and redacts long tokens or key/secret-looking text before writing. Clients can read it through `GET /v1/assist/session/{session_id}`.

The session response includes `active_context`, a compact handoff for UI and operations clients. It exposes the active intent, active symbol, latest topic, confirmation requirement, and safe `next_best_actions` without requiring a client to parse full transcript history. Roxy Live displays this as the `Context` chip and reuses `next_best_actions` for suggested action buttons. Lightweight clients can call `GET /v1/assist/context/{session_id}` when they need only this compact context and not the recent transcript.

Roxy Live also refreshes the `Context` chip after every state or streamed reply using the current turn intent, detected symbol, safety level, and suggested actions. This keeps voice users oriented during a live conversation without requiring a manual memory reload.

When session memory is available, Roxy can resolve short follow-ups such as "por que?", "dame el plan", "continue", or "why?" against the last meaningful topic. For opportunity conversations this can produce `opportunity_reason` or `opportunity_risk` without forcing the user to repeat the symbol, which makes voice conversation feel closer to a natural assistant.

For session recap prompts such as "resumen de sesion" or "conversation recap", Roxy uses the `session_recap` intent. It summarizes the recent saved turns for the active `session_id`, main intents, last topic, and a safe next step. It does not expose long raw history and relies on the existing local redaction used by conversation memory.

User preferences are stored locally in `alerts/roxy_user_profile.json`. Only safe preference fields are allowed: preferred name, language, tone, trading mode, default symbol, watchlist, and browser voice settings. Language is normalized to `es` or `en`. Secrets and unknown keys are ignored.

Voice clients may also include an optional `profile` object in `POST /v1/assist`, `POST /v1/assist/state`, or `POST /v1/assist/stream`. Roxy persists those safe fields before generating the reply, so the visible Roxy Live controls immediately influence language, default symbol, watchlist, trading mode, and voice behavior even before a manual profile save.

For profile-based monitoring, Roxy uses the `watchlist_summary` intent. It reads the saved watchlist and local opportunity rows, summarizes action, decision, readiness, entry, stop, risk, and missing confirmations for each matching symbol, and clearly labels symbols with no local row instead of inventing data.

Feedback learning is stored locally in `alerts/roxy_feedback.json`. Roxy Live can send "Sirvio" or "No sirvio" for the latest answer through `POST /v1/feedback`, including an optional correction note such as "mas corto" or "mas claro". Clients can inspect the aggregate with `GET /v1/feedback/summary`. Roxy can summarize this memory when asked what she learned from feedback. When an intent receives negative feedback, the strategy brain marks the next response for that same intent as feedback-adjusted and makes the answer more direct, separating reading, risk, and next step.

The full local learning state is available through `GET /v1/learning/status`. It combines safe user profile fields, session memory, feedback counts, approved knowledge sources, and recommendations. Roxy Live exposes it with the `Aprendizaje` button so the assistant can explain what she is improving without needing a broker connection or external LLM.

Roxy also understands operational status prompts such as "estado", "estado de Roxy", or "modo autonomo". These return the `autonomy_status` intent with voice readiness, session memory, feedback count, and next recommended action. The word "estado" is explicitly excluded from ticker detection so a status check cannot become a fake symbol lookup.

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
