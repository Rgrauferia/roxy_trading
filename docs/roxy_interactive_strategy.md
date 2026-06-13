# Roxy Interactive Strategy

## Role

Roxy Interactive is the conversation and strategy brain for the assistant. It does not own the visual avatar, the broker execution layer, or the market data pipeline. Its job is to decide what Roxy should say, how cautious she should be, and which next action should be offered.

## Personality Contract

- Voice: feminine, calm, direct, conversational Spanish by default. Roxy Live should prioritize clear young receptionist-style voices such as Paulina, Monica, Flo, Shelley, Samantha, or Ava when the browser provides them, and avoid masculine/heavy voices as automatic defaults.
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

The `Hablar` control also acts as a barge-in control. If Roxy is speaking or still waiting on an assist response, starting a new listening turn records `voice: barge-in`, cancels browser speech synthesis and the active assist HTTP request, then opens the microphone.

Roxy Live applies a client-side timeout to active assist requests. If the service stalls, the browser aborts the request, shows a timeout event, and returns Roxy to a ready state so the user can retry without refreshing the page.

When voice auto-send is off, Roxy Live holds final transcripts as a pending dictation draft. The `Draft` chip shows a truncated preview while Roxy waits for commands such as "Roxy, enviar", "Roxy, borrar", or "Roxy, leer borrador".

Roxy Live also shows a `Heard` chip during microphone capture. Interim transcripts display as `oyendo`, final transcripts display as `final`, and browser confidence is shown when available. This gives the user immediate confirmation of what Roxy heard before the prompt is sent or stored as a draft.

Wake Roxy can read back that local transcript with "Roxy, que escuchaste" / "Roxy, what did you hear". It reads the `Heard` chip title or current text box only, does not create an assistant turn, and helps the user confirm or correct recognition before sending.

When browser speech confidence is available and low, Roxy Live treats the final transcript as a reviewable draft even if voice auto-send is enabled. It speaks a short local warning with the confidence percent and waits for "Roxy, enviar" / "Roxy, send it" before the text reaches the assistant backend. Unknown or unavailable confidence does not block normal voice flow.

When a spoken prompt looks like a direct execution instruction, such as "buy SPY", "sell SPY", "compra SPY", "vende SPY", or "send order", Roxy Live also keeps it as a local draft even when auto-send is enabled. This prevents a raw execution-like phrase from reaching the assistant backend without visible review, and no broker order is sent.

For market regime questions, Roxy uses the `market_summary` intent. It reads local brief fields such as `alert_gate_summary`, `daily_opportunity_plan`, opportunities, and crypto scan candidates to classify the current local read as bullish watch, bearish watch, sideways/wait, or unclear/wait. This is decision support only; it does not execute trades.

For market-session questions such as "sesion de mercado", "horario de mercado", or "market hours", Roxy uses the `market_session` intent. It reads the local `market_session` snapshot from the daily opportunity plan or root brief, explains stock regular/extended/closed status, crypto 24h status, whether stock/options alerts should pause, and ends with a timing-context guardrail. If the snapshot is missing, it asks for a refreshed scan instead of guessing the live market state.

Roxy Live exposes `market_session` through the `Horario` quick prompt, the suggested-action strip, and voice shortcuts such as "Roxy, horario de mercado" / "Roxy, market hours" so users can check timing before interpreting opportunities.

For data freshness prompts such as "frescura de datos" or "source status", Roxy uses the `data_freshness` intent. It reads `daily_opportunity_plan.generated_at`, top-level brief timestamps, or the brief file modified time, then labels the local read as fresh, usable but aging, or stale. Stale data sets `needs_live_source=true` and should force a scan refresh before ranking, sizing, alerts, or trade decisions.

For go/no-go prompts such as "puedo operar ahora" or "should I trade", Roxy uses the `trade_readiness` intent. It combines data freshness, the selected/top-ranked opportunity, entry/stop/risk completeness, readiness, missing confirmations, and action state into `BLOCKED`, `WAIT`, or `PREPARE ONLY`. This is a decision-support gate only and never permission to execute.

