"""
capabilities/github_client.py

Implements Section 2.11's GitHub integration for real, against GitHub's
actual REST API. Works unauthenticated for public data (rate-limited to
60 requests/hour per IP); pass a personal access token for 5,000/hour and
private-repo access.
"""

from __future__ import annotations

from typing import Optional

import requests


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get_repo(self, owner: str, repo: str) -> Optional[dict]:
        try:
            r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=self.headers, timeout=6)
            r.raise_for_status()
            data = r.json()
            return {
                "full_name": data["full_name"],
                "description": data.get("description"),
                "stars": data["stargazers_count"],
                "language": data.get("language"),
                "url": data["html_url"],
            }
        except requests.RequestException:
            return None

    def list_recent_commits(self, owner: str, repo: str, limit: int = 5) -> list:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                headers=self.headers,
                params={"per_page": limit},
                timeout=6,
            )
            r.raise_for_status()
            return [
                {
                    "sha": c["sha"][:7],
                    "message": c["commit"]["message"].splitlines()[0],
                    "author": c["commit"]["author"]["name"],
                }
                for c in r.json()[:limit]
            ]
        except requests.RequestException:
            return []

    def search_repos(self, query: str, limit: int = 5) -> list:
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                headers=self.headers,
                params={"q": query, "per_page": limit},
                timeout=6,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            return [{"full_name": it["full_name"], "stars": it["stargazers_count"], "url": it["html_url"]} for it in items[:limit]]
        except requests.RequestException:
            return []
