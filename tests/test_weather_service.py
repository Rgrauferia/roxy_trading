import json
import time

from tools.weather_service import WeatherSnapshot
from tools.weather_service import fetch_current_weather


def test_fetch_current_weather_requires_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_WEATHER_API_KEY", raising=False)
    monkeypatch.delenv("ROXY_OPENWEATHER_API_KEY", raising=False)

    snapshot = fetch_current_weather("Miami,US", cache_path=tmp_path / "weather.json")

    assert snapshot.status == "missing_key"
    assert snapshot.location == "Miami,US"
    assert "OPENWEATHER_API_KEY" in snapshot.message


def test_fetch_current_weather_reads_fresh_cache(tmp_path):
    cache = tmp_path / "weather.json"
    cache.write_text(
        json.dumps(
            {
                "status": "ok",
                "query_location": "Miami,US",
                "location": "Miami, US",
                "description": "clear sky",
                "temperature_c": 29.4,
                "feels_like_c": 31.0,
                "humidity": 62,
                "wind_mps": 3.2,
                "source": "openweather",
                "observed_at": 1700000000,
                "fetched_at": time.time(),
            }
        ),
        encoding="utf-8",
    )

    snapshot = fetch_current_weather("Miami,US", api_key="not-used", cache_path=cache)

    assert isinstance(snapshot, WeatherSnapshot)
    assert snapshot.status == "ok"
    assert snapshot.location == "Miami, US"
    assert snapshot.temperature_c == 29.4

