from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from roxy_os.core.agent_router import AgentRouter
from roxy_os.memory.memory_manager import RoxyMemoryManager
from roxy_os.models import AgentResult, RoxyRequest
from tools import weather_service


class BaseAgent:
    name = "base"

    def __init__(self, memory: RoxyMemoryManager) -> None:
        self.memory = memory

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        raise NotImplementedError


class GeneralAgent(BaseAgent):
    name = "general"

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        return AgentResult(
            agent=self.name,
            intent=intent,
            message=(
                "Estoy lista como Roxy. Puedo ayudarte con Roxy Trading, classroom, clima, pantalla, lectura de archivos, "
                "navegador, compras, calendario, smart home y codigo. Dentro de Roxy Trading primero uso el contexto visible "
                "de la plataforma antes de responder."
            ),
            data={
                "capabilities": [
                    "trading",
                    "classroom",
                    "weather",
                    "screen",
                    "reader",
                    "browser",
                    "shopping",
                    "calendar",
                    "home",
                    "code",
                    "taxes_on_request",
                ]
            },
        )


def _clean_command_text(text: str) -> str:
    cleaned = re.sub(r"^\s*(hola|ola|hello|hey)\s+roxy\b[\s,.:;-]*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*roxy\b[\s,.:;-]*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


class WeatherAgent(BaseAgent):
    name = "weather"

    LOCATION_PATTERNS = [
        r"(?:clima|weather|lluvia|temperatura|pronostico|pronóstico)\s+(?:en|para|de)\s+(.+)$",
        r"(?:va a llover|llovera|lloverá)\s+(?:en|para)\s+(.+)$",
    ]

    def _extract_location(self, request: RoxyRequest) -> str:
        text = _clean_command_text(request.text)
        for pattern in self.LOCATION_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                location = match.group(1).strip(" ?!.,;:")
                if location:
                    return location
        profile = request.context.get("user_profile") if isinstance(request.context.get("user_profile"), dict) else {}
        for key in ("weather_location", "location", "city"):
            value = str(profile.get(key) or "").strip()
            if value:
                return value
        return weather_service.default_weather_location()

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        location = self._extract_location(request)
        snapshot = weather_service.fetch_current_weather(location)
        payload = snapshot.as_dict()
        if snapshot.status == "ok":
            temp = f"{snapshot.temperature_c:.1f} C" if snapshot.temperature_c is not None else "temperatura no disponible"
            feels = f", se siente {snapshot.feels_like_c:.1f} C" if snapshot.feels_like_c is not None else ""
            humidity = f", humedad {snapshot.humidity}%" if snapshot.humidity is not None else ""
            wind = f", viento {snapshot.wind_mps:.1f} m/s" if snapshot.wind_mps is not None else ""
            description = snapshot.description or "condicion no disponible"
            message = f"Clima en {snapshot.location}: {temp}{feels}, {description}{humidity}{wind}."
        elif snapshot.status == "missing_key":
            message = (
                "Puedo darte clima en vivo, pero falta configurar OPENWEATHER_API_KEY "
                "o ROXY_OPENWEATHER_API_KEY en el entorno."
            )
        else:
            message = f"No pude consultar el clima de {location}: {snapshot.message or snapshot.status}."
        return AgentResult(
            self.name,
            intent,
            message,
            {
                "location": location,
                "weather": payload,
                "requires_weather_api": snapshot.status == "missing_key",
            },
            actions=[
                {
                    "type": "weather_lookup",
                    "location": location,
                    "confirmation_required": False,
                }
            ],
        )


class ReaderAgent(BaseAgent):
    name = "reader"

    BLOCKED_NAMES = {".env", ".env.local", ".env.production", ".npmrc", ".pypirc"}
    BLOCKED_SUFFIXES = {".pem", ".key", ".p12", ".p8"}
    SAFE_SUFFIXES = {".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv", ".ts", ".tsx", ".js", ".jsx"}

    def _extract_path(self, text: str) -> str:
        cleaned = _clean_command_text(text)
        quoted = re.search(r"['\"]([^'\"]+)['\"]", cleaned)
        if quoted:
            return quoted.group(1).strip()
        markers = [
            "lee este archivo",
            "leer archivo",
            "resumeme este archivo",
            "resúmeme este archivo",
            "abre esta carpeta",
            "abre carpeta",
            "lee esto",
        ]
        normalized = cleaned.lower()
        for marker in markers:
            index = normalized.find(marker)
            if index >= 0:
                return cleaned[index + len(marker) :].strip(" :,;")
        return ""

    def _is_blocked_path(self, path: Path) -> bool:
        return path.name in self.BLOCKED_NAMES or path.suffix.lower() in self.BLOCKED_SUFFIXES

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        requested_path = self._extract_path(request.text)
        data: dict[str, Any] = {
            "required_permission": "file_read",
            "mode": permission_mode,
            "requested_path": requested_path,
            "safe_suffixes": sorted(self.SAFE_SUFFIXES),
            "blocked_names": sorted(self.BLOCKED_NAMES),
        }
        if not requested_path:
            return AgentResult(
                self.name,
                intent,
                "Puedo leer o resumir un archivo si me dices cual. Por seguridad no leo secretos ni .env.",
                data,
                actions=[{"type": "file_read_request", "confirmation_required": True}],
            )

        path = Path(requested_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        data["resolved_path"] = str(path)

        if self._is_blocked_path(path):
            return AgentResult(
                self.name,
                intent,
                "No voy a leer ese archivo porque parece contener secretos o llaves.",
                {**data, "blocked": True},
            )

        if permission_mode != "autopilot_safe":
            return AgentResult(
                self.name,
                intent,
                "Puedo preparar la lectura, pero necesito permiso antes de abrir archivos de tu computadora.",
                data,
                actions=[
                    {
                        "type": "file_read_request",
                        "path": str(path),
                        "confirmation_required": True,
                    }
                ],
            )

        if not path.exists():
            return AgentResult(self.name, intent, f"No encontre el archivo o carpeta: {path}.", {**data, "exists": False})

        if path.is_dir():
            children = sorted(child.name for child in path.iterdir() if not child.name.startswith("."))[:30]
            return AgentResult(
                self.name,
                intent,
                "Carpeta abierta. Veo: " + (", ".join(children) if children else "sin archivos visibles") + ".",
                {**data, "type": "directory", "children": children},
            )

        if path.suffix.lower() not in self.SAFE_SUFFIXES:
            return AgentResult(
                self.name,
                intent,
                "Puedo resumir ese tipo de archivo despues de agregar un lector especifico. Por ahora leo texto, codigo y CSV.",
                {**data, "unsupported_suffix": path.suffix},
            )

        content = path.read_text(encoding="utf-8", errors="replace")[:4000]
        summary = " ".join(content.split())[:600]
        return AgentResult(
            self.name,
            intent,
            f"Lei {path.name}. Resumen inicial: {summary}",
            {**data, "type": "file", "chars_read": len(content), "preview": summary},
        )


class ShoppingAgent(BaseAgent):
    name = "shopping"

    def __init__(self, memory: RoxyMemoryManager, router: AgentRouter) -> None:
        super().__init__(memory)
        self.router = router

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        if intent == "shopping_query":
            items = self.memory.list_memories(user_id=request.user_id, memory_type="shopping_item", limit=50)
            if not items:
                return AgentResult(self.name, intent, "No tengo articulos pendientes en tu lista de compra.", {"items": []})
            labels = [item["content"] for item in items]
            return AgentResult(
                self.name,
                intent,
                "En tu lista tengo: " + ", ".join(labels) + ".",
                {"items": items},
            )

        items = self.router.extract_shopping_items(request.text)
        if not items:
            return AgentResult(
                self.name,
                intent,
                "Dime que articulos quieres agregar a la lista de compra.",
                {"items": []},
            )
        writes = []
        for item in items:
            writes.append(
                self.memory.remember(
                    user_id=request.user_id,
                    memory_type="shopping_item",
                    title=f"Comprar {item}",
                    content=item,
                    source="voice_or_text",
                    tags=["shopping", "household"],
                    importance=4,
                    metadata={"status": "pending"},
                )
            )
        return AgentResult(
            self.name,
            intent,
            "Listo, agregue a tu lista: " + ", ".join(item["content"] for item in writes) + ".",
            {"items": writes},
            memory_writes=writes,
        )


class TraderAgent(BaseAgent):
    name = "trader"

    STOCK_SYMBOLS = {
        "apple": "AAPL",
        "aapl": "AAPL",
        "microsoft": "MSFT",
        "msft": "MSFT",
        "nvidia": "NVDA",
        "nvda": "NVDA",
        "tesla": "TSLA",
        "tsla": "TSLA",
        "amd": "AMD",
        "amazon": "AMZN",
        "amzn": "AMZN",
        "meta": "META",
    }
    CRYPTO_SYMBOLS = {
        "bitcoin": "BTC/USD",
        "btc": "BTC/USD",
        "ethereum": "ETH/USD",
        "eth": "ETH/USD",
        "solana": "SOL/USD",
        "sol": "SOL/USD",
        "xrp": "XRP/USD",
        "doge": "DOGE/USD",
        "bnb": "BNB/USD",
    }

    def _extract_symbol(self, normalized: str, context_symbol: Any) -> tuple[str, str]:
        for key, symbol in self.CRYPTO_SYMBOLS.items():
            if key in normalized:
                return symbol, "crypto"
        for key, symbol in self.STOCK_SYMBOLS.items():
            if key in normalized:
                return symbol, "stock"
        context_value = str(context_symbol or "").strip().upper()
        if context_value:
            return context_value, "crypto" if "/" in context_value else "stock"
        return "AAPL", "stock"

    def _visible_rows(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        snapshot = context.get("opportunity_snapshot")
        if not isinstance(snapshot, dict):
            snapshot = context.get("opportunitySnapshot")
        if not isinstance(snapshot, dict) and isinstance(context.get("raw"), dict):
            raw_context = context["raw"]
            snapshot = raw_context.get("opportunity_snapshot")
            if not isinstance(snapshot, dict):
                snapshot = raw_context.get("opportunitySnapshot")
        rows = snapshot.get("rows") if isinstance(snapshot, dict) else []
        return [row for row in rows if isinstance(row, dict)]

    def _row_value(self, row: dict[str, Any], *keys: str, default: str = "no visible") -> str:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return str(value)
        return default

    def _best_visible_row(self, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not rows:
            return None

        def score(row: dict[str, Any]) -> float:
            raw = row.get("confidence") or row.get("score") or row.get("probability") or row.get("strength") or 0
            try:
                return float(str(raw).replace("%", "").strip())
            except ValueError:
                return 0.0

        return max(rows, key=score)

    def _visible_opportunity_message(self, row: dict[str, Any], *, module: str, symbol: str) -> str:
        ticker = self._row_value(row, "symbol", "ticker", default=symbol)
        decision = self._row_value(row, "decision", "signal", "state", default="ESPERAR CONFIRMACION")
        price = self._row_value(row, "price", "live_price", "current_price")
        entry = self._row_value(row, "entry", "entrada")
        stop = self._row_value(row, "stop", "stop_loss", "stopLoss")
        target = self._row_value(row, "target", "target_1", "target1", "tp")
        confidence = self._row_value(row, "confidence", "score", "probability")
        reason = self._row_value(row, "reason", "why", "setup", default="Roxy necesita mas confirmacion visible.")
        risk = self._row_value(row, "risk", "risk_reward", "rr", "r_r")

        if module in {"crypto-20m", "crypto-2h", "crypto-daily"}:
            direction = decision if decision in {"YES", "NO", "NO TRADE"} else decision.upper()
            return (
                f"Mejor oportunidad visible: {ticker}. Senal: {direction}. Precio live: {price}. "
                f"Entrada/strike: {entry}. Stop virtual: {stop}. Objetivo: {target}. "
                f"Confianza: {confidence}. Riesgo/RR: {risk}. Razon: {reason}. "
                "No ejecuto dinero real; usa esto para paper trading y confirma el contrato en la plataforma."
            )

        return (
            f"Mejor oportunidad visible: {ticker}. Estado: {decision}. Precio live: {price}. "
            f"Entrada: {entry}. Stop loss: {stop}. Target: {target}. "
            f"Confianza: {confidence}. Riesgo/RR: {risk}. Razon: {reason}. "
            "No ejecuto trades reales; confirma liquidez, spread y tamano de posicion antes de operar."
        )

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        watchlist = self.memory.list_memories(user_id=request.user_id, memory_type="watchlist", limit=20)
        normalized = request.text.lower()
        requested_symbol, requested_market = self._extract_symbol(normalized, request.context.get("symbol"))
        if any(part in normalized for part in ["2h", "2 h", "dos horas", "2 horas"]):
            module = "crypto-2h"
            symbol = requested_symbol if requested_market == "crypto" else "BTC/USD"
            market = "crypto"
            timeframe = "2h"
        elif any(part in normalized for part in ["daily", "diario", "dia", "día"]):
            module = "crypto-daily"
            symbol = requested_symbol if requested_market == "crypto" else "BTC/USD"
            market = "crypto"
            timeframe = "1d"
        elif any(part in normalized for part in ["crypto", "cripto", "bitcoin", "btc", "20 minuto", "20min"]):
            module = "crypto-20m"
            symbol = requested_symbol if requested_market == "crypto" else "BTC/USD"
            market = "crypto"
            timeframe = "1m"
        else:
            module = "acciones-operar"
            symbol = requested_symbol if requested_market == "stock" else "AAPL"
            market = "stock"
            timeframe = "1h"
        visible_rows = self._visible_rows(request.context)
        best_visible = self._best_visible_row(visible_rows)
        message = (
            self._visible_opportunity_message(best_visible, module=module, symbol=symbol)
            if best_visible
            else (
                "Voy a abrir el modulo operativo correcto y sincronizar las graficas live. Roxy debe mostrar precio, "
                "entrada, stop, target, riesgo, confianza y razon. No ejecutare trades reales sin confirmacion."
            )
        )
        return AgentResult(
            self.name,
            intent,
            message,
            {
                "module": module,
                "symbol": symbol,
                "market": market,
                "timeframe": timeframe,
                "visible_opportunities": visible_rows,
                "best_visible_opportunity": best_visible,
                "next_action": "open_roxy_trading_and_scan",
                "watchlist_memory": watchlist,
                "requires_live_market_data": True,
                "analysis_contract": {
                    "symbol": symbol,
                    "market": market,
                    "timeframe": timeframe,
                    "required_outputs": [
                        "live_price",
                        "signal",
                        "entry",
                        "stop_loss",
                        "target",
                        "risk_reward",
                        "confidence",
                        "why",
                    ],
                    "crypto_strike_modes": ["YES", "NO", "NO TRADE"],
                },
            },
            actions=[
                {
                    "type": "open_module",
                    "module": module,
                    "symbol": symbol,
                    "market": market,
                    "timeframe": timeframe,
                    "confirmation_required": False,
                },
                {
                    "type": "run_trading_scan",
                    "module": module,
                    "market": market,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "confirmation_required": False,
                },
            ],
        )


class ScreenAgent(BaseAgent):
    name = "screen"

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        return AgentResult(
            self.name,
            intent,
            (
                "Puedo resumir tu pantalla cuando el permiso de captura este activo. Primero trabajare en modo lectura; "
                "para hacer clic, copiar o escribir te pedire permiso."
            ),
            {
                "required_permission": "screen_read",
                "mode": permission_mode,
                "next_action": "capture_screen_summary",
            },
            actions=[
                {
                    "type": "screen_capture_summary",
                    "confirmation_required": permission_mode != "autopilot_safe",
                }
            ],
        )


class BrowserAgent(BaseAgent):
    name = "browser"

    def _extract_query(self, text: str) -> str:
        cleaned = _clean_command_text(text)
        patterns = [
            r"(?:abre\s+google\s+y\s+busca|busca\s+en\s+google|busca|buscar)\s+(.+)$",
            r"(?:abre\s+la\s+pagina|abre\s+la\s+página|abre)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,:;")
                if value:
                    return value
        return cleaned

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        query = self._extract_query(request.text)
        return AgentResult(
            self.name,
            intent,
            f"Puedo buscar: {query}. Preparare la accion de navegador y resumire resultados antes de cualquier formulario o compra.",
            {
                "required_permission": "browser",
                "mode": permission_mode,
                "query": query,
            },
            actions=[{"type": "browser_search_or_open", "query": query, "confirmation_required": False}],
        )


class CalendarAgent(BaseAgent):
    name = "calendar"

    REMINDER_PATTERNS = [
        r"(?:acuerdame|acuérdame|recuerdame|recuérdame)\s+(?:que\s+)?(.+)$",
        r"(?:agrega|guarda)\s+(?:un\s+)?recordatorio\s+(?:para\s+)?(.+)$",
    ]

    def _extract_reminder(self, text: str) -> str:
        cleaned = _clean_command_text(text)
        for pattern in self.REMINDER_PATTERNS:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,:;")
                if value:
                    return value
        return ""

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        reminder = self._extract_reminder(request.text)
        if reminder:
            saved = self.memory.remember(
                user_id=request.user_id,
                memory_type="reminder",
                title=f"Recordatorio: {reminder[:80]}",
                content=reminder,
                source="voice_or_text",
                tags=["calendar", "reminder"],
                importance=4,
                metadata={"status": "pending"},
            )
            return AgentResult(
                self.name,
                intent,
                f"Listo, guarde el recordatorio: {reminder}.",
                {"reminder": saved, "requires_calendar_integration": False},
                memory_writes=[saved],
            )

        reminders = self.memory.list_memories(user_id=request.user_id, memory_type="reminder", limit=20)
        if reminders:
            labels = [item["content"] for item in reminders[:8]]
            message = "Tienes estos recordatorios: " + "; ".join(labels) + "."
        else:
            message = (
                "No tengo recordatorios locales pendientes. Cuando conectemos Calendar podre revisar eventos reales "
                "por mes, citas y alertas."
            )
        return AgentResult(
            self.name,
            intent,
            message,
            {"reminders": reminders, "requires_calendar_integration": True},
        )


class HomeAgent(BaseAgent):
    name = "home"

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        return AgentResult(
            self.name,
            intent,
            (
                "Roxy Home debe conectarse a Home Assistant para controlar luces, temperatura, camaras y TV. "
                "Las camaras y seguridad siempre requieren permisos claros."
            ),
            {
                "recommended_hub": "Home Assistant",
                "required_permission": "smart_home",
                "mode": permission_mode,
            },
            actions=[{"type": "home_assistant_command", "command": request.text, "confirmation_required": True}],
        )


class TaxesAgent(BaseAgent):
    name = "taxes"

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        return AgentResult(
            self.name,
            intent,
            (
                "Puedo ayudarte a organizar documentos fiscales, detectar informacion faltante y explicar opciones. "
                "Las decisiones finales deben revisarse con un profesional autorizado."
            ),
            {
                "required_permission": "tax_documents",
                "mode": permission_mode,
                "boundaries": ["no_legal_or_tax_guarantees", "review_required_before_filing"],
            },
        )


class AcademyAgent(BaseAgent):
    name = "academy"

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        progress = self.memory.list_memories(user_id=request.user_id, memory_type="academy_progress", limit=20)
        return AgentResult(
            self.name,
            intent,
            "Puedo guiarte por planetas, clases y juegos. El progreso se guarda en la memoria central de Roxy.",
            {"progress": progress, "module": "classroom", "next_action": "open_classroom"},
            actions=[
                {
                    "type": "open_module",
                    "module": "classroom",
                    "symbol": str(request.context.get("symbol") or "AAPL"),
                    "market": str(request.context.get("market") or "stock"),
                    "timeframe": str(request.context.get("timeframe") or "1h"),
                    "confirmation_required": False,
                }
            ],
        )


class CodeAgent(BaseAgent):
    name = "code"

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        return AgentResult(
            self.name,
            intent,
            (
                "Puedo analizar el proyecto, crear scripts, correr tests y proponer cambios usando el terminal agent. "
                "No hare push, deploy ni comandos destructivos sin confirmacion."
            ),
            {
                "terminal_agent": "roxy-terminal-agent",
                "mode": permission_mode,
                "blocked": ["rm -rf", "sudo", "git push", "production deploy"],
            },
        )


class MemoryAgent(BaseAgent):
    name = "memory"

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        results = self.memory.search(request.text, user_id=request.user_id, limit=8)
        if not results:
            return AgentResult(self.name, intent, "No encontre recuerdos relacionados todavia.", {"memories": []})
        return AgentResult(
            self.name,
            intent,
            "Encontre estos recuerdos relacionados: " + "; ".join(item["title"] for item in results[:3]) + ".",
            {"memories": results},
        )
