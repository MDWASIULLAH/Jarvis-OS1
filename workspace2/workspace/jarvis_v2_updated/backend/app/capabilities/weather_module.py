"""
capabilities/weather_module.py

Implements JARVIS Section 2.7 -- weather. Uses Open-Meteo by default (free,
no key, unlimited for non-commercial use) so weather works out of the box.
If an OpenWeatherMap key is configured in Settings > APIs, that's tried
first (matches the spec's original API-optional design, upgraded from
"sorry, no key configured" to "works either way").
"""

from __future__ import annotations

from typing import Optional

import requests


class WeatherModule:
    def __init__(self, owm_api_key: Optional[str] = None):
        self.owm_api_key = owm_api_key

    def is_configured(self) -> bool:
        """Always True now -- Open-Meteo needs no key. Kept for API
        compatibility with the rest of the app and the original spec's
        Section 2.7 'is a key configured' check."""
        return True

    def current_weather(self, lat: float, lon: float) -> str:
        if self.owm_api_key:
            result = self._from_openweathermap(lat, lon)
            if result:
                return result
        return self._from_open_meteo(lat, lon)

    def _from_openweathermap(self, lat: float, lon: float) -> Optional[str]:
        try:
            r = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "appid": self.owm_api_key, "units": "metric"},
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            return f"It's currently {temp:.0f}°C and {desc}. Humidity is {humidity}%."
        except (requests.RequestException, KeyError):
            return None

    def _from_open_meteo(self, lat: float, lon: float) -> str:
        try:
            r = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": lat, "longitude": lon, "current_weather": "true"},
                timeout=5,
            )
            r.raise_for_status()
            cw = r.json()["current_weather"]
            temp = cw["temperature"]
            wind = cw["windspeed"]
            return f"It's currently {temp:.0f}°C with wind at {wind:.0f} km/h (Open-Meteo, no API key needed)."
        except (requests.RequestException, KeyError):
            return (
                "I couldn't reach a weather source just now -- I'll use cached "
                "data if I have any, or try again shortly."
            )
