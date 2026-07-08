# Roxy OS Architecture Plan

## Vision

Roxy OS is the central assistant ecosystem around Roxy. Roxy Trading becomes one app inside this larger system, not the whole product.

The goal is that the user can sit in front of the computer or use the phone and say "Hola Roxy". Roxy wakes up, understands the user, sees authorized context, listens, speaks, remembers, opens apps, reads screens, controls smart home devices, manages reminders and helps with trading, learning, taxes, documents and daily life.

Roxy must feel like one assistant with one memory, one voice and many specialized abilities.

## Core Principle

Do not create separate Roxys.

Create:

- One Roxy Core.
- One memory layer.
- One permission system.
- Many agents.
- Many devices.
- Many applications.

## High-Level Architecture

```text
User voice / text / touch / camera / screen
        |
        v
Roxy Input Layer
  - Wake word
  - Microphone
  - Camera
  - Screen capture
  - Mobile app
  - Web app
        |
        v
Roxy Core
  - Orchestrator
  - Context Engine
  - Agent Router
  - Permission Manager
  - Task Planner
  - Event Bus
        |
        v
Specialized Agents
  - Roxy General
  - Roxy Screen
  - Roxy Browser
  - Roxy Trading
  - Roxy Academy
  - Roxy Home
  - Roxy Calendar
  - Roxy Shopping
  - Roxy Taxes
  - Roxy Code
  - Roxy Memory
        |
        v
Tools and Integrations
  - Browser automation
  - Desktop automation
  - Home Assistant
  - Calendar
  - Reminders
  - Knowledge base
  - Market data APIs
  - Trading charts
  - ElevenLabs voice
  - OCR / vision models
  - Terminal agent
```

## Proposed Project Structure

```text
roxy_trading/
├── streamlit_app.py
├── roxy_os/
│   ├── core/
│   │   ├── orchestrator.py
│   │   ├── context_engine.py
│   │   ├── agent_router.py
│   │   ├── task_planner.py
│   │   └── event_bus.py
│   ├── memory/
│   │   ├── memory_manager.py
│   │   ├── memory_store.py
│   │   └── schemas.py
│   ├── permissions/
│   │   ├── permission_manager.py
│   │   └── policies.py
│   ├── agents/
│   │   ├── general_agent.py
│   │   ├── voice_agent.py
│   │   ├── screen_agent.py
│   │   ├── browser_agent.py
│   │   ├── trader_agent.py
│   │   ├── academy_agent.py
│   │   ├── home_agent.py
│   │   ├── calendar_agent.py
│   │   ├── shopping_agent.py
│   │   ├── taxes_agent.py
│   │   ├── code_agent.py
│   │   └── memory_agent.py
│   ├── tools/
│   │   ├── browser_tools.py
│   │   ├── screen_tools.py
│   │   ├── home_tools.py
│   │   ├── calendar_tools.py
│   │   ├── shopping_tools.py
│   │   ├── trading_tools.py
│   │   └── code_tools.py
│   └── api/
│       ├── chat.py
│       ├── voice.py
│       ├── memory.py
│       ├── actions.py
│       └── permissions.py
├── knowledge/
├── roxy-terminal-agent/
├── roxy-self-improvement/
└── docs/
```

## Main Modules

### 1. Roxy Core

Roxy Core is the brain. It receives every user request and decides what should happen.

Responsibilities:

- Understand user intent.
- Detect current context.
- Route the request to the right agent.
- Check permissions before actions.
- Keep global task state.
- Log important actions.
- Save useful memories.

Example:

```text
"Roxy, abre Google y busca eventos este mes"
        |
Roxy Core detects:
  intent = browser_search + calendar_context
  agents = Browser Agent + Calendar Agent
  risk = low
  permission = browser allowed
```

### 2. Roxy Memory

One central memory for everything:

- User profile.
- Preferred language.
- Trading preferences.
- Risk tolerance.
- Watchlist.
- Calendar preferences.
- Shopping list.
- Home devices.
- Learning progress.
- Projects.
- Personal routines.
- Important context from conversations.

Memory types:

- `semantic`: facts and preferences.
- `episodic`: events and conversations.
- `procedural`: how the user likes tasks done.
- `project`: project-specific knowledge.
- `visual`: things seen in screenshots/images.
- `trading`: strategies, signals, outcomes and lessons.
- `academy`: learning progress and weak areas.

Initial implementation:

- Local JSON/SQLite for fast development.

Production implementation:

- PostgreSQL + pgvector.
- Redis for short-term session memory.

### 3. Roxy Voice

Voice is the natural entry point.

Required capabilities:

