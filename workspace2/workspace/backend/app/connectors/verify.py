"""
connectors/verify.py

Live credential checks.

Storing a token proves nothing, so every connector has a verifier that makes a
real authenticated call to the provider and reports what came back. A typo'd
token therefore fails at the moment you connect it -- in the Connectors panel,
where the fix is obvious -- rather than silently much later, mid-conversation.

Each verifier returns `(ok, message)` where the message is written for a human
and names the account or resource it reached whenever the provider tells us.
"""

from __future__ import annotations

import smtplib
from typing import Callable

import requests

TIMEOUT = 12
_UA = {"User-Agent": "JARVIS-Local-Assistant/2.0"}


def _fail(exc: Exception) -> tuple[bool, str]:
    if isinstance(exc, requests.Timeout):
        return False, "The provider did not respond in time. Try again."
    if isinstance(exc, requests.ConnectionError):
        return False, "Could not reach the provider. Check your connection or URL."
    return False, f"Verification failed: {exc}"


def _verify_gmail(creds: dict) -> tuple[bool, str]:
    address = (creds.get("address") or "").strip()
    password = (creds.get("app_password") or "").strip()
    password = password.replace(" ", "")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as smtp:
            smtp.login(address, password)
        return True, f"Signed in to Gmail as {address}."
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail rejected those credentials. Use a 16-character App Password "
            "(not your account password), with 2-step verification enabled."
        )
    except Exception as exc:
        return _fail(exc)


def _verify_github(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://api.github.com/user",
            headers={**_UA, "Authorization": f"Bearer {creds.get('token', '')}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected as @{r.json().get('login', 'unknown')}."
        if r.status_code == 401:
            return False, "GitHub rejected that token (401). It may be expired or mistyped."
        return False, f"GitHub returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_gitlab(creds: dict) -> tuple[bool, str]:
    base = (creds.get("base_url") or "https://gitlab.com").rstrip("/")
    try:
        r = requests.get(
            f"{base}/api/v4/user",
            headers={**_UA, "PRIVATE-TOKEN": creds.get("token", "")},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected to GitLab as @{r.json().get('username', 'unknown')}."
        if r.status_code == 401:
            return False, "GitLab rejected that token (401)."
        return False, f"GitLab returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_youtube(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": "test", "maxResults": 1,
                    "type": "video", "key": creds.get("api_key", "")},
            headers=_UA,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, "YouTube Data API key is valid."
        reason = ""
        try:
            reason = r.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        if r.status_code == 403:
            return False, reason or "Key rejected. Is the YouTube Data API v3 enabled?"
        return False, reason or f"YouTube returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_slack(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.post(
            "https://slack.com/api/auth.test",
            headers={**_UA, "Authorization": f"Bearer {creds.get('bot_token', '')}"},
            timeout=TIMEOUT,
        )
        data = r.json() if r.content else {}
        if data.get("ok"):
            return True, f"Connected to {data.get('team', 'Slack')} as {data.get('user', 'bot')}."
        return False, f"Slack rejected the token: {data.get('error', 'unknown error')}."
    except Exception as exc:
        return _fail(exc)


def _verify_telegram(creds: dict) -> tuple[bool, str]:
    token = (creds.get("bot_token") or "").strip()
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getMe", headers=_UA, timeout=TIMEOUT
        )
        data = r.json() if r.content else {}
        if data.get("ok"):
            return True, f"Connected to bot @{data.get('result', {}).get('username', '?')}."
        return False, f"Telegram rejected the token: {data.get('description', 'unknown error')}."
    except Exception as exc:
        return _fail(exc)


