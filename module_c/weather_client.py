"""
weather_client.py — Module C: live weather forecast integration.

HONESTY NOTE (keep in docs/pitch): calling OpenWeatherMap requires an API
key (free tier available at openweathermap.org). Without one configured,
this module returns a clearly-labeled MOCK forecast so the rest of the
pipeline (intensity scoring, threshold recalibration) remains fully
demonstrable -- exactly the same "real interface, honest placeholder when
a credential/dataset isn't available" pattern used for Module A's symbol
detector. The heat index calculation itself is real and always runs on
whatever temperature/humidity numbers are available (live or mock).
"""

import os
import math
from dataclasses import dataclass

import requests

OPENWEATHERMAP_BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"


@dataclass
class WeatherForecast:
    temperature_c: float
    humidity_pct: float
    heat_index_c: float
    heat_index_category: str
    is_mock_data: bool
    source_note: str


def _heat_index_celsius(temp_c: float, humidity_pct: float) -> float:
    """
    Computes heat index using the NWS Rothfusz regression -- the standard
    formula (same one used by meteorological services). OpenWeatherMap's
    API doesn't return heat index directly, so this is a real calculation
    performed on whatever temperature/humidity values are available.
    """
    temp_f = temp_c * 9 / 5 + 32
    rh = humidity_pct

    if temp_f < 80:
        # Rothfusz regression is only valid/meaningful above ~80F;
        # below that, heat index ~= actual temperature.
        hi_f = temp_f
    else:
        hi_f = (
            -42.379 + 2.04901523 * temp_f + 10.14333127 * rh
            - 0.22475541 * temp_f * rh - 0.00683783 * temp_f ** 2
            - 0.05481717 * rh ** 2 + 0.00122874 * temp_f ** 2 * rh
            + 0.00085282 * temp_f * rh ** 2 - 0.00000199 * temp_f ** 2 * rh ** 2
        )

    return round((hi_f - 32) * 5 / 9, 1)


def _heat_index_category(heat_index_c: float) -> str:
    if heat_index_c < 27:
        return "low"
    elif heat_index_c < 32:
        return "caution"
    elif heat_index_c < 41:
        return "extreme_caution"
    elif heat_index_c < 54:
        return "danger"
    else:
        return "extreme_danger"


def get_weather_forecast(lat: float, lon: float, api_key: str | None = None) -> WeatherForecast:
    """
    Fetches the current/near-term forecast for a location. Falls back to
    a clearly-labeled mock forecast if no API key is configured or the
    request fails -- never silently pretends mock data is real.

    api_key: if None, reads from the OPENWEATHERMAP_API_KEY environment
    variable. Get a free key at https://openweathermap.org/api.
    """
    api_key = api_key or os.environ.get("OPENWEATHERMAP_API_KEY")

    if not api_key:
        return _mock_forecast("No OPENWEATHERMAP_API_KEY configured -- returning mock forecast. "
                               "Set the environment variable or pass api_key= to use live data.")

    try:
        resp = requests.get(
            OPENWEATHERMAP_BASE_URL,
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric", "cnt": 1},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        main = data["list"][0]["main"]
        temp_c = float(main["temp"])
        humidity_pct = float(main["humidity"])
    except Exception as e:
        return _mock_forecast(f"Live weather API call failed ({type(e).__name__}: {e}) -- "
                               f"returning mock forecast.")

    heat_index_c = _heat_index_celsius(temp_c, humidity_pct)
    return WeatherForecast(
        temperature_c=temp_c,
        humidity_pct=humidity_pct,
        heat_index_c=heat_index_c,
        heat_index_category=_heat_index_category(heat_index_c),
        is_mock_data=False,
        source_note="Live OpenWeatherMap forecast.",
    )


def _mock_forecast(reason: str) -> WeatherForecast:
    """Reasonable illustrative values for a hot Indian afternoon event
    (matches the Karur case study's conditions) -- clearly labeled as
    mock, never presented as real."""
    temp_c, humidity_pct = 38.0, 55.0
    heat_index_c = _heat_index_celsius(temp_c, humidity_pct)
    return WeatherForecast(
        temperature_c=temp_c,
        humidity_pct=humidity_pct,
        heat_index_c=heat_index_c,
        heat_index_category=_heat_index_category(heat_index_c),
        is_mock_data=True,
        source_note=reason,
    )