When the user asks for an opportunity without naming a symbol, Roxy ranks local rows instead of taking the first file row. Ranking favors actionable signals such as ALERT/BUY/SELL, higher readiness/probability, complete entry/stop/risk data, and penalizes missing confirmations. If the user names a symbol, that symbol still takes priority.

For top-opportunity comparison questions such as "top oportunidades" or "compare opportunities", Roxy uses the `opportunity_compare` intent. It reads the ranked local rows, explains the top three setups with action, decision, readiness, entry, stop, risk, reason, and missing confirmations, then labels the answer as decision support, not execution.

For monitoring-plan prompts such as "plan de monitoreo" or "monitoring plan for SPY", Roxy uses the `monitoring_plan` intent. It picks the named symbol or the current top-ranked local opportunity, then explains what to watch, what invalidates the idea, which confirmations are still missing, and the entry/stop/risk frame. This is a monitoring plan only; checklist and sizing remain separate guarded steps.

For alert-draft prompts such as "prepara alerta" or "set alert for SPY", Roxy uses the `alert_plan` intent. It drafts the alert condition, downgrade/cancel condition, and message from the selected local opportunity. It does not send a notification or create an order; the operational flow must confirm and activate the alert.

For entry, stop, target, and risk questions, Roxy uses the `opportunity_risk` intent. It reads the selected local opportunity from `daily_opportunity_plan`, `opportunities`, or `crypto_scan_candidates` and explains entry, stop, risk percentage, targets, trigger, invalidation, missing checklist items, readiness, probability, and quality. It must end with a no-execution guardrail.

For support/resistance questions such as "soporte y resistencia de SPY" or "support and resistance NVDA", Roxy uses the `support_resistance` intent. It reads local levels from explicit support/resistance fields or scanner fields such as `range_low_60` and `range_high_60`, with safe fallback to stop, entry, and target levels. It explains where price sits relative to the zone and labels the answer as decision support only.

For technical-indicator questions such as "indicadores tecnicos de SPY" or "technical indicators NVDA", Roxy uses the `technical_indicators` intent. It reads local EMA/SMA, VWAP, RSI, MACD, Bollinger, volume, and relative-volume fields from local scan rows, then explains the technical bias in plain Spanish or English. If the snapshot is missing, it asks for a refreshed scan or chart instead of inventing indicator values.

For entry validation questions, Roxy uses the `entry_checklist` intent. It classifies a local opportunity as `READY TO PREPARE`, `WAIT`, or `BLOCKED` based on entry, stop, risk, trigger, readiness, and missing confirmations. Even a ready result remains preparation only; execution requires explicit confirmation in the operational flow.

For position sizing questions, Roxy uses the `position_size` intent. It combines local entry/stop data with account equity supplied in the prompt or local brief account fields, uses an explicit risk percent when provided, otherwise defaults to 0.5% account risk, and returns quantity, notional, and risk used. This is sizing math only and never an execution order.

For executive voice updates, Roxy uses the `daily_briefing` intent. It combines the local market regime, top watch opportunity, entry/stop/risk, missing checklist items, alert count, policy, and generated timestamp into one short speakable briefing in Spanish or English. It is a briefing only, not a trading approval.

For headline analysis, Roxy uses the `news_impact` intent. It can read a pasted headline such as `news impact: ...` / `analiza impacto de noticia: ...`, or the first `news` / `market_news` item in the local brief. The response classifies a conservative tone as bullish, bearish, or neutral, explains likely market impact, asks the user to verify source and timestamp, and refuses to treat the headline as a standalone trade signal. If no headline or local news item exists, Roxy returns `news_impact_unavailable` with `needs_live_source=true`.

For a direct browser experience, run the voice service and open `/roxy-live`. That page provides microphone capture, text fallback, browser voice selection, voice rate/pitch controls, Roxy state chips, event trace, quick prompts, chat history, session-memory reload, browser text-to-speech, and conversation mode that resumes listening after Roxy finishes speaking. The large Roxy avatar is treated as a voice presence: it stays hidden during idle text-only use and appears when the microphone, speech output, Wake Roxy, or conversation mode is active. It also renders `suggested_actions` from each brain response as safe next-step buttons, such as checklist, sizing, monitoring, alert draft, go/no-go, market summary, or session recap.

