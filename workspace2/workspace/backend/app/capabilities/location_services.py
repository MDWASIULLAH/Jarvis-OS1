"""
capabilities/location_services.py

Free, keyless location tools:
- geocode()       via OpenStreetMap Nominatim
- route_summary() via the public OSRM demo server (light/demo use only --
                   self-host OSRM for anything production-grade, per their
                   usage policy)
- ip_info()       via ip-api.com (free tier is HTTP-only and for
                   non-commercial use)
"""

from __future__ import annotations

from typing import Optional

import requests

_UA = {"User-Agent": "JARVIS-local-agent/1.0 (personal assistant project)"}


def geocode(place: str) -> Optional[dict]:
    """Returns {'lat':.., 'lon':.., 'display_name':..} or None if not found."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1},
            headers=_UA,
            timeout=5,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return None
        top = results[0]
        return {"lat": float(top["lat"]), "lon": float(top["lon"]), "display_name": top["display_name"]}
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def route_summary(start: tuple, end: tuple, profile: str = "driving") -> str:
    """start/end are (lat, lon) tuples. Uses the public OSRM demo server."""
    try:
        coords = f"{start[1]},{start[0]};{end[1]},{end[0]}"
        r = requests.get(
            f"https://router.project-osrm.org/route/v1/{profile}/{coords}",
            params={"overview": "false"},
            timeout=6,
        )
        r.raise_for_status()
        data = r.json()
        route = data["routes"][0]
        km = route["distance"] / 1000
        minutes = route["duration"] / 60
        return f"About {km:.1f} km, roughly {minutes:.0f} minutes by {profile}."
    except (requests.RequestException, KeyError, IndexError):
        return "I couldn't reach the routing service just now -- try again shortly."


def ip_info(ip: Optional[str] = None) -> Optional[dict]:
    """Looks up geolocation for an IP (or the caller's IP if None)."""
    try:
        url = f"http://ip-api.com/json/{ip or ''}"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return data if data.get("status") == "success" else None
    except requests.RequestException:
        return None


class LocationService:
    """Object wrapper the Brain Core calls as a tool.

    `geocode` returns a plain (lat, lon) tuple because that is what the
    weather provider takes, and `approximate_location` is IP-derived and
    labelled as approximate so the assistant never implies GPS access.
    """

    def geocode(self, place: str) -> Optional[tuple]:
        found = geocode(place)
        if not found:
            return None
        return (found["lat"], found["lon"], found["display_name"])

    def approximate_location(self) -> Optional[dict]:
        info = ip_info()
        if not info:
            return None
        return {
            "lat": info.get("lat"),
            "lon": info.get("lon"),
            "city": info.get("city") or info.get("regionName") or "your area",
            "country": info.get("country"),
            "accuracy": "approximate (IP-based, not GPS)",
        }