- Wake phrase: "Hola Roxy".
- Listen after wake.
- Speech-to-text.
- Roxy response by voice.
- Interruptions.
- Spanish and English.
- User name personalization.

Flow:

```text
Wake word detected
  -> Start listening
  -> Transcribe user speech
  -> Send to Roxy Core
  -> Execute or answer
  -> Speak response
```

### 4. Roxy Vision

Roxy Vision lets Roxy see the user and the environment with permission.

Levels:

- Level 1: user sends image or screenshot.
- Level 2: user activates camera/screen during a session.
- Level 3: always-on environment mode, only with explicit authorization.

Use cases:

- "Roxy, dime qué ves en mi pantalla."
- "Roxy, léeme este artículo."
- "Roxy, mira este error."
- "Roxy, mira este producto."
- "Roxy, qué tengo abierto."

### 5. Roxy Screen Agent

This agent understands and acts on the computer screen.

Capabilities:

- Screenshot.
- OCR.
- Detect text, buttons and UI regions.
- Summarize current screen.
- Read article/page.
- Copy visible code.
- Fill forms with permission.
- Click buttons with permission.
- Open apps/websites.

Sensitive actions require confirmation:

- Delete files.
- Send email.
- Submit legal/tax forms.
- Make purchases.
- Change account settings.
- Execute real trades.

### 6. Roxy Browser Agent

Browser automation for web tasks.

Examples:

- "Roxy, abre Google y busca esta información."
- "Roxy, abre Roxy Trading."
- "Roxy, léeme este artículo."
- "Roxy, compara estas opciones."
- "Roxy, busca los eventos económicos de este mes."

### 7. Roxy Trading

Roxy Trading remains a full trading module inside Roxy OS.

Responsibilities:

- Open Roxy Trading.
- Analyze market opportunities.
- Show live charts.
- Explain why a signal exists.
- Track watchlist.
- Connect to knowledge base.
- Track strategy performance.
- Support paper trading.
- Never place real-money trades without explicit user confirmation.

Example:

```text
"Roxy, abre Roxy Trading y dime las mejores oportunidades"
  -> Browser Agent opens app
  -> Trader Agent scans assets
  -> Memory loads user risk profile
  -> Roxy explains top opportunities
```

### 8. Roxy Academy

The learning system.

Responsibilities:

- Planet-based lessons.
- Interactive exercises.
- Personalized learning path.
- Use trading knowledge base.
- Teach concepts before strategies.
- Adapt to user progress.

Roxy Academy should use Roxy Memory so it knows what the user already understands.

### 9. Roxy Home

Roxy Home controls smart home devices through a controlled hub.

Recommended integration:

- Home Assistant as the central smart home bridge.

Possible devices:

- Thermostat.
- Lights.
- Cameras.
- TV volume.
- Speakers.
- Motion sensors.
- Door/window sensors.
- Plugs.

Commands:

- "Roxy, baja la temperatura."
- "Roxy, sube el volumen del televisor."
- "Roxy, muéstrame la cámara de la entrada."
- "Roxy, apaga las luces."
- "Roxy, crea una escena para dormir."

Safety:

- Camera access must be explicit.
- Door locks/security actions require confirmation.
- Roxy should log device actions.

### 10. Roxy Calendar and Reminders

Roxy should manage life context.

Examples:

- "Roxy, qué eventos tengo este mes."
- "Roxy, recuérdame pagar esto mañana."
- "Roxy, agenda una cita."
- "Roxy, qué tengo hoy."

Data:

- Calendar events.
- Reminders.
- Tasks.
- Due dates.
- Recurring routines.

### 11. Roxy Shopping

Personal shopping assistant.

Examples:

- "Roxy, recuérdame comprar pan, café y leche."
- "Roxy, qué necesito comprar."
- "Roxy, agrega esto a la lista de la casa."
- "Roxy, estoy en la tienda, qué faltaba."

Memory:

- Household staples.
- Frequent purchases.
- Store-specific lists.
- Budget preferences.

### 12. Roxy Taxes

Tax assistant for workflow support.

Capabilities:

- Organize client documents.
- Ask missing-information questions.
- Summarize possible deductions.
- Explain options.
- Compare filing scenarios.
- Prepare checklists.

Important boundary:

Roxy can assist, organize and explain. It must not claim to be a CPA or guarantee tax outcomes. High-stakes filing decisions should be reviewed by a qualified professional.

### 13. Roxy Code

Code assistant for this project.

Existing base:

- `roxy-terminal-agent/`
- `roxy-self-improvement/`

Capabilities:

