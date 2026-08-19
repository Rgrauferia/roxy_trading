from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


class HomeAIConfigurationError(RuntimeError):
    pass


class HomeAIBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class HomeAIConfig:
    api_key: str
    routine_model: str = "gpt-5.6-luna"
    deep_model: str = "gpt-5.6-terra"
    memory_path: str = "data/roxy_home_food.json"
    budget_path: str = "data/roxy_home_ai_budget.json"
    daily_request_limit: int = 100
    daily_output_token_limit: int = 100_000
    max_output_tokens: int = 4_000

    @classmethod
    def from_env(cls) -> "HomeAIConfig":
        # Deliberately do not fall back to OPENAI_API_KEY or any Study secret.
        api_key = str(os.getenv("ROXY_HOME_OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise HomeAIConfigurationError("Falta ROXY_HOME_OPENAI_API_KEY para Roxy Home.")

        def positive_int(name: str, default: int) -> int:
            try:
                value = int(str(os.getenv(name) or default))
            except ValueError as exc:
                raise HomeAIConfigurationError(f"{name} debe ser un entero.") from exc
            if value <= 0:
                raise HomeAIConfigurationError(f"{name} debe ser mayor que cero.")
            return value

        return cls(
            api_key=api_key,
            routine_model=str(os.getenv("ROXY_HOME_OPENAI_ROUTINE_MODEL") or "gpt-5.6-luna").strip(),
            deep_model=str(os.getenv("ROXY_HOME_OPENAI_DEEP_MODEL") or "gpt-5.6-terra").strip(),
            memory_path=str(os.getenv("ROXY_HOME_MEMORY_PATH") or "data/roxy_home_food.json"),
            budget_path=str(os.getenv("ROXY_HOME_AI_BUDGET_PATH") or "data/roxy_home_ai_budget.json"),
            daily_request_limit=positive_int("ROXY_HOME_AI_DAILY_REQUEST_LIMIT", 100),
            daily_output_token_limit=positive_int("ROXY_HOME_AI_DAILY_OUTPUT_TOKEN_LIMIT", 100_000),
            max_output_tokens=positive_int("ROXY_HOME_AI_MAX_OUTPUT_TOKENS", 4_000),
        )


class HomeAIBudgetLedger:
    """A request/token budget used only by Roxy Home."""

    def __init__(self, path: str | Path, *, request_limit: int, output_token_limit: int) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.request_limit = request_limit
        self.output_token_limit = output_token_limit

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            payload = {}
        today = date.today().isoformat()
        if payload.get("date") != today:
            return {"date": today, "requests": 0, "output_tokens": 0}
        return {
            "date": today,
            "requests": max(0, int(payload.get("requests") or 0)),
            "output_tokens": max(0, int(payload.get("output_tokens") or 0)),
        }

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _locked(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read()
                result = callback(payload)
                self._write(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def reserve_request(self) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            if payload["requests"] >= self.request_limit:
                raise HomeAIBudgetExceeded("Roxy Home alcanzó su límite diario de solicitudes.")
            if payload["output_tokens"] >= self.output_token_limit:
                raise HomeAIBudgetExceeded("Roxy Home alcanzó su límite diario de tokens.")
            payload["requests"] += 1
            return dict(payload)

        return self._locked(apply)

    def record_output_tokens(self, count: int) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["output_tokens"] += max(0, int(count))
            return dict(payload)

        return self._locked(apply)

    def snapshot(self) -> dict[str, Any]:
        payload = self._read()
        return {
            **payload,
            "request_limit": self.request_limit,
            "output_token_limit": self.output_token_limit,
        }


SYSTEM_PROMPT = """Eres Roxy, la misma identidad cálida, clara y práctica del ecosistema Roxy, dentro de Roxy Home.
Tu dominio exclusivo aquí es cocina y hogar: recetas, sustituciones, escalado, planes semanales, preferencias,
alergias y despensa. No tienes acceso a memoria, credenciales ni datos de Study o Trading. Trata las alergias
como restricciones estrictas y advierte sobre contaminación cruzada cuando corresponda. Nunca compres, hagas
pedidos ni controles electrodomésticos o dispositivos sensibles. Convertir una receta en lista requiere una
confirmación posterior del usuario y tú solo produces la receta. Responde exclusivamente con JSON válido, sin
Markdown. No inventes fuentes. Para seguridad alimentaria o retiros usa las fuentes web vigentes proporcionadas,
prioriza autoridades como FDA, USDA y CDC, indica fecha y expresa incertidumbre cuando falte información."""


def _extract_json(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Roxy no devolvió una respuesta JSON válida.") from exc
        result = json.loads(value[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("Roxy no devolvió un objeto JSON válido.")
    return result


def _usage_output_tokens(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get("output_tokens") or 0)
    return int(getattr(usage, "output_tokens", 0) or 0)


def _field(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _web_sources(response: Any) -> tuple[bool, list[dict[str, str]]]:
    """Collect sources returned by Responses web_search_call actions/annotations."""
    called = False
    sources: list[dict[str, str]] = []
    seen: set[str] = set()

    def append(raw: Any) -> None:
        url = str(_field(raw, "url", "") or "").strip()
        if not url or url in seen:
            return
        seen.add(url)
        sources.append(
            {
                "title": str(_field(raw, "title", "") or url).strip(),
                "url": url,
                "authority": str(_field(raw, "authority", "") or "").strip(),
            }
        )

    for item in _field(response, "output", []) or []:
        item_type = str(_field(item, "type", "") or "")
        if item_type == "web_search_call":
            called = True
            action = _field(item, "action", {}) or {}
            for source in _field(action, "sources", []) or []:
                append(source)
        for content in _field(item, "content", []) or []:
            for annotation in _field(content, "annotations", []) or []:
                if str(_field(annotation, "type", "") or "") == "url_citation":
                    append(annotation)
    return called, sources


class RoxyHomeAI:
    def __init__(self, config: HomeAIConfig, *, client: Any | None = None) -> None:
        self.config = config
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=config.api_key)
        self.client = client
        self.budget = HomeAIBudgetLedger(
            config.budget_path,
            request_limit=config.daily_request_limit,
            output_token_limit=config.daily_output_token_limit,
        )

    def _respond(self, task: str, context: dict[str, Any], *, deep: bool, current: bool = False) -> dict[str, Any]:
        self.budget.reserve_request()
        request: dict[str, Any] = {
            "model": self.config.deep_model if deep else self.config.routine_model,
            "instructions": SYSTEM_PROMPT,
            "input": json.dumps({"task": task, "home_context": context}, ensure_ascii=False),
            "max_output_tokens": self.config.max_output_tokens,
            "store": False,
        }
        if current:
            request["tools"] = [{"type": "web_search"}]
            request["tool_choice"] = "required"
        response = self.client.responses.create(**request)
        self.budget.record_output_tokens(_usage_output_tokens(response))
        result = _extract_json(_field(response, "output_text", ""))
        if current:
            web_called, sources = _web_sources(response)
            if not web_called:
                raise ValueError("La investigación vigente no ejecutó la búsqueda web requerida.")
            if sources:
                result["sources"] = sources
        result["model_profile"] = "terra" if deep else "luna"
        result["used_current_web_search"] = bool(current)
        return result

    @staticmethod
    def _context(snapshot: dict[str, Any]) -> dict[str, Any]:
        # Only the authenticated user's Home profile and pantry enter the model.
        return {
            "profile": snapshot.get("profile") or {},
            "pantry": snapshot.get("pantry") or [],
        }

    def generate_recipe(self, prompt: str, snapshot: dict[str, Any], *, deep: bool = False) -> dict[str, Any]:
        return self._respond(
            "Genera una receta realizable, incluyendo comidas, panes, postres o bebidas según la solicitud. "
            "Devuelve title, description, kind (meal, bread, dessert, drink u other), servings, ingredients "
            "(name, quantity, unit, notes), steps completos y allergen_notes. Cada paso debe poder leerse en "
            "voz alta como una instrucción clara. Solicitud: " + str(prompt),
            self._context(snapshot),
            deep=deep,
        )

    def substitutions(self, prompt: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self._respond(
            "Propón sustituciones culinarias seguras y explica proporciones. Solicitud: " + str(prompt),
            self._context(snapshot),
            deep=False,
        )

    def weekly_plan(self, prompt: str, snapshot: dict[str, Any], *, deep: bool = False) -> dict[str, Any]:
        return self._respond(
            "Crea un plan semanal. Devuelve days como lista con day y meals; respeta alergias. Solicitud: "
            + str(prompt),
            self._context(snapshot),
            deep=deep,
        )

    def food_safety(self, question: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self._respond(
            "Investiga esta consulta vigente de seguridad alimentaria o retiros. Devuelve answer, checked_at "
            "y sources con title, url y authority. Pregunta: " + str(question),
            self._context(snapshot),
            deep=True,
            current=True,
        )
