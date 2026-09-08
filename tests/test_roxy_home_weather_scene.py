"""Model-driven Nexo atmosphere, isolated from people, radar and production data."""
from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from roxy_os.home_weather import _weather_number, _weather_valid_at, forecast_location, HomeWeatherConfig


ROOT = Path(__file__).resolve().parents[1]


def run_scene_test(script: str) -> None:
    source = (ROOT / "assets/roxy_list.js").read_text()
    start = source.index("  function familyWeatherMode()")
    end = source.index("  let familyWeatherRefreshTimer=", start)
    subprocess.run(["node", "-e", source[start:end] + script], check=True, capture_output=True, text=True)


@pytest.mark.parametrize("raw,current,expected", [
    ({"timezone": "America/New_York"}, {"time": "2026-09-08T12:15"}, "2026-09-08T16:15:00Z"),
    ({"timezone": "Asia/Tokyo"}, {"time": "2026-09-08T12:15"}, "2026-09-08T03:15:00Z"),
    ({"timezone": "America/New_York"}, {"time": "2026-01-08T12:15"}, "2026-01-08T17:15:00Z"),
    ({"utc_offset_seconds": -14400}, {"time": "2026-09-08T12:15"}, "2026-09-08T16:15:00Z"),
    ({}, {"time": "2026-09-08T12:15:00+02:00"}, "2026-09-08T10:15:00Z"),
    ({}, {"time": "2026-09-08T12:15"}, None),
    ({"timezone": "America/New_York"}, {"time": "bad"}, None),
])
def test_weather_model_time_is_unambiguous(raw, current, expected):
    assert _weather_valid_at(raw, current) == expected


@pytest.mark.parametrize("value", [None, "", "bad", float("nan"), float("inf"), True, -1])
def test_missing_or_invalid_precipitation_is_not_zero(value):
    assert _weather_number(value, minimum=0) is None
    assert _weather_number(0, minimum=0) == 0


def test_forecast_requests_and_preserves_atmosphere_measurements():
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs["params"])
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"timezone": "UTC", "current": {
                    "time": "2026-09-08T16:15", "interval": 900, "weather_code": 82,
                    "precipitation": 2.5, "rain": 1.2, "snowfall": 0,
                    "wind_speed_10m": 12, "wind_direction_10m": 270,
                    "cloud_cover": 92, "is_day": 0,
                }}
        return Response()

    result = forecast_location(44.123, -122.456, config=HomeWeatherConfig(forecast_url="https://weather-test.example/scene"), http_get=get)
    current = result["current"]
    assert current["valid_at"] == "2026-09-08T16:15:00Z"
    assert current["precipitation_mm"] == 2.5 and current["interval_seconds"] == 900
    assert current["cloud_cover_percent"] == 92 and current["wind_direction_degrees"] == 270
    assert current["temperature"] is None and current["feels_like"] is None
    assert current["is_day"] is False and current["source_kind"] == "weather_model"
    assert {"precipitation", "rain", "snowfall", "cloud_cover", "wind_direction_10m"} <= set(calls[0]["current"].split(","))


def test_freshness_never_relabels_stale_fetch_or_model_as_live():
    run_scene_test("""
const assert=require('node:assert/strict'),now=Date.parse('2026-09-08T16:30:00Z');
let homeWeather={status:'READY',updated_at:'2026-09-08T16:20:00Z',current:{valid_at:'2026-09-08T16:15:00Z',code:82,is_day:true}};
assert.equal(familyWeatherAtmosphere(now).mode,'rain');
for(const key of ['valid_at','updated_at']){
 const target=key==='valid_at'?homeWeather.current:homeWeather,original=target[key];
 for(const invalid of ['',null,'2026-09-08T16:15','2026-09-08T14:00:00Z','2026-09-08T18:00:00Z']){
   target[key]=invalid;assert.equal(familyWeatherAtmosphere(now).mode,'');
 }
 target[key]=original;
}
homeWeather.status='UNAVAILABLE';assert.equal(familyWeatherAtmosphere(now).fresh,false);
""")


def test_day_night_and_codes_do_not_invent_sun_snow_or_storm():
    run_scene_test("""
const assert=require('node:assert/strict');let homeWeather={status:'READY',current:{is_day:true}};
for(const code of [0,1]){homeWeather.current.code=code;assert.equal(familyWeatherMode(),'sunny');homeWeather.current.is_day=false;assert.equal(familyWeatherMode(),'clear-night');homeWeather.current.is_day=true;}
for(const [mode,codes] of Object.entries({rain:[51,53,55,56,57,61,63,65,66,67,80,81,82],snow:[71,73,75,77,85,86],storm:[95,96,99],fog:[45,48],'partly-cloudy':[2],cloudy:[3]})){
 for(const code of codes){homeWeather.current.code=code;assert.equal(familyWeatherMode(),mode);}
}
for(const code of [null,'',-1,4,52,54,58,59,60,62,64,51.5,100,NaN]){homeWeather.current.code=code;assert.equal(familyWeatherMode(),'');}
homeWeather.current={code:0,is_day:null};assert.equal(familyWeatherMode(),'');
""")


def test_precipitation_uses_its_interval_not_daily_rain_probability():
    run_scene_test("""
const assert=require('node:assert/strict'),now=Date.parse('2026-09-08T16:30:00Z');
let homeWeather={status:'READY',updated_at:'2026-09-08T16:20:00Z',daily:[{rain_probability:100}],current:{valid_at:'2026-09-08T16:15:00Z',code:61,is_day:true,precipitation_mm:.1,interval_seconds:900,wind_mph:20,wind_direction_degrees:270}};
const light=familyWeatherAtmosphere(now);assert(light.intensity<.3);assert(light.drift>0);
homeWeather.current.precipitation_mm=2;const heavy=familyWeatherAtmosphere(now);assert.equal(heavy.intensity,1);
homeWeather.current.wind_direction_degrees=90;assert(familyWeatherAtmosphere(now).drift<0);
homeWeather.current.wind_direction_degrees=null;assert.equal(familyWeatherAtmosphere(now).drift,0);
assert(familyWeatherParticles(heavy).length>familyWeatherParticles(light).length);
for(const particle of familyWeatherParticles(heavy)){assert(particle.length<17);assert(particle.size<1.1);assert(particle.opacity<.5);}
homeWeather.current.code=0;assert.equal(familyWeatherParticles(familyWeatherAtmosphere(now)).length,0);
""")


def test_scene_accessibility_source_and_refresh_contract():
    js = (ROOT / "assets/roxy_list.js").read_text()
    css = (ROOT / "assets/roxy_list.css").read_text()
    assert "family-lightning" not in css
    assert ".family-weather-fx i{display:none}" in css
    assert "animation-play-state:paused!important" in css
    assert "Visualización según Open-Meteo; no es radar." in js
    assert "Sin clima reciente: ambiente pausado. El mapa sigue disponible." in js
    refresh = js[js.index("  async function refreshFamilyWeatherIfNeeded()"):js.index("  function renderFamilyWeatherFx()")]
    assert "activePanel!=='family'||document.hidden" in refresh
    assert "!commerce.profile?.location_enabled" in refresh
    assert "300000" in refresh
    assert "requestedUser=user" in refresh and "user!==requestedUser" in refresh
    assert "method:'POST'" not in refresh and "getCurrentPosition" not in refresh