- Read project files.
- Propose fixes.
- Edit safe files.
- Run tests.
- Run lint/build.
- Generate reports.
- Ask confirmation before deploy/push/destructive actions.

## Permission Modes

Every agent must run under one permission mode.

### read_only

Roxy can read and explain only.

### ask_before_action

Roxy can propose actions but must ask before executing.

### autopilot_safe

Roxy can perform low-risk actions without asking.

Examples:

- Open Roxy Trading.
- Search the web.
- Add a reminder.
- Update a shopping list.
- Start paper-trading analysis.

### autopilot_full

Only for explicitly approved workflows.

Never allowed without confirmation:

- Real-money trading.
- Sending money.
- Signing documents.
- Submitting tax/legal forms.
- Sending important emails.
- Deleting files.
- Changing security settings.
- Unlocking doors.

## First MVP

The first MVP should focus on making Roxy feel alive and useful without overbuilding.

### MVP Goal

User says:

"Hola Roxy, dime qué estoy viendo en la pantalla."

Roxy should:

1. Wake up.
2. Capture screen with permission.
3. Summarize the screen.
4. Speak the response.
5. Offer next actions.

Second core command:

"Roxy, abre Roxy Trading y dime las mejores oportunidades."

Roxy should:

1. Open Roxy Trading.
2. Read current user profile.
3. Trigger trading scan.
4. Show best opportunities.
5. Explain risk and reasoning.

Third core command:

"Roxy, acuérdame comprar pan y café."

Roxy should:

1. Save shopping-list memory.
2. Confirm by voice.
3. Retrieve it later on request.

## Development Phases

### Phase 1: Roxy Core Skeleton

Build:

- `roxy_os/core/orchestrator.py`
- `roxy_os/core/agent_router.py`
- `roxy_os/memory/memory_manager.py`
- `roxy_os/permissions/permission_manager.py`

Capabilities:

- Receive text command.
- Detect intent.
- Route to agent.
- Save simple memories.
- Enforce safety mode.

### Phase 2: Voice Wake Flow

Build:

- Wake word listener.
- Voice input.
- Voice output.
- Connection to Roxy Core.

Initial commands:

- "Hola Roxy."
- "Qué puedes hacer."
- "Guarda esto en memoria."
- "Abre Roxy Trading."

### Phase 3: Screen Read Mode

Build:

- Screenshot permission flow.
- OCR/screen summary.
- "Read my screen" command.
- "Read this article" command.

No clicking yet. Read-only first.

### Phase 4: Browser Action Mode

Build:

- Open browser.
- Search Google.
- Open Roxy Trading.
- Navigate pages.
- Summarize page.

Actions are low-risk but logged.

### Phase 5: Trading Integration

Connect Roxy Core to existing trading functions.

Roxy should answer:

- Best opportunities now.
- Why this signal.
- What risk.
- What chart confirms.
- What not to trade.

### Phase 6: Calendar and Shopping

Build:

- Reminder memory.
- Shopping list memory.
- Monthly event summary.
- Mobile-friendly commands.

### Phase 7: Roxy Home

Use Home Assistant.

Start with:

- Read device status.
- Control one test light or virtual device.
- Control thermostat later.
- Cameras only after explicit permission.

### Phase 8: Taxes Workflow

Build:

- Client checklist.
- Document intake.
- Missing-info detector.
- Deduction explanation helper.
- Scenario notes.

### Phase 9: Mobile App

Eventually:

- React Native or Expo.
- Voice.
- Camera.
- Reminders.
- Shopping.
- Roxy Home.
- Push notifications.

## Data Model

Core tables/entities:

- users
- user_profiles
- memories
- conversations
- messages
- agents
- permissions
- tasks
- actions
- reminders
- shopping_items
- screen_sessions
- home_devices
- trading_sessions
- academy_progress
- tax_clients

## Immediate Next Step

Create the actual `roxy_os` package with the first working loop:

```python
result = RoxyOrchestrator().handle(
    user_id="local_user",
    text="Roxy, acuérdame comprar pan y café",
    context={"surface": "desktop"}
)
```

Expected behavior:

- Router detects `shopping/reminder`.
- Permission system approves safe memory write.
- Memory manager saves the item.
- Roxy returns a spoken/text response.

Then connect this loop to the current app.

## Success Criteria

Roxy OS is working when:

- Roxy has one memory across modules.
- Roxy can be activated by voice.
- Roxy can understand the current page/screen.
- Roxy can open Roxy Trading.
- Roxy can save and recall reminders.
- Roxy can explain what she is doing.
- Roxy asks before sensitive actions.
- Roxy Trading remains intact as one module inside the ecosystem.
