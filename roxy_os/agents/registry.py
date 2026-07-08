from __future__ import annotations

from roxy_os.agents.simple_agents import (
    AcademyAgent,
    BrowserAgent,
    CalendarAgent,
    CodeAgent,
    GeneralAgent,
    HomeAgent,
    MemoryAgent,
    ReaderAgent,
    ScreenAgent,
    ShoppingAgent,
    TaxesAgent,
    TraderAgent,
    WeatherAgent,
)
from roxy_os.core.agent_router import AgentRouter
from roxy_os.memory.memory_manager import RoxyMemoryManager


def build_default_agents(memory: RoxyMemoryManager, router: AgentRouter) -> dict[str, object]:
    return {
        "academy": AcademyAgent(memory),
        "browser": BrowserAgent(memory),
        "calendar": CalendarAgent(memory),
        "code": CodeAgent(memory),
        "general": GeneralAgent(memory),
        "home": HomeAgent(memory),
        "memory": MemoryAgent(memory),
        "reader": ReaderAgent(memory),
        "screen": ScreenAgent(memory),
        "shopping": ShoppingAgent(memory, router),
        "taxes": TaxesAgent(memory),
        "trader": TraderAgent(memory),
        "weather": WeatherAgent(memory),
    }
