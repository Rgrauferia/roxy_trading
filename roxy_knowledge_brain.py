from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


TOKEN_RE = re.compile(r"[a-zA-Z0-9ÁÉÍÓÚÜÑáéíóúüñ/%._-]+")
STOPWORDS = {
    "a",
    "al",
    "and",
    "con",
    "de",
    "del",
    "el",
    "en",
    "for",
    "la",
    "las",
    "los",
    "of",
    "or",
    "para",
    "por",
    "que",
    "the",
    "to",
    "un",
    "una",
    "y",
}


@dataclass(frozen=True)
class KnowledgeFragment:
    id: str
    title: str
    category: str
    source: str
    processed_at: str
    content: str
    path: str


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str) and not value.strip():
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text)
        if len(token) > 2 and token.lower() not in STOPWORDS
    }


def _first_present(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "-"):
            return value
    return None


class RoxyKnowledgeBrain:
    """Retrieves local knowledge and enriches opportunities without replacing strategy logic."""

    def __init__(self, processed_root: str | Path = "knowledge/processed", *, max_fragments: int = 5000) -> None:
        self.processed_root = Path(processed_root)
        self.max_fragments = max(1, int(max_fragments))
        self.fragments: list[KnowledgeFragment] = []
        self._loaded = False

    def load(self) -> "RoxyKnowledgeBrain":
        if self._loaded:
            return self
        fragments: list[KnowledgeFragment] = []
        if self.processed_root.exists():
            for path in sorted(self.processed_root.glob("*/fragments.json")):
                fragments.extend(self._load_fragment_file(path))
                if len(fragments) >= self.max_fragments:
                    break
        self.fragments = fragments[: self.max_fragments]
        self._loaded = True
        return self

    def status(self) -> dict[str, Any]:
        self.load()
        categories: dict[str, int] = {}
        for fragment in self.fragments:
            categories[fragment.category] = categories.get(fragment.category, 0) + 1
        return {
            "processed_root": str(self.processed_root),
            "loaded": self._loaded,
            "fragment_count": len(self.fragments),
            "categories": categories,
        }

    def search(self, query: str, *, categories: Iterable[str] | None = None, limit: int = 6) -> list[dict[str, Any]]:
        self.load()
        query_tokens = _tokens(query)
        category_filter = {item.lower() for item in categories or [] if item}
        if not query_tokens:
            return []

        scored: list[tuple[float, KnowledgeFragment]] = []
        for fragment in self.fragments:
            if category_filter and fragment.category.lower() not in category_filter:
                continue
            title_tokens = _tokens(fragment.title)
            category_tokens = _tokens(fragment.category)
            content_tokens = _tokens(fragment.content[:5000])
            title_hits = len(query_tokens & title_tokens)
            category_hits = len(query_tokens & category_tokens)
            content_hits = len(query_tokens & content_tokens)
            if not (title_hits or category_hits or content_hits):
                continue
            score = title_hits * 5.0 + category_hits * 3.0 + content_hits
            scored.append((score, fragment))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [self._result(fragment, score) for score, fragment in scored[: max(1, int(limit))]]

    def context_for_opportunity(self, opportunity: dict[str, Any], *, limit: int = 6) -> dict[str, Any]:
        query = self._query_for_opportunity(opportunity)
        sources = self.search(query, limit=limit)
        return {
            "query": query,
            "sources": sources,
            "knowledge_score": round(sum(item["score"] for item in sources), 2),
            "source_count": len(sources),
        }

    def enrich_opportunity(self, opportunity: dict[str, Any], *, limit: int = 6) -> dict[str, Any]:
        enriched = dict(opportunity)
        context = self.context_for_opportunity(enriched, limit=limit)
        checklist = self._confirmation_checklist(enriched)
        risk_notes = self._risk_notes(enriched)
        enrichment = {
            "brain_version": "knowledge-brain-v1",
            "mode": "enrich_only_preserve_strategy",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "query": context["query"],
            "knowledge_score": context["knowledge_score"],
            "source_count": context["source_count"],
            "source_fragments": context["sources"],
            "confirmation_checklist": checklist,
            "risk_notes": risk_notes,
            "confidence_adjustment": 0,
            "confidence_adjustment_reason": "La capa de conocimiento no cambia score, senal, entrada, stop ni target; solo agrega contexto para decidir mejor.",
            "roxy_reasoning": self._reasoning(enriched, context, checklist, risk_notes),
        }
        enriched["knowledge_enrichment"] = enrichment
        enriched["knowledge_context_status"] = "READY" if context["source_count"] else "NO_MATCH"
        return enriched

    def enrich_opportunities(self, opportunities: Iterable[dict[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
        return [self.enrich_opportunity(item, limit=limit) for item in opportunities]

    def _load_fragment_file(self, path: Path) -> list[KnowledgeFragment]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = raw if isinstance(raw, list) else raw.get("fragments", [])
        if not isinstance(items, list):
            return []
        loaded: list[KnowledgeFragment] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            content = _safe_text(item.get("content") or item.get("text") or item.get("chunk"))
            if not content:
                continue
            loaded.append(
                KnowledgeFragment(
                    id=_safe_text(item.get("id")) or f"{path.parent.name}-{index + 1:04d}",
                    title=_safe_text(item.get("title")) or path.parent.name,
                    category=_safe_text(item.get("category")) or "sin-categoria",
                    source=_safe_text(item.get("source")) or str(path),
                    processed_at=_safe_text(item.get("processedAt") or item.get("processed_at")),
                    content=content,
                    path=str(path),
                )
            )
        return loaded

    def _result(self, fragment: KnowledgeFragment, score: float) -> dict[str, Any]:
        snippet = " ".join(fragment.content.split())
        if len(snippet) > 280:
            snippet = snippet[:277].rstrip() + "..."
        return {
            "id": fragment.id,
            "title": fragment.title,
            "category": fragment.category,
            "source": fragment.source,
            "processed_at": fragment.processed_at,
            "score": round(float(score), 2),
            "snippet": snippet,
        }

    def _query_for_opportunity(self, row: dict[str, Any]) -> str:
        parts = [
            _safe_text(_first_present(row, ("symbol", "ticker", "asset"))),
            _safe_text(_first_present(row, ("market", "asset_class"))),
            _safe_text(_first_present(row, ("strategy_family", "setup", "trigger_setup", "trend_setup"))),
            _safe_text(_first_present(row, ("timeframe", "entry_tf", "tf"))),
            _safe_text(_first_present(row, ("signal", "trade_decision", "ai_action"))),
            _safe_text(_first_present(row, ("reasons", "memory_note", "alert_next_action"))),
            "EMA SMA VWAP RSI MACD ATR Bollinger volume risk target stop entry trend breakout pullback momentum",
        ]
        return " ".join(part for part in parts if part).strip()

    def _confirmation_checklist(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        signal = _safe_text(row.get("signal")).upper()
        decision = _safe_text(row.get("trade_decision") or row.get("decision")).upper()
        entry = _safe_float(_first_present(row, ("entry", "entrada", "suggested_entry")))
        stop = _safe_float(_first_present(row, ("stop", "stop_loss", "stopLoss")))
        target = _safe_float(_first_present(row, ("recommended_target_price", "target", "target_1", "target_2pct_price")))
        risk = _safe_float(row.get("risk_pct"))
        rel_vol = _safe_float(_first_present(row, ("relative_volume_15m", "relative_volume", "volume_ratio")))
        score = _safe_float(_first_present(row, ("ai_score", "confluence_score", "score")))
        return [
            {"label": "Senal tecnica", "status": "ok" if signal in {"BUY", "WATCH"} else "wait", "detail": signal or "-"},
            {
                "label": "Decision operativa",
                "status": "ok" if decision.startswith("TRADE_FOR") else "wait",
                "detail": decision or "WAIT",
            },
            {"label": "Entrada definida", "status": "ok" if entry is not None else "missing", "detail": entry},
            {"label": "Stop definido", "status": "ok" if stop is not None else "missing", "detail": stop},
            {"label": "Target definido", "status": "ok" if target is not None else "missing", "detail": target},
            {
                "label": "Riesgo medido",
                "status": "ok" if risk is not None and risk <= 0.03 else "wait",
                "detail": f"{risk * 100:.2f}%" if risk is not None else "-",
            },
            {
                "label": "Volumen confirma",
                "status": "ok" if rel_vol is not None and rel_vol >= 1.0 else "wait",
                "detail": f"{rel_vol:.2f}x" if rel_vol is not None else "-",
            },
            {
                "label": "Score suficiente",
                "status": "ok" if score is not None and score >= 70 else "wait",
                "detail": int(score) if score is not None else "-",
            },
        ]

    def _risk_notes(self, row: dict[str, Any]) -> list[str]:
        notes: list[str] = []
        risk = _safe_float(row.get("risk_pct"))
        entry = _safe_float(_first_present(row, ("entry", "entrada", "suggested_entry")))
        stop = _safe_float(_first_present(row, ("stop", "stop_loss", "stopLoss")))
        target = _safe_float(_first_present(row, ("recommended_target_price", "target", "target_1", "target_2pct_price")))
        if entry is None:
            notes.append("Falta entrada: Roxy no debe convertir esta oportunidad en operacion sin precio de entrada.")
        if stop is None:
            notes.append("Falta stop: sin stop no hay control de perdida.")
        if target is None:
            notes.append("Falta target: no hay salida objetiva para calcular relacion riesgo/recompensa.")
        if risk is None:
            notes.append("Falta riesgo porcentual validado.")
        elif risk > 0.03:
            notes.append("Riesgo superior a 3%: requiere confirmacion extra o menor tamano.")
        if entry is not None and stop is not None and stop >= entry:
            notes.append("Stop invalido para setup alcista: debe estar por debajo de la entrada.")
        return notes

    def _reasoning(
        self,
        row: dict[str, Any],
        context: dict[str, Any],
        checklist: list[dict[str, Any]],
        risk_notes: list[str],
    ) -> str:
        symbol = _safe_text(row.get("symbol") or row.get("ticker")).upper() or "Este activo"
        sources = context.get("sources") or []
        ok_count = sum(1 for item in checklist if item.get("status") == "ok")
        total = len(checklist)
        if not sources:
            base = f"{symbol}: Roxy no encontro fragmentos suficientes en la base local para enriquecer esta senal."
        else:
            titles = ", ".join(dict.fromkeys(_safe_text(item.get("title")) for item in sources[:3] if item.get("title")))
            base = f"{symbol}: Roxy comparo la senal con {len(sources)} fragmentos de conocimiento local ({titles})."
        base += f" Checklist operativo {ok_count}/{total}."
        if risk_notes:
            base += " Antes de operar debe resolver: " + " ".join(risk_notes[:2])
        else:
            base += " No detecte huecos criticos de entrada, stop, target o riesgo."
        return base


@lru_cache(maxsize=1)
def default_knowledge_brain() -> RoxyKnowledgeBrain:
    return RoxyKnowledgeBrain().load()


def enrich_opportunity_with_knowledge(opportunity: dict[str, Any], *, limit: int = 6) -> dict[str, Any]:
    return default_knowledge_brain().enrich_opportunity(opportunity, limit=limit)


def enrich_opportunities_with_knowledge(opportunities: Iterable[dict[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
    return default_knowledge_brain().enrich_opportunities(opportunities, limit=limit)
