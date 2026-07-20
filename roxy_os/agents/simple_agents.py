from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from roxy_os.core.agent_router import AgentRouter
from roxy_os.memory.memory_manager import RoxyMemoryManager
from roxy_os.models import AgentResult, RoxyRequest
from roxy_os.personal_tasks import ACTIVE_TASK_STATUSES, PersonalTaskStore
from roxy_os.shopping_list import ShoppingListStore
from roxy_os.home_assistant import HomeAssistantClient
from roxy_os.document_vault import DocumentVault
from roxy_os.email_service import GmailReadonlyClient, OutlookReadonlyClient, readonly_email_client
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


class DocumentsAgent(BaseAgent):
    name = "documents"

    def __init__(self, memory: RoxyMemoryManager, vault: DocumentVault | None = None) -> None:
        super().__init__(memory)
        self.vault = vault or DocumentVault()

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        snapshot = self.vault.snapshot(request.user_id, limit=25)
        documents = list(snapshot.get("documents") or [])
        if documents:
            names = [str(row.get("name") or "") for row in documents[:8]]
            message = "Tus documentos locales activos son: " + ", ".join(names) + "."
        else:
            message = "No tienes documentos activos en el repositorio local de Roxy."
        return AgentResult(
            self.name,
            intent,
            message,
            {
                "document_snapshot": snapshot,
                "content_read": False,
                "required_permission_for_content": "file_read",
            },
            actions=[{"type": "open_documents", "view": "Documentos", "confirmation_required": False}],
        )


class EmailAgent(BaseAgent):
    name = "email"

    def __init__(
        self,
        memory: RoxyMemoryManager,
        client: GmailReadonlyClient | OutlookReadonlyClient | None = None,
    ) -> None:
        super().__init__(memory)
        self.client = client or readonly_email_client()

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        inbox = self.client.inbox(limit=5)
        status = str(inbox.get("status") or "SERVICE_NOT_CONFIGURED")
        messages = list(inbox.get("messages") or [])
        provider = "Outlook" if str(inbox.get("provider") or "").lower() == "outlook" else "Gmail"
        if status == "CONNECTED" and messages:
            labels = [str(row.get("subject") or "(sin asunto)") for row in messages]
            message = f"{provider} esta conectado en solo lectura. Asuntos recientes: " + "; ".join(labels) + "."
        elif status == "CONNECTED":
            message = f"{provider} esta conectado en solo lectura y no devolvio mensajes recientes en INBOX."
        else:
            message = f"Correo: {status}. {inbox.get('detail') or 'Proveedor no disponible.'}"
        return AgentResult(
            self.name,
            intent,
            message,
            {"email_snapshot": inbox, "body_read": False, "send_enabled": False},
            actions=[{"type": "open_email", "view": "Correo", "confirmation_required": False}],
        )


class ShoppingAgent(BaseAgent):
    name = "shopping"

    def __init__(
        self,
        memory: RoxyMemoryManager,
        router: AgentRouter,
        shopping_list: ShoppingListStore | None = None,
    ) -> None:
        super().__init__(memory)
        self.router = router
        self.shopping_list = shopping_list or ShoppingListStore()

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        if intent == "shopping_query":
            items = self.shopping_list.list_items(request.user_id, statuses={"PENDING"}, limit=50)
            if not items:
                return AgentResult(self.name, intent, "No tengo articulos pendientes en tu lista de compra.", {"items": []})
            labels = [str(item.get("name") or "") for item in items]
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
            saved = self.shopping_list.add(request.user_id, item, source="voice_or_text")
            saved["content"] = saved["name"]  # compatibility with the original voice response contract
            writes.append(saved)
        return AgentResult(
            self.name,
            intent,
            "Listo, agregue a tu lista: " + ", ".join(item["content"] for item in writes) + ".",
            {"items": writes},
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

    def _matching_visible_row(self, rows: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
        requested = str(symbol or "").strip().upper()
        return next(
            (
                row
                for row in rows
                if str(row.get("symbol") or row.get("ticker") or "").strip().upper() == requested
            ),
            None,
        )

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
        explicit_asset = any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
            for alias in (*self.STOCK_SYMBOLS.keys(), *self.CRYPTO_SYMBOLS.keys())
        )
        relative_asset = any(
            phrase in normalized
            for phrase in (
                "esta oportunidad",
                "este activo",
                "esta accion",
                "esta acción",
                "esta crypto",
                "esta cripto",
                "esta grafica",
                "esta gráfica",
            )
        )
        matching_visible = self._matching_visible_row(visible_rows, requested_symbol)
        best_visible = matching_visible if matching_visible and (explicit_asset or relative_asset) else self._best_visible_row(visible_rows)
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
                "selected_visible_opportunity": matching_visible,
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

    def __init__(self, memory: RoxyMemoryManager, personal_tasks: PersonalTaskStore | None = None) -> None:
        super().__init__(memory)
        self.personal_tasks = personal_tasks or PersonalTaskStore()

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
            saved = self.personal_tasks.create(request.user_id, reminder, source="voice_or_text")
            saved["content"] = saved["title"]  # compatibility with the original reminder response contract
            return AgentResult(
                self.name,
                intent,
                f"Listo, guarde el recordatorio: {reminder}.",
                {"reminder": saved, "task": saved, "requires_calendar_integration": False},
            )

        reminders = self.personal_tasks.list_tasks(
            request.user_id,
            statuses=ACTIVE_TASK_STATUSES,
            limit=20,
        )
        if reminders:
            labels = [str(item.get("title") or "") for item in reminders[:8]]
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
            {"reminders": reminders, "tasks": reminders, "requires_calendar_integration": True},
        )


class HomeAgent(BaseAgent):
    name = "home"

    def __init__(self, memory: RoxyMemoryManager, home_assistant: HomeAssistantClient | None = None) -> None:
        super().__init__(memory)
        self.home_assistant = home_assistant or HomeAssistantClient()

    def handle(self, request: RoxyRequest, *, intent: str, permission_mode: str) -> AgentResult:
        snapshot = self.home_assistant.entities()
        status = str(snapshot.get("status") or "SERVICE_NOT_CONFIGURED")
        if status == "CONNECTED":
            writable = sum(bool(item.get("writable")) for item in snapshot.get("entities", []))
            message = (
                f"Home Assistant esta conectado. Veo {int(snapshot.get('entity_count') or 0)} entidades, "
                f"de las cuales {writable} son luces o interruptores controlables. "
                "Prepare la accion solicitada, pero no la ejecutare sin entidad exacta, permiso y confirmacion."
            )
        else:
            message = f"Roxy Home: {status}. {snapshot.get('detail') or 'Servicio no disponible.'}"
        return AgentResult(
            self.name,
            intent,
            message,
            {
                "recommended_hub": "Home Assistant",
                "required_permission": "smart_home",
                "mode": permission_mode,
                "home_assistant": snapshot,
            },
            actions=[{
                "type": "home_assistant_command_preview",
                "command": request.text,
                "confirmation_required": True,
                "executed": False,
                "provider_status": status,
            }],
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
