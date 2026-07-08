from __future__ import annotations

import re


class AgentRouter:
    def route(self, text: str) -> tuple[str, str]:
        normalized = text.lower().strip()

        if self._has_any(
            normalized,
            ["clima", "weather", "lluvia", "llover", "rain", "temperatura afuera", "pronostico", "pronóstico"],
        ):
            return "weather_query", "weather"

        if self._has_any(normalized, ["comprar", "compra", "mercado", "supermercado"]) and self._has_any(
            normalized, ["pan", "cafe", "café", "leche", "mercado", "casa"]
        ):
            return "shopping_add", "shopping"
        if self._has(normalized, "que necesito comprar") or self._has(normalized, "lista de compra"):
            return "shopping_query", "shopping"

        if self._has_any(
            normalized,
            [
                "roxy trading",
                "oportunidades",
                "inversion",
                "inversión",
                "acciones",
                "accion",
                "acción",
                "crypto",
                "cripto",
                "bitcoin",
                "btc",
                "ethereum",
                "eth",
                "solana",
                "sol",
                "apple",
                "aapl",
                "microsoft",
                "msft",
                "nvidia",
                "nvda",
                "tesla",
                "tsla",
            ],
        ):
            return "trading_scan", "trader"

        if self._has_any(normalized, ["pantalla", "estoy viendo", "lee este articulo", "léeme este artículo", "resume esto"]):
            return "screen_summary", "screen"

        if self._has_any(normalized, ["lee este archivo", "leer archivo", "abre esta carpeta", "abre carpeta", "lee esto", "resumeme este archivo", "resúmeme este archivo"]):
            return "reader_request", "reader"

        if self._has_any(normalized, ["abre google", "busca en google", "navega", "abre la pagina", "abre la página"]):
            return "browser_action", "browser"

        if self._has_any(normalized, ["temperatura", "luces", "televisor", "volumen", "camara", "cámara", "termostato"]):
            return "home_control", "home"

        if self._has_any(
            normalized,
            [
                "evento",
                "cita",
                "calendario",
                "este mes",
                "recordatorio",
                "recordatorios",
                "acuerdame",
                "acuérdame",
                "recuerdame",
                "recuérdame",
            ],
        ):
            return "calendar_query", "calendar"

        if self._has_any(normalized, ["tax", "taxes", "impuesto", "declaracion", "declaración", "deduccion", "deducción"]):
            return "taxes_assist", "taxes"

        if self._has_any(normalized, ["classroom", "academy", "clase", "leccion", "lección", "aprender"]):
            return "academy_query", "academy"

        if self._has_any(
            normalized,
            ["codigo", "código", "terminal", "test", "build", "error de codigo", "git push", "deploy", "produccion", "producción"],
        ):
            return "code_task", "code"

        if self._has_any(normalized, ["recuerda", "recordaste", "que sabes de", "memoria"]):
            return "memory_recall", "memory"

        return "general", "general"

    def _has(self, text: str, *parts: str) -> bool:
        return all(part in text for part in parts)

    def _has_any(self, text: str, parts: list[str]) -> bool:
        return any(part in text for part in parts)

    def extract_shopping_items(self, text: str) -> list[str]:
        normalized = re.sub(r"(?i)^.*?(comprar|compra de la casa|necesito)\s+", "", text).strip()
        normalized = re.sub(r"(?i)\b(roxy|acu[eé]rdame|recuerdame|que tengo que|hacer la)\b", "", normalized)
        items = re.split(r",|\sy\s|\be[xs]tera\b|\betc(?:etera)?\b", normalized)
        cleaned = []
        for item in items:
            value = re.sub(r"\s+", " ", item).strip(" .;:-")
            if value and len(value) > 1:
                cleaned.append(value)
        if len(cleaned) == 1:
            common_groceries = {
                "agua",
                "arroz",
                "azucar",
                "azúcar",
                "cafe",
                "café",
                "carne",
                "cereal",
                "huevo",
                "huevos",
                "jabon",
                "jabón",
                "jugo",
                "leche",
                "pan",
                "papel",
                "pollo",
                "queso",
                "sal",
                "yogurt",
            }
            words = cleaned[0].split()
            if 1 < len(words) <= 8 and all(word.lower() in common_groceries for word in words):
                cleaned = words
        return cleaned
