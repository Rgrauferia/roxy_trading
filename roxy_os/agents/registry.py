from __future__ import annotations

from roxy_os.agents.simple_agents import (
    AcademyAgent,
    BrowserAgent,
    CalendarAgent,
    CodeAgent,
    DocumentsAgent,
    EmailAgent,
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
from roxy_os.personal_tasks import PersonalTaskStore
from roxy_os.shopping_list import ShoppingListStore
from roxy_os.document_vault import DocumentVault


def build_default_agents(
    memory: RoxyMemoryManager,
    router: AgentRouter,
    personal_tasks: PersonalTaskStore | None = None,
    shopping_list: ShoppingListStore | None = None,
    document_vault: DocumentVault | None = None,
) -> dict[str, object]:
    return {
        "academy": AcademyAgent(memory),
        "browser": BrowserAgent(memory),
        "calendar": CalendarAgent(memory, personal_tasks),
        "code": CodeAgent(memory),
        "documents": DocumentsAgent(memory, document_vault),
        "email": EmailAgent(memory),
        "general": GeneralAgent(memory),
        "home": HomeAgent(memory),
        "memory": MemoryAgent(memory),
        "reader": ReaderAgent(memory),
        "screen": ScreenAgent(memory),
        "shopping": ShoppingAgent(memory, router, shopping_list),
        "taxes": TaxesAgent(memory),
        "trader": TraderAgent(memory),
        "weather": WeatherAgent(memory),
    }
