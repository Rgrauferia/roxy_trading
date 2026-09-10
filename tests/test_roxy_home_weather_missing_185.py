"""Missing/invalid model data must not become a sunny, dry or zero-degree claim."""
from copy import deepcopy
from datetime import date

import pytest

from roxy_os import home_weather as weather


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(weather, "_CACHE", {})


def raw_forecast():
    return {
        "timezone": "UTC",
        "current": {"time": "2026-09-10T12:00", "weather_code": 3, "is_day": 1},
        "daily": {"time": ["2026-09-10"], "weather_code": [3], "temperature_2m_max": [80],
                  "temperature_2m_min": [60], "precipitation_probability_max": [10], "wind_speed_10m_max": [8]},
        "hourly": {"time": ["2026-09-10T09:00", "2026-09-10T15:00"], "weather_code": [3, 3],
                   "temperature_2m": [70, 79], "precipitation_probability": [10, 30]},
    }


def fetch(raw):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return deepcopy(raw)
    return lambda *_args, **_kwargs: Response()


def normalized(raw):
    return weather.forecast_location(28.0, -81.0, http_get=fetch(raw))


@pytest.mark.parametrize("value", [True, False, None, "", " ", "bad", 95.9, "95.9", float("nan"), float("inf"), -1, 4, 100, [], {}, 10**500])
def test_invalid_condition_never_becomes_sun_or_thunder(value):
    result = weather.condition_for_code(value)
    assert result == {"code": -1, "condition": "Condición no disponible", "icon": "help_outline", "emoji": ""}


@pytest.mark.parametrize("value", [0, "0", 0.0, 95, "95", 95.0])
def test_exact_supported_codes_remain_supported(value):
    assert weather.condition_for_code(value)["code"] == int(value)


@pytest.mark.parametrize("bad", [None, [], "invalid", {}])
def test_missing_or_malformed_current_and_daily_are_not_false_zero(bad):
    raw = raw_forecast(); raw["current"] = bad; raw["daily"] = bad
    result = normalized(raw)
    assert result["daily"] == []
    assert result["current"]["temperature"] is None
    assert result["current"]["code"] == -1
    assert result["current"]["is_day"] is None


def test_missing_daily_arrays_keep_day_but_unknown_measurements():
    raw = raw_forecast(); raw["daily"] = {"time": ["2026-09-10"]}; raw["hourly"] = {}
    day = normalized(raw)["daily"][0]
    for key in ("temperature_min", "temperature_max", "wind_max_mph", "rain_probability", "sunrise", "sunset", "best_outdoor_window"):
        assert day[key] is None
    assert day["outdoor_rating"] == "unknown"
    assert day["code"] == -1 and day["emoji"] == ""


@pytest.mark.parametrize("bad", [None, True, False, "", "bad", float("nan"), float("inf"), -1, 101, 10**500])
def test_invalid_daily_rain_is_unknown_not_dry(bad):
    raw = raw_forecast(); raw["daily"]["precipitation_probability_max"] = [bad]
    day = normalized(raw)["daily"][0]
    assert day["rain_probability"] is None
    assert day["outdoor_rating"] == "unknown"


def test_zero_temperature_zero_wind_and_zero_probability_are_real_values():
    raw = raw_forecast()
    for key in ("temperature_2m_max", "temperature_2m_min", "precipitation_probability_max", "wind_speed_10m_max"):
        raw["daily"][key] = [0]
    day = normalized(raw)["daily"][0]
    assert all(day[key] == 0 for key in ("temperature_max", "temperature_min", "rain_probability", "wind_max_mph"))
    assert day["outdoor_rating"] == "good"


def test_inverted_temperature_bounds_are_not_silently_swapped():
    raw = raw_forecast(); raw["daily"]["temperature_2m_max"] = [60]; raw["daily"]["temperature_2m_min"] = [80]
    day = normalized(raw)["daily"][0]
    assert day["temperature_min"] is None and day["temperature_max"] is None
    assert day["outdoor_rating"] == "unknown"


