__all__ = ["RoxyOrchestrator", "RoxyRequest", "RoxyResponse"]


def __getattr__(name: str):
    """Load the full Roxy brain only when requested.

    Lightweight services such as Roxy Home can reuse one core store without
    importing trading, email, document, weather, and voice dependencies.
    """

    if name == "RoxyOrchestrator":
        from .core.orchestrator import RoxyOrchestrator

        return RoxyOrchestrator
    if name in {"RoxyRequest", "RoxyResponse"}:
        from .models import RoxyRequest, RoxyResponse

        return {"RoxyRequest": RoxyRequest, "RoxyResponse": RoxyResponse}[name]
    raise AttributeError(name)
