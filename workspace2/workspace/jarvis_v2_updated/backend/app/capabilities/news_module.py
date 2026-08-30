"""
capabilities/news_module.py v2

Enhanced news module with real-time news for:
- Technology, AI, Sports, Finance, Politics, Weather, Entertainment
- Regional news (India, US, UK, etc.)
- Daily briefing functionality
- Multiple source aggregation
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import requests

RSS_FEEDS = {
    "top": "https://news.google.com/rss",
    "technology": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY",
    "ai": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
    "sports": "https://news.google.com/rss/headlines/section/topic/SPORTS",
    "business": "https://news.google.com/rss/headlines/section/topic/BUSINESS",
    "finance": "https://news.google.com/rss/headlines/section/topic/BUSINESS",
    "politics": "https://news.google.com/rss/headlines/section/topic/NATION",
    "entertainment": "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT",
    "health": "https://news.google.com/rss/headlines/section/topic/HEALTH",
    "science": "https://news.google.com/rss/headlines/section/topic/SCIENCE",
    "world": "https://news.google.com/rss/headlines/section/topic/WORLD",
    "india": "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
    "us": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "uk": "https://news.google.com/rss?hl=en-GB&gl=GB&ceid=GB:en",
}

CATEGORIES = {
    "tech": "technology", "technology": "technology", "ai": "ai",
    "artificial intelligence": "ai", "sports": "sports", "sport": "sports",
    "business": "business", "finance": "finance", "money": "finance",
    "politics": "politics", "political": "politics",
    "entertainment": "entertainment", "movies": "entertainment",
    "health": "health", "medical": "health",
    "science": "science", "research": "science",
    "world": "world", "global": "world", "international": "world",
    "india": "india", "indian": "india",
}

TOPIC_ALIASES = {
    "daily brief": "top", "daily briefing": "top", "briefing": "top",
    "morning brief": "top", "today's news": "top", "what's happening": "top",
}


@dataclass
class NewsItem:
    title: str
    source: str
    link: str
    category: str = ""


class NewsModule:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def headlines(self, topic: str = "top", limit: int = 5) -> list[NewsItem]:
        topic = topic.lower().strip()
        topic = TOPIC_ALIASES.get(topic, topic)
        topic = CATEGORIES.get(topic, topic)

        if self.is_configured():
            return self._from_news_api(topic, limit)
        return self._from_rss(topic, limit)

    def _from_news_api(self, topic: str, limit: int) -> list[NewsItem]:
        try:
            params = {"apiKey": self.api_key, "pageSize": limit, "language": "en"}
            if topic in ("technology", "sports", "business", "entertainment", "health", "science"):
                params["category"] = topic
                url = "https://newsapi.org/v2/top-headlines"
            else:
                params["q"] = topic
                url = "https://newsapi.org/v2/everything"
            r = requests.get(url, params=params, timeout=5)
            r.raise_for_status()
            articles = r.json().get("articles", [])
            return [
                NewsItem(title=a["title"], source=a["source"]["name"], link=a["url"], category=topic)
                for a in articles[:limit]
            ]
        except requests.RequestException:
            return self._from_rss(topic, limit)

    def _from_rss(self, topic: str, limit: int) -> list[NewsItem]:
        url = RSS_FEEDS.get(topic, RSS_FEEDS["top"])
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            items = []
            for item in root.findall(".//item")[:limit]:
                title = item.findtext("title") or "Untitled"
                source_el = item.find("source")
                source = source_el.text if source_el is not None else "Google News"
                link = item.findtext("link") or ""
                items.append(NewsItem(title=title, source=source, link=link, category=topic))
            return items
        except (requests.RequestException, ET.ParseError):
            return []

    def summarize(self, topic: str = "top", limit: int = 5) -> str:
        items = self.headlines(topic, limit)
        if not items:
            return "I couldn't reach a news source just now -- try again shortly."
        header = f"**{'Top' if topic == 'top' else topic.title()} News** ({len(items)} headlines)"
        lines = [f"{i + 1}. {it.title} — *{it.source}*" for i, it in enumerate(items)]
        return header + "\n" + "\n".join(lines)

    def daily_briefing(self) -> str:
        """Generate a comprehensive daily briefing across all categories."""
        sections = [
            ("Top Stories", self.headlines("top", 3)),
            ("Technology", self.headlines("technology", 2)),
            ("Sports", self.headlines("sports", 2)),
            ("Business", self.headlines("business", 2)),
        ]
        parts = ["# JARVIS Daily Briefing\n"]
        for label, items in sections:
            if not items:
                continue
            parts.append(f"## {label}")
            for i, item in enumerate(items, 1):
                parts.append(f"{i}. {item.title} — *{item.source}*")
            parts.append("")
        return "\n".join(parts) if len(parts) > 1 else "No news available at this time."
