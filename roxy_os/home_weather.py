from __future__ import annotations

import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import requests


WMO_CONDITIONS: dict[int, tuple[str, str, str]] = {
    0: ("Despejado", "sunny", "☀️"),
    1: ("Mayormente despejado", "partly_cloudy_day", "🌤️"),
    2: ("Parcialmente nublado", "partly_cloudy_day", "⛅"),
    3: ("Nublado", "cloud", "☁️"),
    45: ("Niebla", "foggy", "🌫️"),
    48: ("Niebla con escarcha", "foggy", "🌫️"),
    51: ("Llovizna ligera", "rainy_light", "🌦️"),
    53: ("Llovizna", "rainy", "🌦️"),
    55: ("Llovizna intensa", "rainy", "🌧️"),
    56: ("Llovizna helada", "weather_hail", "🌧️"),
    57: ("Llovizna helada intensa", "weather_hail", "🌧️"),
    61: ("Lluvia ligera", "rainy_light", "🌦️"),
    63: ("Lluvia", "rainy", "🌧️"),
    65: ("Lluvia intensa", "rainy", "🌧️"),
    66: ("Lluvia helada", "weather_hail", "🌧️"),
    67: ("Lluvia helada intensa", "weather_hail", "🌧️"),
    71: ("Nieve ligera", "weather_snowy", "🌨️"),
    73: ("Nieve", "weather_snowy", "🌨️"),
    75: ("Nieve intensa", "weather_snowy", "❄️"),
    77: ("Granos de nieve", "weather_snowy", "🌨️"),
    80: ("Chubascos ligeros", "rainy_light", "🌦️"),
    81: ("Chubascos", "rainy", "🌧️"),
    82: ("Chubascos intensos", "rainy", "🌧️"),
    85: ("Chubascos de nieve", "weather_snowy", "🌨️"),
    86: ("Chubascos de nieve intensos", "weather_snowy", "❄️"),
    95: ("Tormentas", "thunderstorm", "⛈️"),
    96: ("Tormentas con granizo", "thunderstorm", "⛈️"),
    99: ("Tormentas fuertes con granizo", "thunderstorm", "⛈️"),
}

SPANISH_WEEKDAYS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}


