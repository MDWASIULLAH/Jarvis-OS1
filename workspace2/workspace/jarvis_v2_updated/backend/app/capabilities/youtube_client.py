"""
capabilities/youtube_client.py

YouTube Data API v3 client (Section 13). Needs a free API key from Google
Cloud Console (enable "YouTube Data API v3" -- the free quota is generous
for personal use).

Honest note: googleapis.com isn't reachable from this sandbox's network, so
this hasn't been tested live the way github_client.py was -- it follows the
official documented endpoint and response shape exactly, but you're the one
who gets to run it for real, with your own key.
"""

from __future__ import annotations

import requests


class YouTubeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_videos(self, query: str, limit: int = 5) -> list:
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "q": query, "type": "video", "maxResults": limit, "key": self.api_key},
                timeout=6,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            return [
                {
                    "title": it["snippet"]["title"],
                    "channel": it["snippet"]["channelTitle"],
                    "url": f"https://youtube.com/watch?v={it['id']['videoId']}",
                }
                for it in items
            ]
        except requests.RequestException:
            return []