When a structured response returns `language: "en"` or `language: "es"`, Roxy Live updates its language selector and selects a compatible browser voice before the next listening turn. This keeps browser speech recognition, browser TTS diagnostics, and the inline profile aligned with the language Roxy just used.

Siri-style operation is available in Roxy Live with `Wake Roxy`. When active, the browser can keep listening and only sends a prompt after the wake word, for example: "Roxy, resume la oportunidad" or "Roxy, silencio". The browser still controls microphone permission and may pause recognition depending on Chrome/Edge policies.

Wake Roxy, or a manual `Hablar` turn that includes the wake word, can change listening modes locally without calling the assistant backend. "Roxy, modo Siri" / "Roxy, Siri mode" enables wake-word mode, "Roxy, modo conversación" / "Roxy, conversation mode" enables continuous conversation, and "Roxy, modo manual" disables continuous listening. These mode changes are saved in browser settings and remain decision-support only.

Roxy Live also exposes `Iniciar voz` and the voice command "Roxy, iniciar voz" / "Roxy, start voice session" as a guided local startup. It enables browser speech output, auto-send, conversation mode, and Wake Roxy together, selects the compatible feminine browser voice, and speaks a short safe-start script. This only prepares the local voice loop; it never executes trades or bypasses explicit confirmation.

Wake Roxy also supports local language control commands such as "Roxy, speak English" or "Roxy, habla español". These switch the browser recognition language and compatible voice without calling the assistant backend.

Wake Roxy also supports local conversation controls such as "Roxy, repite" / "Roxy, repeat" for replaying the last answer, "Roxy, silencio" / "Roxy, stop" for stopping microphone/speech, and "Roxy, ayuda" / "Roxy, help" for a short command reminder. These controls run in the browser and return to listening without creating a new assistant turn.

Wake Roxy can adjust browser voice pace locally with "Roxy, voz mas lenta", "Roxy, voz mas rapida", or "Roxy, voz normal" plus English equivalents such as "Roxy, slower voice". These commands update the browser voice-rate control and saved local settings only.

Wake Roxy can also switch output behavior locally. "Roxy, sin voz" / "Roxy, voice off" disables browser speech for later answers, while "Roxy, con voz" / "Roxy, voice on" enables it again. "Roxy, modo dictado" disables auto-send so the transcript can be reviewed before sending, and "Roxy, enviar al terminar" restores auto-send. These are browser settings only and do not create backend assistant turns.

In dictation mode, Wake Roxy keeps the latest voice transcript as a draft instead of sending it immediately. The user can say "Roxy, enviar" / "Roxy, send it" to send the draft, "Roxy, borrar" / "Roxy, clear draft" to discard it, "Roxy, leer borrador" / "Roxy, read draft" to hear the pending text, or "Roxy, corrige borrador ..." / "Roxy, replace draft with ..." to replace a misheard draft locally before it reaches the assistant backend. This makes the voice loop safer for trading prompts because the user can review and correct intent before Roxy answers.

Wake Roxy can read local voice configuration with "Roxy, estado de voz" / "Roxy, voice status". The brief includes listening mode, speech output, auto-send/dictation mode, selected browser voice, default symbol, and watchlist. This is a local diagnostic and does not create a backend assistant turn.

Wake Roxy can apply a clear receptionist-style voice preset with "Roxy, voz clara" / "Roxy, receptionist voice", or through the `Voz clara` button. The preset reselects the best compatible feminine browser voice, restores Roxy's natural speech rate/pitch, turns browser speech back on, saves those local settings, and reads a short confirmation sample. It is only a browser voice profile change.

Wake Roxy can run a broader local system check with "Roxy, diagnostico" / "Roxy, system check", or through the `Diagnostico` button in Roxy Live. This checks `/health`, approved knowledge sources, local learning/feedback status, active session context, and browser voice diagnostics, then reads one concise bilingual-ready summary. It is an operational readiness check only; it does not create a market-assistant turn, send broker instructions, or bypass trade confirmations.

Wake Roxy can also run a local voice sample with "Roxy, prueba tu voz" / "Roxy, test voice", and Roxy Live exposes the same flow through the `Probar voz` button. This uses the currently selected browser voice and speech settings so users can verify clarity before a live conversation.