def _plain(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return normalized.encode("ascii", "ignore").decode("ascii").lower().strip()


def _https_url(value: str, *, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{label} debe usar una URL HTTPS segura.")
    return value.rstrip("/")


@dataclass(frozen=True)
class HomeWeatherConfig:
    forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    api_key: str = ""
    timeout_seconds: float = 10.0
    cache_seconds: int = 900

    @classmethod
    def from_env(cls) -> "HomeWeatherConfig":
        return cls(
            forecast_url=_https_url(
                os.getenv("ROXY_HOME_WEATHER_API_URL", cls.forecast_url),
                label="ROXY_HOME_WEATHER_API_URL",
            ),
            geocoding_url=_https_url(
                os.getenv("ROXY_HOME_WEATHER_GEOCODING_URL", cls.geocoding_url),
                label="ROXY_HOME_WEATHER_GEOCODING_URL",
            ),
            api_key=os.getenv("ROXY_HOME_WEATHER_API_KEY", "").strip(),
            timeout_seconds=max(2.0, min(float(os.getenv("ROXY_HOME_WEATHER_TIMEOUT_SECONDS", "10")), 30.0)),
            cache_seconds=max(60, min(int(os.getenv("ROXY_HOME_WEATHER_CACHE_SECONDS", "900")), 3600)),
        )


_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def _cached(key: str, ttl: int) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        row = _CACHE.get(key)
        if row and time.time() - row[0] <= ttl:
            return row[1]
        if row:
            _CACHE.pop(key, None)
    return None


def _remember(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), payload)
    return payload


def condition_for_code(value: Any) -> dict[str, Any]:
    try:
        code = int(value)
    except (TypeError, ValueError):
        code = -1
    label, icon, emoji = WMO_CONDITIONS.get(code, ("Condiciones variables", "partly_cloudy_day", "🌤️"))
    return {"code": code, "condition": label, "icon": icon, "emoji": emoji}


def geocode_place(
    query: str,
    *,
    config: HomeWeatherConfig | None = None,
    http_get: Any = requests.get,
) -> dict[str, Any] | None:
    config = config or HomeWeatherConfig.from_env()
    cleaned = " ".join(str(query or "").split())[:120]
    if len(cleaned) < 2:
        return None
    params: dict[str, Any] = {"name": cleaned, "count": 5, "language": "es", "format": "json"}
    if config.api_key:
        params["apikey"] = config.api_key
    response = http_get(config.geocoding_url, params=params, timeout=config.timeout_seconds)
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        return None
    row = results[0]
    label = ", ".join(
        part for part in (str(row.get("name") or ""), str(row.get("admin1") or "")) if part
    )
    return {
        "label": label or cleaned,
        "latitude": round(float(row["latitude"]), 3),
        "longitude": round(float(row["longitude"]), 3),
        "timezone": str(row.get("timezone") or "auto"),
        "country": str(row.get("country") or ""),
    }


def _hourly_best_window(hourly: dict[str, Any], day_key: str) -> dict[str, Any] | None:
    times = hourly.get("time") or []
    rain = hourly.get("precipitation_probability") or []
    temperatures = hourly.get("temperature_2m") or []
    candidates: list[tuple[int, int, float]] = []
    for index, raw_time in enumerate(times):
        if not str(raw_time).startswith(day_key):
            continue
        try:
            hour = int(str(raw_time)[11:13])
            chance = int(rain[index] if index < len(rain) and rain[index] is not None else 0)
            temp = float(temperatures[index] if index < len(temperatures) and temperatures[index] is not None else 0)
        except (TypeError, ValueError):
            continue
        if 7 <= hour <= 20:
            candidates.append((chance, hour, temp))
    if not candidates:
        return None
    chance, hour, temp = min(candidates, key=lambda row: (row[0], abs(row[2] - 74), row[1]))
    suffix = "a. m." if hour < 12 else "p. m."
    display_hour = hour if 1 <= hour <= 12 else abs(hour - 12) or 12
    return {"hour": hour, "label": f"{display_hour}:00 {suffix}", "rain_probability": chance, "temperature": round(temp)}


def forecast_location(
    latitude: float,
    longitude: float,
    *,
    label: str = "Tu ubicación",
    days: int = 16,
    timezone_name: str = "auto",
    config: HomeWeatherConfig | None = None,
    http_get: Any = requests.get,
) -> dict[str, Any]:
    config = config or HomeWeatherConfig.from_env()
    latitude = round(float(latitude), 3)
    longitude = round(float(longitude), 3)
    days = max(1, min(int(days), 16))
    cache_key = f"{config.forecast_url}|{latitude}|{longitude}|{days}|{timezone_name}"
    cached = _cached(cache_key, config.cache_seconds)
    if cached is not None:
        return {**cached, "cached": True}
    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_name or "auto",
        "forecast_days": days,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "current": "temperature_2m,apparent_temperature,is_day,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,sunrise,sunset",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
    }
    if config.api_key:
        params["apikey"] = config.api_key
    response = http_get(config.forecast_url, params=params, timeout=config.timeout_seconds)
    response.raise_for_status()
    raw = response.json()
    current_raw = raw.get("current") or {}
    current_condition = condition_for_code(current_raw.get("weather_code"))
    current = {
        **current_condition,
        "temperature": round(float(current_raw.get("temperature_2m") or 0)),
        "feels_like": round(float(current_raw.get("apparent_temperature") or 0)),
        "wind_mph": round(float(current_raw.get("wind_speed_10m") or 0)),
        "is_day": bool(current_raw.get("is_day", 1)),
        "observed_at": str(current_raw.get("time") or ""),
    }
    daily_raw = raw.get("daily") or {}
    daily: list[dict[str, Any]] = []
    for index, day_key in enumerate(daily_raw.get("time") or []):
        def value(name: str, default: Any = 0) -> Any:
            values = daily_raw.get(name) or []
            return values[index] if index < len(values) and values[index] is not None else default

        chance = int(value("precipitation_probability_max"))
        code = value("weather_code", -1)
        row = {
            "date": str(day_key),
            **condition_for_code(code),
            "temperature_max": round(float(value("temperature_2m_max"))),
            "temperature_min": round(float(value("temperature_2m_min"))),
            "rain_probability": chance,
            "wind_max_mph": round(float(value("wind_speed_10m_max"))),
            "sunrise": str(value("sunrise", "")),
            "sunset": str(value("sunset", "")),
            "outdoor_rating": "poor" if int(code) >= 95 or chance >= 70 else "caution" if chance >= 35 else "good",
        }
        row["best_outdoor_window"] = _hourly_best_window(raw.get("hourly") or {}, str(day_key))
        daily.append(row)
    payload = {
        "status": "READY",
        "provider": "open_meteo",
        "location": {"label": label, "latitude": latitude, "longitude": longitude},
        "timezone": str(raw.get("timezone") or timezone_name or "auto"),
        "units": {"temperature": "°F", "wind": "mph"},
        "current": current,
        "daily": daily,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "cached": False,
        "notice": "Pronóstico orientativo. Confirma las alertas oficiales antes de actividades sensibles.",
    }
    return _remember(cache_key, payload)


