"""
capabilities/smart_home.py

Home Assistant REST API client (Section 13.1). Needs a running Home
Assistant instance (the free, self-hosted kind) and a long-lived access
token (generate one from your HA user profile page).

Honest note: there's no Home Assistant instance reachable from this
sandbox, so this hasn't been tested live -- it follows HA's documented
REST API exactly, but you're the one who gets to run it for real, against
your own instance.
"""

from __future__ import annotations

import requests


class SmartHomeClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def call_service(self, domain: str, service: str, entity_id: str) -> bool:
        try:
            r = requests.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                headers=self.headers,
                json={"entity_id": entity_id},
                timeout=6,
            )
            return r.ok
        except requests.RequestException:
            return False

    def turn_on(self, entity_id: str) -> bool:
        return self.call_service(entity_id.split(".")[0], "turn_on", entity_id)

    def turn_off(self, entity_id: str) -> bool:
        return self.call_service(entity_id.split(".")[0], "turn_off", entity_id)
