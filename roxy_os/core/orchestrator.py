from __future__ import annotations

from pathlib import Path
from typing import Any

from roxy_os.agents import build_default_agents
from roxy_os.context import ContextEngine
from roxy_os.core.agent_router import AgentRouter
from roxy_os.events import EventBus
from roxy_os.memory import RoxyMemoryManager
from roxy_os.models import AgentResult, RoxyRequest, RoxyResponse
from roxy_os.permissions import PermissionManager
from roxy_os.planning import TaskPlanner


class RoxyOrchestrator:
    def __init__(
        self,
        *,
        memory_path: str | Path = "data/roxy_os_memory.json",
        memory: RoxyMemoryManager | None = None,
        permission_manager: PermissionManager | None = None,
        router: AgentRouter | None = None,
        context_engine: ContextEngine | None = None,
        event_bus: EventBus | None = None,
        task_planner: TaskPlanner | None = None,
    ) -> None:
        self.memory = memory or RoxyMemoryManager(memory_path)
        self.permission_manager = permission_manager or PermissionManager()
        self.router = router or AgentRouter()
        self.context_engine = context_engine or ContextEngine(self.memory)
        self.event_bus = event_bus or EventBus()
        self.task_planner = task_planner or TaskPlanner()
        self.agents = build_default_agents(self.memory, self.router)

    def handle(self, text: str, *, user_id: str = "local_user", context: dict[str, Any] | None = None) -> RoxyResponse:
        enriched_context = self.context_engine.build(user_id=user_id, raw_context=context or {})
        request = RoxyRequest(text=text, user_id=user_id, context=enriched_context)
        intent, agent_name = self.router.route(request.text)
        permission = self.permission_manager.decide(intent=intent, text=request.text, context=request.context)
        plan = self.task_planner.create_plan(intent=intent, agent=agent_name, text=request.text, context=request.context)
        self.event_bus.publish(
            "request_received",
            {"request_id": request.request_id, "user_id": request.user_id, "intent": intent, "agent": agent_name},
        )

        if not permission.allowed:
            self._record_event(request, intent, agent_name, "blocked", {"reason": permission.reason})
            self.event_bus.publish(
                "request_blocked",
                {"request_id": request.request_id, "intent": intent, "reason": permission.reason},
            )
            return RoxyResponse(
                request_id=request.request_id,
                user_id=request.user_id,
                intent=intent,
                agent=agent_name,
                message=f"No voy a ejecutar eso automaticamente. {permission.reason}",
                data={"blocked": True, "plan": plan, "context": enriched_context},
                permission=permission,
            )

        agent = self.agents.get(agent_name) or self.agents["general"]
        result: AgentResult = agent.handle(request, intent=intent, permission_mode=permission.mode)
        self._record_event(request, intent, agent_name, "handled", {"message": result.message})
        self.event_bus.publish(
            "request_handled",
            {"request_id": request.request_id, "intent": result.intent, "agent": result.agent},
        )
        data = dict(result.data)
        data.setdefault("plan", plan)
        data.setdefault("context", enriched_context)
        data.setdefault("events", self.event_bus.recent(limit=5))

        return RoxyResponse(
            request_id=request.request_id,
            user_id=request.user_id,
            intent=result.intent,
            agent=result.agent,
            message=result.message,
            data=data,
            actions=result.actions,
            permission=permission,
        )

    def _record_event(
        self,
        request: RoxyRequest,
        intent: str,
        agent_name: str,
        status: str,
        metadata: dict[str, Any],
    ) -> None:
        self.memory.remember(
            user_id=request.user_id,
            memory_type="episodic",
            title=f"{agent_name}:{intent}:{status}",
            content=request.text,
            source="roxy_os_orchestrator",
            tags=["roxy_os", agent_name, intent, status],
            importance=2,
            metadata={"request_id": request.request_id, **metadata},
        )