Wake Roxy can also answer "Roxy, contexto actual" / "Roxy, current context" locally from the active browser turn. It speaks the current symbol, intent/topic, safety level, and next safe actions without calling the assistant backend, giving the user a low-latency orientation check during a live voice session. Full saved-history recaps still use the normal `session_recap` backend intent.

Wake Roxy can answer "Roxy, que sigue" / "Roxy, next step" locally from the active context. It speaks the first safe suggested action, prepares that prompt in the input for review, and refuses to skip explicit confirmation when the last turn was guarded or critical. If a dictation draft is pending, the safe next step is to read, send, or clear the draft first.

Wake Roxy can answer "Roxy, opciones" / "Roxy, options" locally from the active context. It speaks up to three available suggested actions and example wake-word prompts, or draft actions when a dictation draft is pending. This is a local orientation helper only; it does not call the assistant backend or execute anything.

Wake Roxy supports natural follow-ups after an answer. "Roxy, mas corto" / "Roxy, shorter" produces a local concise version of the latest reply without recording negative feedback. "Roxy, mas detalle", "Roxy, pasos", or "Roxy, explicalo simple" / "Roxy, give more detail", "Roxy, steps", or "Roxy, explain simply" expand into a follow-up prompt about the latest query or answer and then follow the normal auto-send or dictation setting.

Wake Roxy can read local learning and source status without sending a market prompt. "Roxy, aprendizaje" / "Roxy, learning status" calls the local learning endpoint, updates the learning/context view, and speaks a short feedback-memory summary. "Roxy, fuentes" / "Roxy, sources" calls the knowledge-source endpoint and speaks how many approved local documents are available.

Wake Roxy, or a manual `Hablar` turn that includes the wake word, can update safe local profile context without calling the assistant backend. "Roxy, símbolo NVDA" / "Roxy, symbol NVDA" updates the default symbol, and "Roxy, watchlist SPY QQQ NVDA" updates the watchlist saved in the browser. Later assistant turns include those values in the normal profile payload; they do not execute trades or change broker state.

Wake Roxy can also update the local trading-mode preference with commands such as "Roxy, modo paper", "Roxy, modo semi auto", or "Roxy, full auto guarded". This only changes the browser profile field sent with later assistant turns; it never places orders and never bypasses the operational confirmation layer.

Wake Roxy can also expand short bilingual market commands into full assistant prompts. Examples include "Roxy, mercado" / "Roxy, market" for market summary, "Roxy, briefing diario" / "Roxy, daily briefing" for an executive spoken update, "Roxy, top oportunidades" / "Roxy, top opportunities" for setup ranking, "Roxy, frescura de datos" / "Roxy, data freshness" for source-age checks, "Roxy, niveles de SPY" / "Roxy, support and resistance SPY" for local support/resistance, "Roxy, indicadores de SPY" / "Roxy, technical indicators SPY" for EMA/RSI/VWAP/MACD/Bollinger/volume reads, "Roxy, plan de monitoreo SPY" / "Roxy, monitoring plan SPY" for what to watch next, "Roxy, prepara alerta SPY" / "Roxy, set alert SPY" for a non-sending alert draft, "Roxy, tamaño de posición SPY capital 10000 riesgo 0.5%" / "Roxy, position size SPY account 10000 risk 0.5%" for sizing math, "Roxy, riesgo de SPY" / "Roxy, risk SPY" for entry-stop-target risk explanation, and "Roxy, puedo operar ahora" / "Roxy, can I trade now" for the trade-readiness gate. When the command includes a symbol from the watchlist, default symbol, or a common stock/crypto ticker such as `SPY`, `NVDA`, or `BTC/USD`, Roxy Live appends it to the expanded prompt. With auto-send on, these shortcuts call the assistant backend and preserve the normal trading safety contract; in dictation mode they stay as a reviewable draft until the user says "Roxy, enviar".

Wake Roxy supports news voice shortcuts as well. "Roxy, noticias" / "Roxy, news" asks for connected/local news, while "Roxy, noticia Tesla sube por resultados" or "Roxy, news impact Nvidia reports revenue" expands into the guarded headline-impact prompt. Roxy must still ask for source, timestamp, confirmation, and price-volume validation before treating a headline as decision support.

