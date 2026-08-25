from __future__ import annotations

from datetime import date

from roxy_os.home_weather import (
    HomeWeatherConfig,
    answer_weather_query,
    condition_for_code,
    forecast_location,
    requested_weather_date,
    requested_weather_place,
    weather_for_profile,
)
from tools.roxy_home_service import _assistant_shopping_intent


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_weather_condition_and_natural_request_parsing() -> None:
    assert condition_for_code(95)["condition"] == "Tormentas"
    assert requested_weather_date("¿Lloverá este domingo?", today=date(2026, 8, 24)) == date(2026, 8, 30)
    assert requested_weather_place(
        "Roxy, este domingo quiero ir a Daytona Beach, ¿qué probabilidad de lluvia hay?"
    ) == "Daytona Beach"
    assert _assistant_shopping_intent("¿Qué probabilidad de lluvia hay en Daytona Beach el domingo?") == "weather_query"


def test_profile_requires_explicit_location_consent() -> None:
    result = weather_for_profile({"location_enabled": False, "latitude": 29.0, "longitude": -81.0})
    assert result["status"] == "LOCATION_REQUIRED"
    assert result["daily"] == []


def test_forecast_is_normalized_and_finds_outdoor_window() -> None:
    calls: list[dict] = []

    def fake_get(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse(
            {
                "timezone": "America/New_York",
                "current": {
                    "time": "2026-08-24T12:00",
                    "temperature_2m": 84.4,
                    "apparent_temperature": 88.1,
                    "is_day": 1,
                    "weather_code": 2,
                    "wind_speed_10m": 8.2,
                },
                "daily": {
                    "time": ["2026-08-24"],
                    "weather_code": [61],
                    "temperature_2m_max": [88.2],
                    "temperature_2m_min": [74.2],
                    "precipitation_probability_max": [45],
                    "wind_speed_10m_max": [15.5],
                    "sunrise": ["2026-08-24T07:00"],
                    "sunset": ["2026-08-24T19:55"],
                },
                "hourly": {
                    "time": ["2026-08-24T09:00", "2026-08-24T15:00"],
                    "temperature_2m": [80, 87],
                    "precipitation_probability": [10, 45],
                    "weather_code": [1, 61],
                },
            }
        )

    config = HomeWeatherConfig(api_key="server-secret", cache_seconds=60)
    result = forecast_location(29.2111, -81.0228, label="Daytona Beach, Florida", config=config, http_get=fake_get)
    assert result["status"] == "READY"
    assert result["current"]["temperature"] == 84
    assert result["daily"][0]["rain_probability"] == 45
    assert result["daily"][0]["best_outdoor_window"]["label"] == "9:00 a. m."
    assert calls[0]["params"]["apikey"] == "server-secret"
    assert "server-secret" not in result


def test_destination_query_uses_geocoding_then_forecast() -> None:
    def fake_get(url: str, **kwargs):
        if "geocoding" in url:
            return FakeResponse(
                {"results": [{"name": "Daytona Beach", "admin1": "Florida", "country": "Estados Unidos", "latitude": 29.21, "longitude": -81.02, "timezone": "America/New_York"}]}
            )
        return FakeResponse(
            {
                "timezone": "America/New_York",
                "current": {"time": "2026-08-24T12:00", "temperature_2m": 82, "apparent_temperature": 86, "is_day": 1, "weather_code": 1, "wind_speed_10m": 7},
                "daily": {
                    "time": ["2026-08-30"], "weather_code": [2], "temperature_2m_max": [85], "temperature_2m_min": [75],
                    "precipitation_probability_max": [20], "wind_speed_10m_max": [12],
                    "sunrise": ["2026-08-30T07:00"], "sunset": ["2026-08-30T19:45"],
                },
                "hourly": {"time": ["2026-08-30T10:00"], "temperature_2m": [81], "precipitation_probability": [10], "weather_code": [1]},
            }
        )

    result = answer_weather_query(
        "Este domingo quiero ir a Daytona Beach, ¿qué probabilidad de lluvia hay?",
        {},
        today=date(2026, 8, 24),
        config=HomeWeatherConfig(cache_seconds=60),
        http_get=fake_get,
    )
    assert result["status"] == "READY"
    assert result["location"]["label"] == "Daytona Beach, Florida"
    assert result["selected_day"]["rain_probability"] == 20
    assert "20% de probabilidad de lluvia" in result["message"]


def test_weather_ui_and_server_route_are_connected() -> None:
    html = open("assets/roxy_list.html", encoding="utf-8").read()
    script = open("assets/roxy_list.js", encoding="utf-8").read()
    service = open("tools/roxy_home_service.py", encoding="utf-8").read()
    assert 'id="todayWeatherCard"' in html
    assert 'id="calendarWeatherCard"' in html
    assert "/v1/home-weather/" in script
    assert "weatherForDay" in script
    assert "captureCommerceLocation(true)" in script
    assert "Ubicación aproximada guardada. Roxy ya está cargando el clima real." in script
    assert '@app.get("/v1/home-weather/{user_id}")' in service