def weather_for_profile(
    profile: dict[str, Any],
    *,
    days: int = 16,
    config: HomeWeatherConfig | None = None,
    http_get: Any = requests.get,
) -> dict[str, Any]:
    if not profile.get("location_enabled") or profile.get("latitude") is None or profile.get("longitude") is None:
        return {
            "status": "LOCATION_REQUIRED",
            "message": "Activa tu ubicación aproximada en el perfil para ver el clima local.",
            "daily": [],
        }
    label = str(profile.get("locality") or profile.get("postal_code") or "Tu ubicación")
    return forecast_location(
        float(profile["latitude"]),
        float(profile["longitude"]),
        label=label,
        days=days,
        config=config,
        http_get=http_get,
    )


def requested_weather_date(text: str, *, today: date | None = None) -> date:
    today = today or date.today()
    plain = _plain(text)
    if "pasado manana" in plain:
        return today + timedelta(days=2)
    if "manana" in plain:
        return today + timedelta(days=1)
    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", plain)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    for name, weekday in SPANISH_WEEKDAYS.items():
        if re.search(rf"\b{name}\b", plain):
            delta = (weekday - today.weekday()) % 7
            if delta == 0 and re.search(r"\b(proximo|siguiente)\b", plain):
                delta = 7
            return today + timedelta(days=delta)
    return today


def requested_weather_place(text: str) -> str:
    plain = " ".join(str(text or "").strip().split())
    patterns = (
        r"(?i)\b(?:ir|viajar|voy|vamos|visitar|estar(?:e|emos)?)\s+(?:a|para|en)\s+(.+?)(?=\s+(?:hoy|mañana|manana|este|esta|el|la|que|qué|cual|cuál|si|probabilidad|posibilidad|va\s+a|habra|habrá|hara|hará)\b|[,.?]|$)",
        r"(?i)\b(?:clima|tiempo|pronostico|pronóstico|lluvia|temperatura)\s+(?:en|para|de)\s+(.+?)(?=\s+(?:hoy|mañana|manana|este|esta|el|la|que|qué|cual|cuál|si|probabilidad|posibilidad|va\s+a|habra|habrá|hara|hará)\b|[,.?]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, plain)
        if match:
            candidate = match.group(1).strip(" .?¿!¡")
            if 2 <= len(candidate) <= 120:
                return candidate
    return ""


def answer_weather_query(
    text: str,
    profile: dict[str, Any],
    *,
    today: date | None = None,
    config: HomeWeatherConfig | None = None,
    http_get: Any = requests.get,
) -> dict[str, Any]:
    config = config or HomeWeatherConfig.from_env()
    place_query = requested_weather_place(text)
    if place_query:
        location = geocode_place(place_query, config=config, http_get=http_get)
        if location is None:
            return {"status": "PLACE_NOT_FOUND", "message": f"No encontré {place_query}. Dime la ciudad y el estado para precisar.", "daily": []}
        forecast = forecast_location(
            location["latitude"], location["longitude"], label=location["label"],
            days=16, timezone_name=location["timezone"], config=config, http_get=http_get,
        )
    else:
        forecast = weather_for_profile(profile, days=16, config=config, http_get=http_get)
    if forecast.get("status") != "READY":
        return forecast
    target = requested_weather_date(text, today=today)
    selected = next((row for row in forecast.get("daily") or [] if row.get("date") == target.isoformat()), None)
    if selected is None:
        return {
            **forecast,
            "status": "OUT_OF_RANGE",
            "target_date": target.isoformat(),
            "message": "Esa fecha está fuera del pronóstico disponible. Puedo revisarla cuando falten 16 días o menos.",
        }
    location_label = forecast.get("location", {}).get("label") or "tu ubicación"
    chance = int(selected.get("rain_probability") or 0)
    window = selected.get("best_outdoor_window") or {}
    recommendation = (
        "No la elegiría para una actividad exterior sin un plan alternativo."
        if selected.get("outdoor_rating") == "poor"
        else "Lleva un plan alternativo por si cambia el tiempo."
        if selected.get("outdoor_rating") == "caution"
        else "En principio se ve como un buen día para estar afuera."
    )
    message = (
        f"Para {location_label}, el {target.strftime('%d/%m')} se espera {str(selected.get('condition') or '').lower()}, "
        f"entre {selected.get('temperature_min')} y {selected.get('temperature_max')} grados Fahrenheit, con {chance}% de probabilidad de lluvia. "
        f"{recommendation}"
    )
    if window and chance >= 20:
        message += f" La ventana con menor riesgo se aproxima a las {window.get('label')}."
    return {**forecast, "selected_day": selected, "target_date": target.isoformat(), "message": message}
