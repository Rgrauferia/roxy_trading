"""OpenAI reasoning layer for Roxy Trading.

This module is intentionally product-scoped.  It never reads a generic OpenAI
key, Study/Home memory, or broker credentials.  It explains verified Roxy data;
it does not create market facts or execute orders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping, Protocol
from uuid import uuid4


PRODUCT = "roxy_trading"
ROUTINE_TIER = "routine"
DEEP_TIER = "deep"
DEFAULT_ROUTINE_MODEL = "gpt-5.6-luna"
DEFAULT_DEEP_MODEL = "gpt-5.6-terra"
DEFAULT_LEDGER_PATH = Path("alerts") / "roxy_trading_openai_usage.sqlite"
DEFAULT_LUNA_INPUT_USD_PER_MTOK = 0.20
DEFAULT_LUNA_OUTPUT_USD_PER_MTOK = 1.20
DEFAULT_TERRA_INPUT_USD_PER_MTOK = 2.00
DEFAULT_TERRA_OUTPUT_USD_PER_MTOK = 12.00


class ResponsesClient(Protocol):
    class _Responses(Protocol):
        def create(self, **kwargs: Any) -> Any: ...

    responses: _Responses


@dataclass(frozen=True)
class RoxyOpenAIConfig:
    api_key: str
    enabled: bool
    product: str = PRODUCT
    routine_model: str = DEFAULT_ROUTINE_MODEL
    deep_model: str = DEFAULT_DEEP_MODEL
    monthly_budget_usd: float = 0.0
    max_call_reserve_usd: float = 0.25
    ledger_path: Path = DEFAULT_LEDGER_PATH
    routine_input_usd_per_mtoken: float | None = DEFAULT_LUNA_INPUT_USD_PER_MTOK
    routine_output_usd_per_mtoken: float | None = DEFAULT_LUNA_OUTPUT_USD_PER_MTOK
    deep_input_usd_per_mtoken: float | None = DEFAULT_TERRA_INPUT_USD_PER_MTOK
    deep_output_usd_per_mtoken: float | None = DEFAULT_TERRA_OUTPUT_USD_PER_MTOK

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        product: str = "trading",
    ) -> "RoxyOpenAIConfig":
        values = env if env is not None else os.environ
        scope = "crypto" if str(product).strip().lower() == "crypto" else "trading"
        prefix = f"ROXY_{scope.upper()}_OPENAI"
        product_name = f"roxy_{scope}"
        # Deliberately no fallback to OPENAI_API_KEY or a Study key.
        key = str(values.get(f"{prefix}_API_KEY", "")).strip()
        enabled = str(values.get(f"{prefix}_ENABLED", "0")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return cls(
            api_key=key,
            enabled=enabled,
            product=product_name,
            routine_model=str(values.get(f"{prefix}_ROUTINE_MODEL", DEFAULT_ROUTINE_MODEL)).strip()
            or DEFAULT_ROUTINE_MODEL,
            deep_model=str(values.get(f"{prefix}_DEEP_MODEL", DEFAULT_DEEP_MODEL)).strip()
            or DEFAULT_DEEP_MODEL,
            monthly_budget_usd=_nonnegative_float(
                values.get(f"{prefix}_MONTHLY_BUDGET_USD"), 0.0
            ),
            max_call_reserve_usd=max(
                0.01,
                _nonnegative_float(values.get(f"{prefix}_MAX_CALL_USD"), 0.25),
            ),
            ledger_path=Path(
                str(values.get(f"{prefix}_USAGE_DB", "")).strip()
                or Path("alerts") / f"roxy_{scope}_openai_usage.sqlite"
            ),
            routine_input_usd_per_mtoken=_optional_nonnegative_float(
                values.get(f"{prefix}_LUNA_INPUT_USD_PER_MTOK"),
                DEFAULT_LUNA_INPUT_USD_PER_MTOK,
            ),
            routine_output_usd_per_mtoken=_optional_nonnegative_float(
                values.get(f"{prefix}_LUNA_OUTPUT_USD_PER_MTOK"),
                DEFAULT_LUNA_OUTPUT_USD_PER_MTOK,
            ),
            deep_input_usd_per_mtoken=_optional_nonnegative_float(
                values.get(f"{prefix}_TERRA_INPUT_USD_PER_MTOK"),
                DEFAULT_TERRA_INPUT_USD_PER_MTOK,
            ),
            deep_output_usd_per_mtoken=_optional_nonnegative_float(
                values.get(f"{prefix}_TERRA_OUTPUT_USD_PER_MTOK"),
                DEFAULT_TERRA_OUTPUT_USD_PER_MTOK,
            ),
        )

    def public_status(self) -> dict[str, Any]:
        return {
            "product": self.product,
            "enabled": self.enabled,
            "configured": bool(self.api_key),
            "routine_model": self.routine_model,
            "deep_model": self.deep_model,
            "monthly_budget_usd": self.monthly_budget_usd,
            "max_call_reserve_usd": self.max_call_reserve_usd,
            "memory_scope": self.product,
            "credential_scope": self.product,
            "key_exposed": False,
        }


@dataclass(frozen=True)
class RoxySource:
    name: str
    url: str | None = None
    as_of: str | None = None


@dataclass(frozen=True)
class RoxyUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    budget_charge_usd: float = 0.0
    monthly_spend_usd: float = 0.0
    monthly_budget_usd: float = 0.0


@dataclass(frozen=True)
class RoxyOpenAIAnswer:
    text: str
    status: str
    model: str | None
    tier: str
    sources: tuple[RoxySource, ...] = field(default_factory=tuple)
    usage: RoxyUsage = field(default_factory=RoxyUsage)
    requires_confirmation: bool = False
    execution_allowed: bool = False
    data_as_of: str | None = None
    blocked_reason: str | None = None

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nonnegative_float(value: Any, default: float) -> float:
    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _optional_nonnegative_float(value: Any, default: float | None = None) -> float | None:
    if value is None or not str(value).strip():
        return default
    return _nonnegative_float(value, 0.0)


def _month_key(now: datetime | None = None) -> str:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return current.strftime("%Y-%m")


class RoxyOpenAIUsageLedger:
    """Token/cost ledger isolated from every other Roxy product."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS roxy_trading_openai_usage (
                request_id TEXT PRIMARY KEY,
                month_key TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                model TEXT NOT NULL,
                tier TEXT NOT NULL,
                status TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                estimated_cost_usd REAL,
                budget_charge_usd REAL NOT NULL
            )
            """
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return connection

    def reserve(self, *, model: str, tier: str, amount_usd: float, budget_usd: float) -> str | None:
        request_id = uuid4().hex
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            spent = float(
                connection.execute(
                    "SELECT COALESCE(SUM(budget_charge_usd), 0) FROM roxy_trading_openai_usage "
                    "WHERE month_key = ?",
                    (_month_key(now),),
                ).fetchone()[0]
            )
            if spent + amount_usd > budget_usd + 1e-9:
                connection.rollback()
                return None
            connection.execute(
                "INSERT INTO roxy_trading_openai_usage "
                "(request_id, month_key, occurred_at, model, tier, status, budget_charge_usd) "
                "VALUES (?, ?, ?, ?, ?, 'reserved', ?)",
                (request_id, _month_key(now), now.isoformat(), model, tier, amount_usd),
            )
        return request_id

    def complete(
        self,
        request_id: str,
        *,
        status: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        estimated_cost_usd: float | None,
        budget_charge_usd: float,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE roxy_trading_openai_usage SET status = ?, input_tokens = ?, "
                "output_tokens = ?, total_tokens = ?, estimated_cost_usd = ?, "
                "budget_charge_usd = ? WHERE request_id = ?",
                (
                    status,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost_usd,
                    max(0.0, budget_charge_usd),
                    request_id,
                ),
            )

    def monthly_spend(self) -> float:
        if not self.path.exists():
            return 0.0
        with self._connect() as connection:
            value = connection.execute(
                "SELECT COALESCE(SUM(budget_charge_usd), 0) FROM roxy_trading_openai_usage "
                "WHERE month_key = ?",
                (_month_key(),),
            ).fetchone()[0]
        return round(float(value or 0.0), 6)


_DEEP_TERMS = re.compile(
    r"\b(investiga|investigacion|research|profundo|deep|escenarios?|scenario|"
    r"noticias?|news|catalizadores?|catalysts?|macro)\b",
    re.IGNORECASE,
)
_CURRENT_MARKET_TERMS = re.compile(
    r"\b(hoy|ahora|actual|current|live|precio|price|cotizacion|quote|noticias?|news|"
    r"senal|señal|signal|entrada|entry|stop|target|mercado|market|ticker|accion|acción|crypto)\b",
    re.IGNORECASE,
)
_WEB_RESEARCH_TERMS = re.compile(
    r"\b(noticias?|news|catalizadores?|catalysts?|macro|investiga|investigacion|research|"
    r"regulacion|regulación|sec|fed|etf|aprobacion|aprobación)\b",
    re.IGNORECASE,
)
_SENSITIVE_ACTION = re.compile(
    r"\b(compra|vende|ejecuta|coloca|cancela|abre (?:una )?posicion|cierra (?:la )?posicion|"
    r"buy now|sell now|place (?:the )?order|execute (?:the )?trade|cancel (?:the )?order)\b",
    re.IGNORECASE,
)


def route_tier(question: str, requested_depth: str | None = None) -> str:
    depth = str(requested_depth or "").strip().lower()
    if depth in {"deep", "research", "profundo"} or _DEEP_TERMS.search(question or ""):
        return DEEP_TIER
    return ROUTINE_TIER


def sanitize_sources(raw_sources: Any) -> tuple[RoxySource, ...]:
    sources: list[RoxySource] = []
    for item in raw_sources if isinstance(raw_sources, (list, tuple)) else []:
        if isinstance(item, str):
            name = item.strip()
            url = None
            as_of = None
        elif isinstance(item, Mapping):
            name = str(item.get("name") or item.get("provider") or item.get("source") or "").strip()
            url = str(item.get("url") or "").strip() or None
            as_of = str(item.get("as_of") or item.get("timestamp") or "").strip() or None
        else:
            continue
        if name:
            sources.append(RoxySource(name=name[:120], url=url, as_of=as_of))
    return tuple(sources[:12])


def _usage_value(usage: Any, key: str) -> int | None:
    value = usage.get(key) if isinstance(usage, Mapping) else getattr(usage, key, None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _response_web_sources(response: Any) -> tuple[bool, tuple[RoxySource, ...]]:
    called = False
    collected: list[dict[str, Any]] = []
    output = response.get("output", []) if isinstance(response, Mapping) else getattr(response, "output", [])
    for item in output or []:
        item_type = item.get("type") if isinstance(item, Mapping) else getattr(item, "type", "")
        if item_type == "web_search_call":
            called = True
            action = item.get("action", {}) if isinstance(item, Mapping) else getattr(item, "action", {})
            raw_sources = action.get("sources", []) if isinstance(action, Mapping) else getattr(action, "sources", [])
            for source in raw_sources or []:
                if isinstance(source, Mapping):
                    collected.append(
                        {
                            "name": source.get("title") or source.get("url") or "Fuente web",
                            "url": source.get("url"),
                            "as_of": source.get("published_at") or source.get("date"),
                        }
                    )
        content = item.get("content", []) if isinstance(item, Mapping) else getattr(item, "content", [])
        for part in content or []:
            annotations = part.get("annotations", []) if isinstance(part, Mapping) else getattr(part, "annotations", [])
            for annotation in annotations or []:
                annotation_type = annotation.get("type") if isinstance(annotation, Mapping) else getattr(annotation, "type", "")
                if annotation_type != "url_citation":
                    continue
                url = annotation.get("url") if isinstance(annotation, Mapping) else getattr(annotation, "url", None)
                title = annotation.get("title") if isinstance(annotation, Mapping) else getattr(annotation, "title", None)
                collected.append({"name": title or url or "Fuente web", "url": url})
    return called, sanitize_sources(collected)


class RoxyTradingOpenAIBrain:
    def __init__(
        self,
        config: RoxyOpenAIConfig | None = None,
        *,
        client: ResponsesClient | None = None,
        ledger: RoxyOpenAIUsageLedger | None = None,
    ) -> None:
        self.config = config or RoxyOpenAIConfig.from_env()
        self._client = client
        self.ledger = ledger or RoxyOpenAIUsageLedger(self.config.ledger_path)

    def _client_or_create(self) -> ResponsesClient:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.config.api_key)
        return self._client

    def answer(
        self,
        question: str,
        *,
        market_context: Mapping[str, Any] | None = None,
        requested_depth: str | None = None,
        confirmed: bool = False,
    ) -> RoxyOpenAIAnswer:
        prompt = str(question or "").strip()
        tier = route_tier(prompt, requested_depth)
        model = self.config.deep_model if tier == DEEP_TIER else self.config.routine_model
        context = dict(market_context or {})
        sources = sanitize_sources(context.pop("sources", []))
        data_as_of = str(context.get("data_as_of") or context.get("as_of") or "").strip() or None

        if not prompt:
            return self._blocked("La pregunta está vacía.", "empty_question", tier, model, sources)
        if not self.config.enabled or not self.config.api_key:
            return self._blocked(
                f"El cerebro OpenAI de {self._product_label()} no está configurado.",
                "not_configured",
                tier,
                model,
                sources,
            )
        if self.config.monthly_budget_usd <= 0:
            return self._blocked(
                f"El presupuesto independiente de OpenAI para {self._product_label()} no está habilitado.",
                "budget_not_configured",
                tier,
                model,
                sources,
            )
        if _SENSITIVE_ACTION.search(prompt) and not confirmed:
            return RoxyOpenAIAnswer(
                text=(
                    "Necesito tu confirmación antes de preparar una acción sensible. "
                    "Puedo explicar el escenario y crear un preview, pero no colocaré la orden."
                ),
                status="confirmation_required",
                model=None,
                tier=tier,
                sources=sources,
                requires_confirmation=True,
                execution_allowed=False,
                data_as_of=data_as_of,
                blocked_reason="sensitive_action",
            )
        if _CURRENT_MARKET_TERMS.search(prompt) and not sources:
            return self._blocked(
                "No tengo una fuente de mercado verificable para responder eso sin inventar datos.",
                "missing_market_sources",
                tier,
                model,
                sources,
                data_as_of=data_as_of,
            )

        reservation = self.ledger.reserve(
            model=model,
            tier=tier,
            amount_usd=self.config.max_call_reserve_usd,
            budget_usd=self.config.monthly_budget_usd,
        )
        if reservation is None:
            return self._blocked(
                f"Roxy alcanzó el presupuesto mensual independiente de OpenAI para {self._product_label()}.",
                "monthly_budget_exhausted",
                tier,
                model,
                sources,
                data_as_of=data_as_of,
            )

        safe_context = _json_safe_context(context)
        source_payload = [asdict(source) for source in sources]
        try:
            use_web_search = tier == DEEP_TIER and bool(_WEB_RESEARCH_TERMS.search(prompt))
            request: dict[str, Any] = {
                "model": model,
                "instructions": _system_instructions(tier, product=self.config.product),
                "input": json.dumps(
                    {
                        "question": prompt,
                        "verified_roxy_context": safe_context,
                        "sources": source_payload,
                        "data_as_of": data_as_of,
                        "confirmed_for_preview": bool(confirmed),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "reasoning": {"effort": "high" if tier == DEEP_TIER else "low"},
                "max_output_tokens": 900 if tier == DEEP_TIER else 450,
                "store": False,
            }
            if use_web_search:
                request["tools"] = [{"type": "web_search"}]
                request["tool_choice"] = "required"
            response = self._client_or_create().responses.create(**request)
            if use_web_search:
                web_called, web_sources = _response_web_sources(response)
                if not web_called:
                    raise ValueError("required_web_search_missing")
                sources = sanitize_sources(
                    [*(asdict(item) for item in sources), *(asdict(item) for item in web_sources)]
                )
            text = str(getattr(response, "output_text", "") or "").strip()
            usage_raw = getattr(response, "usage", None)
            input_tokens = _usage_value(usage_raw, "input_tokens")
            output_tokens = _usage_value(usage_raw, "output_tokens")
            total_tokens = _usage_value(usage_raw, "total_tokens")
            estimated_cost = self._estimate_cost(tier, input_tokens, output_tokens)
            charge = estimated_cost if estimated_cost is not None else self.config.max_call_reserve_usd
            self.ledger.complete(
                reservation,
                status="completed",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                budget_charge_usd=charge,
            )
            return RoxyOpenAIAnswer(
                text=text or "OpenAI no devolvió una explicación utilizable.",
                status="ok" if text else "empty_response",
                model=str(getattr(response, "model", "") or model),
                tier=tier,
                sources=sources,
                usage=RoxyUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    estimated_cost_usd=estimated_cost,
                    budget_charge_usd=round(charge, 6),
                    monthly_spend_usd=self.ledger.monthly_spend(),
                    monthly_budget_usd=self.config.monthly_budget_usd,
                ),
                requires_confirmation=False,
                execution_allowed=False,
                data_as_of=data_as_of,
            )

        except Exception:
            self.ledger.complete(
                reservation,
                status="failed",
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                estimated_cost_usd=None,
                budget_charge_usd=0.0,
            )
            return self._blocked(
                "OpenAI no está disponible ahora; Roxy conserva los datos y gates locales.",
                "provider_error",
                tier,
                model,
                sources,
                data_as_of=data_as_of,
            )

    def _product_label(self) -> str:
        return "Crypto" if self.config.product == "roxy_crypto" else "Trading"

    def _estimate_cost(
        self, tier: str, input_tokens: int | None, output_tokens: int | None
    ) -> float | None:
        if input_tokens is None or output_tokens is None:
            return None
        if tier == DEEP_TIER:
            input_rate = self.config.deep_input_usd_per_mtoken
            output_rate = self.config.deep_output_usd_per_mtoken
        else:
            input_rate = self.config.routine_input_usd_per_mtoken
            output_rate = self.config.routine_output_usd_per_mtoken
        if input_rate is None or output_rate is None:
            return None
        return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 8)

    def _blocked(
        self,
        text: str,
        reason: str,
        tier: str,
        model: str,
        sources: tuple[RoxySource, ...],
        *,
        data_as_of: str | None = None,
    ) -> RoxyOpenAIAnswer:
        return RoxyOpenAIAnswer(
            text=text,
            status="blocked",
            model=None,
            tier=tier,
            sources=sources,
            usage=RoxyUsage(
                monthly_spend_usd=self.ledger.monthly_spend(),
                monthly_budget_usd=self.config.monthly_budget_usd,
            ),
            execution_allowed=False,
            data_as_of=data_as_of,
            blocked_reason=reason,
        )


def _json_safe_context(context: Mapping[str, Any]) -> dict[str, Any]:
    denied = re.compile(r"(secret|password|token|api.?key|credential|private)", re.IGNORECASE)

    def clean(value: Any, depth: int = 0) -> Any:
        if depth > 5:
            return "[truncated]"
        if isinstance(value, Mapping):
            return {
                str(key)[:80]: clean(item, depth + 1)
                for key, item in list(value.items())[:80]
                if not denied.search(str(key))
            }
        if isinstance(value, (list, tuple)):
            return [clean(item, depth + 1) for item in list(value)[:80]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value if not isinstance(value, str) else value[:4000]
        return str(value)[:500]

    cleaned = clean(context)
    return cleaned if isinstance(cleaned, dict) else {}


def _system_instructions(tier: str, *, product: str = PRODUCT) -> str:
    depth = "razonamiento profundo" if tier == DEEP_TIER else "respuesta breve y práctica"
    domain = (
        "Roxy Crypto. Solo analiza activos crypto, exchanges, velas y señales crypto verificadas"
        if product == "roxy_crypto"
        else "Roxy Trading. Solo analiza acciones, ETFs, opciones y datos bursátiles verificados"
    )
    return (
        f"Eres Roxy, la misma identidad femenina del ecosistema Roxy, operando dentro de {domain}. "
        f"Responde en español natural con {depth}. Trabajas únicamente con el JSON de contexto "
        "verificado y sus fuentes. Nunca inventes precios, noticias, señales, posiciones, saldos "
        "ni frescura. Distingue hechos, inferencias y datos faltantes; menciona proveedor y hora "
        "cuando existan. Explica señales, riesgo, escenarios y estrategias, pero nunca coloques, "
        "simules como ejecutada ni afirmes haber colocado una operación. No eludas gates paper/live, "
        "stops, límites ni confirmaciones. Una confirmación solo permite explicar un preview; "
        "execution_allowed siempre es falso. No solicites ni reveles secretos."
    )


def trading_openai_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    config = RoxyOpenAIConfig.from_env(env)
    status = config.public_status()
    status["monthly_spend_usd"] = RoxyOpenAIUsageLedger(config.ledger_path).monthly_spend()
    return status


class RoxyCryptoOpenAIBrain(RoxyTradingOpenAIBrain):
    """Crypto-scoped brain with an independent key, budget and usage ledger."""

    def __init__(
        self,
        config: RoxyOpenAIConfig | None = None,
        *,
        client: ResponsesClient | None = None,
        ledger: RoxyOpenAIUsageLedger | None = None,
    ) -> None:
        super().__init__(
            config or RoxyOpenAIConfig.from_env(product="crypto"),
            client=client,
            ledger=ledger,
        )


def crypto_openai_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    config = RoxyOpenAIConfig.from_env(env, product="crypto")
    status = config.public_status()
    status["monthly_spend_usd"] = RoxyOpenAIUsageLedger(config.ledger_path).monthly_spend()
    return status
