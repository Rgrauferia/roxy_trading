from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from durable_storage import atomic_write_text


OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
DEFAULT_WEATHER_CACHE_PATH = Path("alerts/roxy_weather_cache.json")
DEFAULT_WEATHER_TTL_SECONDS = 600


@dataclass(frozen=True)
class WeatherSnapshot:
    status: str
    location: str
    description: str = ""
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity: int | None = None
    wind_mps: float | None = None
    source: str = "openweather"
    observed_at: int | None = None
    fetched_at: float | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "location": self.location,
            "description": self.description,
            "temperature_c": self.temperature_c,
            "feels_like_c": self.feels_like_c,
            "humidity": self.humidity,
            "wind_mps": self.wind_mps,
            "source": self.source,
            "observed_at": self.observed_at,
            "fetched_at": self.fetched_at,
            "message": self.message,
        }


def weather_api_key() -> str:
    return (
        os.getenv("OPENWEATHER_API_KEY")
        or os.getenv("OPEN_WEATHER_API_KEY")
        or os.getenv("ROXY_OPENWEATHER_API_KEY")
        or ""
    ).strip()


def default_weather_location() -> str:
    return (os.getenv("ROXY_DEFAULT_WEATHER_LOCATION") or "New York,US").strip()


def fetch_current_weather(
    location: str | None = None,
    *,
    api_key: str | None = None,
    cache_path: Path = DEFAULT_WEATHER_CACHE_PATH,
    ttl_seconds: int = DEFAULT_WEATHER_TTL_SECONDS,
    timeout_seconds: int = 8,
) -> WeatherSnapshot:
    location_text = (location or default_weather_location()).strip() or "New York,US"
    key = (api_key if api_key is not None else weather_api_key()).strip()
    if not key:
        return WeatherSnapshot(
            status="missing_key",
            location=location_text,
            source="openweather",
            message="Set OPENWEATHER_API_KEY to enable live weather.",
        )

    cached = _read_cached_weather(cache_path, location_text, ttl_seconds)
    if cached:
        return cached

    params = urlencode({"q": location_text, "appid": key, "units": "metric"})
    url = f"{OPENWEATHER_CURRENT_URL}?{params}"
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return WeatherSnapshot(
            status="error",
            location=location_text,
            source="openweather",
            message=f"{type(exc).__name__}: {exc}",
        )

    snapshot = _snapshot_from_openweather(payload, location_text)
    _write_cached_weather(cache_path, snapshot, location_text)
    return snapshot


def _snapshot_from_openweather(payload: dict[str, Any], fallback_location: str) -> WeatherSnapshot:
    weather_items = payload.get("weather") if isinstance(payload.get("weather"), list) else []
    weather = weather_items[0] if weather_items and isinstance(weather_items[0], dict) else {}
    main = payload.get("main") if isinstance(payload.get("main"), dict) else {}
    wind = payload.get("wind") if isinstance(payload.get("wind"), dict) else {}
    name = str(payload.get("name") or fallback_location).strip()
    sys_payload = payload.get("sys") if isinstance(payload.get("sys"), dict) else {}
    country = str(sys_payload.get("country") or "").strip()
    location = f"{name}, {country}" if country and country not in name else name
    return WeatherSnapshot(
        status="ok",
        location=location or fallback_location,
        description=str(weather.get("description") or "").strip(),
        temperature_c=_float_or_none(main.get("temp")),
        feels_like_c=_float_or_none(main.get("feels_like")),
        humidity=_int_or_none(main.get("humidity")),
        wind_mps=_float_or_none(wind.get("speed")),
        source="openweather",
        observed_at=_int_or_none(payload.get("dt")),
        fetched_at=time.time(),
    )


def _read_cached_weather(cache_path: Path, location: str, ttl_seconds: int) -> WeatherSnapshot | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    fetched_at = _float_or_none(payload.get("fetched_at"))
    if fetched_at is None or time.time() - fetched_at > max(0, ttl_seconds):
        return None
    if str(payload.get("query_location") or "").lower() != location.lower():
        return None
    return WeatherSnapshot(
        status=str(payload.get("status") or "ok"),
        location=str(payload.get("location") or location),
        description=str(payload.get("description") or ""),
        temperature_c=_float_or_none(payload.get("temperature_c")),
        feels_like_c=_float_or_none(payload.get("feels_like_c")),
        humidity=_int_or_none(payload.get("humidity")),
        wind_mps=_float_or_none(payload.get("wind_mps")),
        source=str(payload.get("source") or "openweather_cache"),
        observed_at=_int_or_none(payload.get("observed_at")),
        fetched_at=fetched_at,
        message=str(payload.get("message") or ""),
    )


def _write_cached_weather(cache_path: Path, snapshot: WeatherSnapshot, query_location: str) -> None:
    if snapshot.status != "ok":
        return
    payload = snapshot.as_dict()
    payload["query_location"] = query_location
    atomic_write_text(json.dumps(payload, indent=2, sort_keys=True), cache_path)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
