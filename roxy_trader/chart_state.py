from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


CHART_STATE_SCHEMA_VERSION = 2
MAX_DRAWINGS = 200
MAX_SETTINGS = 32
DEFAULT_CHART_STATE_PATH = Path(os.environ.get("ROXY_CHART_STATE_PATH", "data/roxy_chart_state.json"))
SUPPORTED_DRAWING_TOOLS = {
    "trend",
    "ray",
    "horizontal",
    "vertical",
    "rect",
    "channel",
    "fib",
    "triangle",
    "wedgeUp",
    "wedgeDown",
    "arrow",
    "measure",
    "text",
    "priceLevel",
    "entryZone",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_chart_user(value: Any) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return clean[:96] or "local_user"


def normalize_chart_symbol(value: Any) -> str:
    clean = re.sub(r"[^A-Z0-9./_-]+", "", str(value or "").strip().upper())
    return clean[:32]


def normalize_chart_market(value: Any, symbol: str = "") -> str:
    return "crypto" if str(value or "").lower() == "crypto" or "/" in symbol else "stock"


def normalize_chart_timeframe(value: Any) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "", str(value or "1h").strip().lower())
    return clean[:8] or "1h"


def _finite_number(value: Any) -> float | int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (-1e12 < number < 1e12):
        return None
    return int(number) if number.is_integer() else number


def normalize_chart_settings(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    settings: dict[str, bool] = {}
    for key, enabled in list(value.items())[:MAX_SETTINGS]:
        clean_key = re.sub(r"[^a-zA-Z0-9 _-]+", "", str(key or ""))[:32]
        if clean_key:
            settings[clean_key] = bool(enabled)
    return settings


def normalize_chart_viewport(value: Any) -> dict[str, int]:
    """Validate a persisted time window without accepting arbitrary chart state."""

    if not isinstance(value, dict):
        return {}
    start = _finite_number(value.get("from"))
    end = _finite_number(value.get("to"))
    if start is None or end is None:
        return {}
    start_value = int(start)
    end_value = int(end)
    if start_value <= 0 or end_value <= start_value or end_value - start_value > 10 * 366 * 86400:
        return {}
    return {"from": start_value, "to": end_value}


def normalize_chart_drawing(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    tool = str(value.get("tool") or "").strip()
    if tool not in SUPPORTED_DRAWING_TOOLS:
        return None
    clean: dict[str, Any] = {"tool": tool, "version": 2}
    for key in ("time1", "time2", "price1", "price2", "offsetPrice", "level", "createdAt"):
        number = _finite_number(value.get(key))
        if number is not None:
            clean[key] = number
    for key in ("kind", "levelKind", "label", "color", "text"):
        text = re.sub(r"[<>]", "", " ".join(str(value.get(key) or "").split()))
        if text:
            clean[key] = text[:160]
    for key in ("snap", "systemPlan", "roxyPlanApplied"):
        if key in value:
            clean[key] = bool(value.get(key))
    if not any(key in clean for key in ("price1", "price2", "level")):
        return None
    return clean


def normalize_chart_drawings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    drawings: list[dict[str, Any]] = []
    for item in value[:MAX_DRAWINGS]:
        clean = normalize_chart_drawing(item)
        if clean is not None:
            drawings.append(clean)
    return drawings


class ChartStateStore:
    def __init__(self, path: str | Path = DEFAULT_CHART_STATE_PATH):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": CHART_STATE_SCHEMA_VERSION, "updated_at": _now_iso(), "users": {}}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("users"), dict):
            return self._empty()
        payload["schema_version"] = CHART_STATE_SCHEMA_VERSION
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = CHART_STATE_SCHEMA_VERSION
        payload["updated_at"] = _now_iso()
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _mutate(self, callback):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                self.lock_path.chmod(0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                result = callback(payload)
                self._write_unlocked(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _key(symbol: str, market: str, timeframe: str) -> str:
        return f"{market}:{symbol}:{timeframe}"

    def snapshot(self, user_id: Any, *, symbol: Any, market: Any, timeframe: Any) -> dict[str, Any]:
        clean_user = normalize_chart_user(user_id)
        clean_symbol = normalize_chart_symbol(symbol)
        clean_market = normalize_chart_market(market, clean_symbol)
        clean_timeframe = normalize_chart_timeframe(timeframe)
        payload = self._read_unlocked()
        users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
        user = users.get(clean_user) if isinstance(users.get(clean_user), dict) else {}
        states = user.get("states") if isinstance(user.get("states"), dict) else {}
        record = states.get(self._key(clean_symbol, clean_market, clean_timeframe))
        if not isinstance(record, dict):
            return {
                "status": "NO_DATA",
                "drawings": [],
                "settings": {},
                "viewport": {},
                "updated_at": "",
                "source": str(self.path),
            }
        return {
            "status": "READY",
            "drawings": normalize_chart_drawings(record.get("drawings")),
            "settings": normalize_chart_settings(record.get("settings")),
            "viewport": normalize_chart_viewport(record.get("viewport")),
            "updated_at": str(record.get("updated_at") or ""),
            "source": str(self.path),
        }

    def save(
        self,
        user_id: Any,
        *,
        symbol: Any,
        market: Any,
        timeframe: Any,
        drawings: Any,
        settings: Any,
        viewport: Any = None,
    ) -> dict[str, Any]:
        clean_user = normalize_chart_user(user_id)
        clean_symbol = normalize_chart_symbol(symbol)
        clean_market = normalize_chart_market(market, clean_symbol)
        clean_timeframe = normalize_chart_timeframe(timeframe)
        if not clean_symbol:
            return {"saved": False, "reason": "invalid_symbol"}
        clean_drawings = normalize_chart_drawings(drawings)
        clean_settings = normalize_chart_settings(settings)
        clean_viewport = normalize_chart_viewport(viewport)
        updated_at = _now_iso()

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            users = payload.setdefault("users", {})
            user = users.setdefault(clean_user, {"states": {}})
            states = user.setdefault("states", {})
            states[self._key(clean_symbol, clean_market, clean_timeframe)] = {
                "symbol": clean_symbol,
                "market": clean_market,
                "timeframe": clean_timeframe,
                "drawings": clean_drawings,
                "settings": clean_settings,
                "viewport": clean_viewport,
                "updated_at": updated_at,
            }
            return {
                "saved": True,
                "symbol": clean_symbol,
                "market": clean_market,
                "timeframe": clean_timeframe,
                "drawing_count": len(clean_drawings),
                "updated_at": updated_at,
            }

        return self._mutate(apply)
