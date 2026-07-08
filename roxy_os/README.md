# Roxy OS

Roxy OS is the central assistant layer for the project. Roxy Trading is one module inside this larger ecosystem.

This first implementation is intentionally local and dependency-free:

- `RoxyOrchestrator` receives a user command.
- `AgentRouter` detects the intent.
- `ContextEngine` merges page, module, user profile, permissions, symbol and related memories.
- `TaskPlanner` turns the intent into a reviewable execution plan.
- `EventBus` records request lifecycle events for debugging and future automations.
- `PermissionManager` blocks or gates sensitive actions.
- `RoxyMemoryManager` stores durable local memories.
- Specialized agents prepare responses and safe actions.

Example:

```python
from roxy_os import RoxyOrchestrator

roxy = RoxyOrchestrator()
response = roxy.handle(
    "Roxy, acuérdame comprar pan y café",
    user_id="robert",
    context={"page": "Dashboard", "module": "home"},
)
print(response.message)
print(response.data["plan"])
```

Current supported intents:

- Shopping list
- Trading scan preparation
- Weather lookup preparation
- File/folder reading preparation with secret-file blocking
- Screen summary preparation
- Browser action preparation
- Calendar/reminders
- Smart home planning
- Taxes support planning
- Academy routing
- Code agent routing
- Memory recall

Sensitive actions are not executed directly. They are routed with a permission decision so the UI or voice layer can ask for confirmation.

## Streamlit bridge

`streamlit_app.py` exposes a small `Roxy OS Core` expander after login. It is a test bridge for the larger assistant:

- Runs local Roxy OS commands.
- Uses the logged-in user as the memory scope.
- Passes the active page/module/symbol/timeframe to the context engine.
- Shows prepared actions instead of executing sensitive steps.

The next production step is to connect the same `run_roxy_os_command()` bridge to the voice wake-word layer and future screen/browser tooling.

## Local CLI

Use the CLI to test Roxy OS without opening Streamlit or Render:

```bash
PYTHONPATH=. python3 scripts/roxy_os_cli.py "Hola Roxy clima en Miami"
PYTHONPATH=. python3 scripts/roxy_os_cli.py "Roxy abre Bitcoin crypto 2 horas"
PYTHONPATH=. python3 scripts/roxy_os_cli.py "Roxy lee este archivo README.md"
PYTHONPATH=. python3 scripts/roxy_os_cli.py --allow file_read "Roxy lee este archivo README.md"
```

Roxy blocks secret-like files such as `.env`, `.pem`, `.key`, `.p12` and `.p8`.

Weather uses `OPENWEATHER_API_KEY`, `OPEN_WEATHER_API_KEY`, or `ROXY_OPENWEATHER_API_KEY` when available. Without a key, Roxy explains what environment variable is missing instead of failing.
