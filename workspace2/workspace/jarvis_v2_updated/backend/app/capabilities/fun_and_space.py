"""
capabilities/fun_and_space.py

Free, mostly-keyless extras:
- astronomy_picture_of_the_day() via NASA's API (DEMO_KEY works out of the
  box, shared and rate-limited -- get your own free key at api.nasa.gov for
  higher limits)
- space_news()                  via the Spaceflight News API (fully keyless)
- top_tech_news()                via the Hacker News Firebase API (fully keyless)
- qr_code_url()                  via the GoQR API (fully keyless, returns an
  image URL -- no request needed until it's actually rendered)
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

import requests


def astronomy_picture_of_the_day(nasa_api_key: Optional[str] = None) -> Optional[dict]:
    try:
        r = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params={"api_key": nasa_api_key or "DEMO_KEY"},
            timeout=6,
        )
        r.raise_for_status()
        data = r.json()
        return {"title": data.get("title"), "explanation": data.get("explanation"), "url": data.get("url")}
    except requests.RequestException:
        return None


def space_news(limit: int = 5) -> list:
    try:
        r = requests.get(
            "https://api.spaceflightnewsapi.net/v4/articles",
            params={"limit": limit},
            timeout=6,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return [{"title": a["title"], "url": a["url"], "source": a["news_site"]} for a in results[:limit]]
    except (requests.RequestException, KeyError):
        return []


def top_tech_news(limit: int = 5) -> list:
    try:
        ids_resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5)
        ids_resp.raise_for_status()
        ids = ids_resp.json()[:limit]
        items = []
        for story_id in ids:
            item_resp = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5)
            item = item_resp.json()
            if item:
                items.append({"title": item.get("title"), "url": item.get("url"), "score": item.get("score")})
        return items
    except requests.RequestException:
        return []


def qr_code_url(data: str, size: int = 200) -> str:
    """Returns a direct image URL -- no request needed until it's rendered."""
    return f"https://api.qrserver.com/v1/create-qr-code/?size={size}x{size}&data={quote(data)}"