In conversation or wake mode, browser microphone errors such as `no-speech` or `aborted` are treated as recoverable. Roxy Live returns the avatar to ready, records a retry event, and schedules listening again instead of blocking the assistant.

Fatal microphone states such as unsupported speech recognition, denied permission, or missing audio capture are handled as blocked voice states. Roxy Live speaks or displays a specific local recovery message, records `voice: mic blocked`, `voice: mic unsupported`, or `voice: mic error`, and keeps the assistant from looping until the user fixes permissions/device and presses `Hablar` again.

Roxy Live suppresses duplicate final speech transcripts that arrive within a short window. This prevents Chrome or Edge from sending the same voice turn twice during continuous conversation or wake-word listening.

Session memory is stored locally in `alerts/roxy_conversation_memory.json` when a `session_id` is supplied. The memory is intentionally small, capped by turns per session and by total recent sessions, and redacts long tokens or key/secret-looking text before writing. Clients can read it through `GET /v1/assist/session/{session_id}`.

The session response includes `active_context`, a compact handoff for UI and operations clients. It exposes the active intent, active symbol, latest topic, confirmation requirement, and safe `next_best_actions` without requiring a client to parse full transcript history. Roxy Live displays this as the `Context` chip and reuses `next_best_actions` for suggested action buttons. Lightweight clients can call `GET /v1/assist/context/{session_id}` when they need only this compact context and not the recent transcript.

Voice and mobile clients can call `GET /v1/assist/session/{session_id}/brief?language=es|en` for a compact speakable session brief. It returns `speakable_summary`, `active_context`, and `suggested_actions` without returning full `recent_turns`, so clients can orient the user quickly without exposing long conversation history.

Roxy Live also refreshes the `Context` chip after every state or streamed reply using the current turn intent, detected symbol, safety level, and suggested actions. This keeps voice users oriented during a live conversation without requiring a manual memory reload.

When session memory is available, Roxy can resolve short follow-ups such as "por que?", "dame el plan", "continue", or "why?" against the last meaningful topic. For opportunity conversations this can produce `opportunity_reason` or `opportunity_risk` without forcing the user to repeat the symbol, which makes voice conversation feel closer to a natural assistant.

For session recap prompts such as "resumen de sesion" or "conversation recap", Roxy uses the `session_recap` intent. It summarizes the recent saved turns for the active `session_id`, main intents, last topic, and a safe next step. It does not expose long raw history and relies on the existing local redaction used by conversation memory.

User preferences are stored locally in `alerts/roxy_user_profile.json`. Only safe preference fields are allowed: preferred name, language, tone, trading mode, default symbol, watchlist, and browser voice settings. Language is normalized to `es` or `en`. Secrets and unknown keys are ignored.

Voice clients may also include an optional `profile` object in `POST /v1/assist`, `POST /v1/assist/state`, or `POST /v1/assist/stream`. Roxy persists those safe fields before generating the reply, so the visible Roxy Live controls immediately influence language, default symbol, watchlist, trading mode, and voice behavior even before a manual profile save.

For profile-based monitoring, Roxy uses the `watchlist_summary` intent. It reads the saved watchlist and local opportunity rows, summarizes action, decision, readiness, entry, stop, risk, and missing confirmations for each matching symbol, and clearly labels symbols with no local row instead of inventing data.

Feedback learning is stored locally in `alerts/roxy_feedback.json`. Roxy Live can send "Sirvio" or "No sirvio" for the latest answer through `POST /v1/feedback`, including an optional correction note such as "mas corto" or "mas claro". Clients can inspect the aggregate with `GET /v1/feedback/summary`. Roxy can summarize this memory when asked what she learned from feedback. When an intent receives negative feedback, the strategy brain marks the next response for that same intent as feedback-adjusted and makes the answer more direct, separating reading, risk, and next step.

Wake Roxy can also capture feedback by voice. "Roxy, sirvió" records positive feedback for the latest answer. "Roxy, no sirvió, más corto" / "Roxy, bad answer, be shorter" records negative feedback with the spoken correction note, confirms by voice, and does not create a new assistant market turn.

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