def test_known_storm_or_high_rain_still_warn_when_other_fields_missing():
    raw = raw_forecast(); raw["daily"] = {"time": ["2026-09-10", "2026-09-11"], "weather_code": [95, None], "precipitation_probability_max": [None, 90]}
    days = normalized(raw)["daily"]
    assert [day["outdoor_rating"] for day in days] == ["poor", "poor"]


@pytest.mark.parametrize("field", ["precipitation_probability", "temperature_2m", "weather_code"])
def test_missing_hourly_measurement_does_not_win_best_window(field):
    hourly = raw_forecast()["hourly"]; hourly[field][0] = None
    result = weather._hourly_best_window(hourly, "2026-09-10")
    assert result["hour"] == 15
    hourly[field][1] = None
    assert weather._hourly_best_window(hourly, "2026-09-10") is None


@pytest.mark.parametrize("bad", [None, True, False, -1, 101, "bad", float("nan"), float("inf")])
def test_invalid_hourly_probability_not_selected_as_zero(bad):
    hourly = raw_forecast()["hourly"]; hourly["precipitation_probability"][0] = bad
    assert weather._hourly_best_window(hourly, "2026-09-10")["hour"] == 15


def test_known_hourly_storm_cannot_be_called_best_window_with_low_rain():
    hourly = raw_forecast()["hourly"]; hourly["weather_code"][0] = 95; hourly["precipitation_probability"][0] = 0
    assert weather._hourly_best_window(hourly, "2026-09-10")["hour"] == 15


def test_hourly_time_validation_and_minutes_are_preserved():
    hourly = raw_forecast()["hourly"]; hourly["time"] = ["2026-09-10-invalid-09", "2026-09-10T15:30"]
    result = weather._hourly_best_window(hourly, "2026-09-10")
    assert result["label"] == "3:30 p. m."
    assert weather._hourly_best_window({"time": "2026-09-10T09:00"}, "2026-09-10") is None


def test_bad_dates_and_wrong_array_shapes_do_not_crash_or_invent_days():
    raw = raw_forecast(); raw["daily"]["time"] = [None, "bad", "2026-99-10", "2026-09-10"]
    raw["daily"]["temperature_2m_max"] = "80"; raw["daily"]["weather_code"] = {"3": 99}
    days = normalized(raw)["daily"]
    assert len(days) == 1 and days[0]["date"] == "2026-09-10"
    assert days[0]["temperature_max"] is None and days[0]["code"] == -1


@pytest.mark.parametrize("day", [True, False, "1", "0", 2, None])
def test_invalid_is_day_does_not_become_a_sunny_scene(day):
    raw = raw_forecast(); raw["current"]["is_day"] = day
    assert normalized(raw)["current"]["is_day"] is None


def test_missing_values_are_spoken_as_unavailable_not_zero_or_good_day():
    raw = raw_forecast(); raw["daily"] = {"time": ["2026-09-10"]}; raw["hourly"] = {}
    result = weather.answer_weather_query("clima hoy", {"location_enabled": True, "latitude": 28, "longitude": -81}, today=date(2026, 9, 10), http_get=fetch(raw))
    message = result["message"]
    assert "temperatura no disponible" in message
    assert "probabilidad de lluvia no disponible" in message
    assert "Faltan datos" in message
    assert "0%" not in message and "None" not in message and "buen día" not in message


def test_unknown_one_temperature_is_not_spoken_as_none_or_dropped():
    raw = raw_forecast(); raw["daily"]["temperature_2m_min"] = [None]
    message = weather.answer_weather_query("clima hoy", {"location_enabled": True, "latitude": 28, "longitude": -81}, today=date(2026, 9, 10), http_get=fetch(raw))["message"]
    assert "máxima de 80 grados Fahrenheit; mínima no disponible" in message
    assert "None" not in message and "buen día" not in message