def _verify_discord(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers={**_UA, "Authorization": f"Bot {creds.get('bot_token', '')}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected as {r.json().get('username', 'bot')}."
        if r.status_code == 401:
            return False, "Discord rejected that bot token (401)."
        return False, f"Discord returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_home_assistant(creds: dict) -> tuple[bool, str]:
    base = (creds.get("base_url") or "").rstrip("/")
    try:
        r = requests.get(
            f"{base}/api/",
            headers={**_UA, "Authorization": f"Bearer {creds.get('token', '')}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, "Home Assistant API reachable and token accepted."
        if r.status_code in (401, 403):
            return False, "Home Assistant rejected that token."
        return False, f"Home Assistant returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_openweather(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": "London", "appid": creds.get("api_key", "")},
            headers=_UA,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, "OpenWeatherMap key is valid."
        if r.status_code == 401:
            return False, (
                "Key rejected. Newly created OpenWeatherMap keys can take a "
                "couple of hours to activate."
            )
        return False, f"OpenWeatherMap returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_newsapi(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"country": "us", "pageSize": 1, "apiKey": creds.get("api_key", "")},
            headers=_UA,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, "NewsAPI key is valid."
        reason = ""
        try:
            reason = r.json().get("message", "")
        except ValueError:
            pass
        return False, reason or f"NewsAPI returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_notion(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://api.notion.com/v1/users/me",
            headers={
                **_UA,
                "Authorization": f"Bearer {creds.get('api_key', '')}",
                "Notion-Version": "2022-06-28",
            },
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected to Notion as {r.json().get('name', 'user')}."
        return False, f"Notion returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_jira(creds: dict) -> tuple[bool, str]:
    domain = (creds.get("domain") or "").strip()
    email = (creds.get("email") or "").strip()
    token = (creds.get("api_token") or "").strip()
    try:
        r = requests.get(
            f"https://{domain}/rest/api/2/myself",
            auth=(email, token),
            headers=_UA,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected to Jira as {r.json().get('displayName', 'user')}."
        return False, f"Jira returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_trello(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://api.trello.com/1/members/me",
            params={"key": creds.get("api_key", ""), "token": creds.get("api_token", "")},
            headers=_UA,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected to Trello as {r.json().get('username', 'user')}."
        return False, f"Trello returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_spotify(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://api.spotify.com/v1/me",
            headers={**_UA, "Authorization": f"Bearer {creds.get('access_token', '')}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected to Spotify as {r.json().get('display_name', 'user')}."
        if r.status_code == 401:
            return False, "Spotify token expired or invalid. Re-authenticate."
        return False, f"Spotify returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_dropbox(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.post(
            "https://api.dropboxapi.com/2/users/get_current_account",
            headers={**_UA, "Authorization": f"Bearer {creds.get('access_token', '')}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected to Dropbox as {r.json().get('email', 'user')}."
        if r.status_code == 401:
            return False, "Dropbox token expired or invalid."
        return False, f"Dropbox returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_figma(creds: dict) -> tuple[bool, str]:
    try:
        r = requests.get(
            "https://api.figma.com/v1/me",
            headers={**_UA, "X-Figma-Token": creds.get("access_token", "")},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"Connected to Figma as {r.json().get('email', 'user')}."
        return False, f"Figma returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_openai_compatible(base_key: str, creds: dict, label: str) -> tuple[bool, str]:
    base = (creds.get(base_key) or "").rstrip("/")
    if not base:
        return False, "No endpoint URL provided."
    try:
        r = requests.get(
            f"{base}/models",
            headers={**_UA, "Authorization": f"Bearer {creds.get('api_key', '')}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return True, f"{label} endpoint reachable and key accepted."
        if r.status_code in (401, 403):
            return False, f"{label} rejected that API key."
        if r.status_code == 404:
            return False, (
                f"Reached the host but /models was not found. Check the base URL "
                f"includes the version path, e.g. https://api.openai.com/v1"
            )
        return False, f"{label} returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


def _verify_openrouter(creds: dict) -> tuple[bool, str]:
    api_key = (creds.get("api_key") or "").strip()
    if not api_key:
        return False, "No API key provided."
    try:
        r = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={**_UA, "Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            label = data.get("label") or "OpenRouter Key"
            return True, f"Connected to OpenRouter API key ({label})."
        if r.status_code in (401, 403):
            return False, "OpenRouter rejected that API key (invalid or expired)."
        r2 = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={**_UA, "Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        if r2.status_code == 200:
            return True, "OpenRouter API key verified successfully."
        return False, f"OpenRouter returned HTTP {r.status_code}."
    except Exception as exc:
        return _fail(exc)


VERIFIERS: dict[str, Callable[[dict], tuple[bool, str]]] = {
    "gmail": _verify_gmail,
    "github": _verify_github,
    "gitlab": _verify_gitlab,
    "youtube": _verify_youtube,
    "slack": _verify_slack,
    "telegram": _verify_telegram,
    "discord": _verify_discord,
    "home_assistant": _verify_home_assistant,
    "openweather": _verify_openweather,
    "newsapi": _verify_newsapi,
    "notion": _verify_notion,
    "jira": _verify_jira,
    "trello": _verify_trello,
    "spotify": _verify_spotify,
    "dropbox": _verify_dropbox,
    "figma": _verify_figma,
    "openrouter": _verify_openrouter,
    "image_api": lambda c: _verify_openai_compatible("api_url", c, "Image API"),
    "cloud_llm": lambda c: _verify_openai_compatible("base_url", c, "Cloud LLM"),
}


def verify(connector_id: str, creds: dict) -> tuple[bool, str]:
    verifier = VERIFIERS.get(connector_id)
    if verifier is None:
        return False, "No verification available for this connector."
    if not creds:
        return False, "Nothing is configured yet."
    return verifier(creds)
