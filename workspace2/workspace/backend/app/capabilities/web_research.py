"""
capabilities/web_research.py

Keyless factual retrieval and page extraction.

Sources, in the order the Decision Engine prefers them:

1. Wikipedia REST API  -- summaries, images, and full page text. Keyless,
   stable, generous rate limits, and a citable source URL.
2. DuckDuckGo Instant Answer -- short direct answers (already used by
   `knowledge_apis.quick_answer`), useful when a query is not an article
   title.
3. DuckDuckGo HTML results -- titles/snippets/links for open-ended queries.
   This is scraping, so it is best-effort and clearly marked as such.

Everything degrades to an honest "couldn't reach it" string rather than
raising, because a research failure must never take down a chat turn.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

import requests

USER_AGENT = "JARVIS-Local-Assistant/2.0 (personal local assistant; contact: local user)"
_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en"}
TIMEOUT = 12


def _get(url: str, **kwargs) -> requests.Response:
    """GET with one short retry on throttling.

    Wikipedia returns 429 under bursts of requests. Without a retry that
    surfaced to the user as "no matching article" -- a transient throttle
    was indistinguishable from a genuine knowledge gap.
    """
    kwargs.setdefault("headers", _HEADERS)
    kwargs.setdefault("timeout", TIMEOUT)
    response = requests.get(url, **kwargs)
    if response.status_code in (429, 503):
        time.sleep(1.5)
        response = requests.get(url, **kwargs)
    return response


@dataclass
class Article:
    title: str
    summary: str
    url: str
    thumbnail: Optional[str] = None
    source: str = "wikipedia"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "thumbnail": self.thumbnail,
            "source": self.source,
        }


# ------------------------------------------------------------- wikipedia

def wikipedia_search(query: str, limit: int = 5) -> list[dict]:
    try:
        response = _get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
            },
        )
        response.raise_for_status()
        results = response.json().get("query", {}).get("search", [])
        return [
            {
                "title": item.get("title", ""),
                "snippet": re.sub(r"<[^>]+>", "", html.unescape(item.get("snippet", ""))),
                "url": f"https://en.wikipedia.org/wiki/{quote(item.get('title', '').replace(' ', '_'))}",
            }
            for item in results
        ]
    except (requests.RequestException, ValueError):
        return []


_QUESTION_PREAMBLE = re.compile(
    r"^(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?"
    r"(?:tell\s+me\s+(?:about|who|what)\s*|what(?:'s|\s+is|\s+are|\s+was|\s+were)\s*|"
    r"who(?:'s|\s+is|\s+are|\s+was|\s+were)\s*|where\s+is\s*|when\s+(?:is|was)\s*|"
    r"how\s+(?:tall|big|old|long|far|high)\s+(?:is|are|was)\s*|"
    r"give\s+me\s+|look\s+up\s+|search\s+for\s+|define\s+)"
    r"(?:the\s+|a\s+|an\s+)?",
    re.IGNORECASE,
)


def _search_subject(question: str) -> str:
    """Strip conversational scaffolding so the search sees the actual subject.

    Wikipedia's full-text search ranks on the whole string, so leaving the
    question intact actively misleads it: "what is the capital of Japan"
    returns "Capital punishment in Japan" as the top hit (both "capital" and
    "Japan" score heavily), while "capital of Japan" correctly returns
    "Capital of Japan".
    """
    subject = _QUESTION_PREAMBLE.sub("", question.strip(), count=1)
    subject = subject.strip().rstrip("?.!").strip()
    return subject or question.strip()


def _relevance(title: str, subject: str) -> float:
    """Fraction of the subject's content words present in the candidate title."""
    stop = {"the", "a", "an", "of", "in", "is", "was", "for", "to", "and", "on"}
    want = {w for w in re.findall(r"[a-z0-9]+", subject.lower()) if w not in stop}
    if not want:
        return 0.0
    have = set(re.findall(r"[a-z0-9]+", title.lower()))
    return len(want & have) / len(want)


def wikipedia_summary(topic: str) -> Optional[Article]:
    """Summary for `topic`; falls back to the best search hit for the title."""
    title = topic.strip()
    subject = _search_subject(title)
    # Try the subject as a literal page title first, since an exact article
    # match beats anything full-text search will rank.
    candidates: list[str] = [subject]
    if title != subject:
        candidates.append(title)
    candidates.append("")  # sentinel: fall back to scored search hits
    for candidate in candidates:
        if not candidate:
            # Score several hits against the subject instead of blindly
            # trusting hits[0], which is how "capital of Japan" ended up
            # answered with the death penalty.
            hits = wikipedia_search(subject, limit=5)
            if not hits:
                return None
            best = max(hits, key=lambda h: _relevance(h["title"], subject))
            candidate = best["title"]
        try:
            response = _get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(candidate.replace(' ', '_'))}"
            )
            if response.status_code != 200:
                continue
            payload = response.json()
            if payload.get("type", "").endswith("disambiguation"):
                continue
            extract = (payload.get("extract") or "").strip()
            if not extract:
                continue
            return Article(
                title=payload.get("title", candidate),
                summary=extract,
                url=(payload.get("content_urls", {}).get("desktop", {}) or {}).get(
                    "page", f"https://en.wikipedia.org/wiki/{quote(candidate)}"
                ),
                thumbnail=(payload.get("originalimage") or payload.get("thumbnail") or {}).get("source"),
            )
        except (requests.RequestException, ValueError):
            continue
    return None


def wikipedia_page_images(topic: str, limit: int = 6) -> list[dict]:
    """Real image URLs from a Wikipedia article, largest thumbnails first."""
    try:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "images",
                "titles": topic,
                "gimlimit": limit * 3,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": 900,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        pages = (response.json().get("query", {}) or {}).get("pages", {}) or {}
    except (requests.RequestException, ValueError):
        return []

    images: list[dict] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        url = info.get("thumburl") or info.get("url")
        if not url or not mime.startswith("image/") or mime == "image/svg+xml":
            continue
        title = page.get("title", "").replace("File:", "")
        if re.search(r"(icon|logo|commons|wiki|edit|symbol|flag_of|ambox|question_book)", title, re.I):
            continue
        metadata = info.get("extmetadata") or {}
        credit = re.sub(r"<[^>]+>", "", html.unescape(str(metadata.get("Artist", {}).get("value", ""))))[:120]
        images.append(
            {
                "url": url,
                "media_type": mime,
                "caption": title.rsplit(".", 1)[0].replace("_", " "),
                "width": info.get("thumbwidth") or info.get("width"),
                "height": info.get("thumbheight") or info.get("height"),
                "source": "wikimedia",
                "credit": credit,
                "source_url": info.get("descriptionurl", ""),
            }
        )
    images.sort(key=lambda i: (i.get("width") or 0) * (i.get("height") or 0), reverse=True)
    return images[:limit]


def commons_search_images(query: str, limit: int = 6) -> list[dict]:
    """Wikimedia Commons full-text image search -- broader than one article."""
    try:
        response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"filetype:bitmap {query}",
                "gsrnamespace": 6,
                "gsrlimit": limit * 2,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": 900,
                "format": "json",
            },
            headers=_HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        pages = (response.json().get("query", {}) or {}).get("pages", {}) or {}
    except (requests.RequestException, ValueError):
        return []

    images: list[dict] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        mime = info.get("mime", "")
        if not url or not mime.startswith("image/") or mime == "image/svg+xml":
            continue
        images.append(
            {
                "url": url,
                "media_type": mime,
                "caption": page.get("title", "").replace("File:", "").rsplit(".", 1)[0].replace("_", " "),
                "width": info.get("thumbwidth") or info.get("width"),
                "height": info.get("thumbheight") or info.get("height"),
                "source": "wikimedia_commons",
                "source_url": info.get("descriptionurl", ""),
            }
        )
    return images[:limit]


def openverse_search_images(query: str, limit: int = 6) -> list[dict]:
    """Openverse: ~700M openly-licensed images, keyless for anonymous use."""
    try:
        response = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": limit, "license_type": "all"},
            headers=_HEADERS,
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            return []
        results = response.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []
    images: list[dict] = []
    for item in results:
        url = item.get("url")
        if not url:
            continue
        images.append(
            {
                "url": url,
                "media_type": f"image/{(item.get('filetype') or 'jpeg').lower().replace('jpg', 'jpeg')}",
                "caption": item.get("title") or query,
                "width": item.get("width"),
                "height": item.get("height"),
                "source": f"openverse:{item.get('source', 'unknown')}",
                "credit": item.get("creator") or "",
                "source_url": item.get("foreign_landing_url") or url,
            }
        )
    return images[:limit]


# ------------------------------------------------------- generic web pages

_SCRIPT_RE = re.compile(r"<(script|style|noscript|svg|head)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r"<img[^>]+>", re.I)
_ATTR_RE = re.compile(r"([a-zA-Z\-:]+)\s*=\s*[\"']([^\"']*)[\"']")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def _absolute(base: str, candidate: str) -> str:
    if candidate.startswith("//"):
        return f"{urlparse(base).scheme}:{candidate}"
    return urljoin(base, candidate)


def extract_page(url: str, max_chars: int = 6000, max_images: int = 8) -> dict:
    """Fetch a URL and return its readable text plus discovered image URLs.

    This is the "read a website / extract images from the page" capability.
    It is plain HTML parsing, not a headless browser, so JavaScript-rendered
    pages return little text -- the result says so instead of pretending.
    """
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        response = requests.get(url, headers=_HEADERS, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type and "xml" not in content_type:
            return {
                "url": response.url,
                "title": url,
                "text": f"(the URL returned {content_type or 'a non-HTML response'}, so there is no page text to read)",
                "images": [],
                "chars": 0,
                "truncated": False,
                "ok": False,
            }
        markup = response.text
    except requests.RequestException as exc:
        return {"url": url, "title": url, "text": f"(could not load the page: {exc})", "images": [], "chars": 0, "truncated": False, "ok": False}

    title_match = _TITLE_RE.search(markup)
    title = html.unescape(_TAG_RE.sub("", title_match.group(1)).strip()) if title_match else url

    images: list[dict] = []
    seen: set[str] = set()
    for tag in _IMG_RE.findall(markup)[:120]:
        attributes = dict(_ATTR_RE.findall(tag))
        source = (
            attributes.get("src")
            or attributes.get("data-src")
            or (attributes.get("srcset", "").split(" ")[0] if attributes.get("srcset") else "")
        )
        if not source or source.startswith("data:"):
            continue
        absolute = _absolute(response.url, source)
        if absolute in seen or not re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", absolute, re.I):
            continue
        seen.add(absolute)
        images.append(
            {
                "url": absolute,
                "caption": html.unescape(attributes.get("alt", "") or title)[:160],
                "media_type": "image/jpeg",
                "source": urlparse(response.url).netloc,
                "source_url": response.url,
            }
        )
        if len(images) >= max_images:
            break

    body = _SCRIPT_RE.sub(" ", markup)
    body = re.sub(r"<(br|/p|/div|/li|/h[1-6])[^>]*>", "\n", body, flags=re.I)
    text = html.unescape(_TAG_RE.sub(" ", body))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    # `chars` is what the page actually held; callers (and the audit trail) need it
    # to tell "this page is thin" from "we truncated a long page".
    return {
        "url": response.url,
        "title": title,
        "text": text[:max_chars],
        "images": images,
        "chars": len(text),
        "truncated": len(text) > max_chars,
        "ok": bool(text),
    }


def web_results(query: str, limit: int = 5) -> list[dict]:
    """Best-effort general web results (DuckDuckGo HTML endpoint)."""
    try:
        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=_HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        markup = response.text
    except requests.RequestException:
        return []

    results: list[dict] = []
    pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'(?:class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>)?',
        re.S | re.I,
    )
    for match in pattern.finditer(markup):
        link, title, snippet = match.group(1), match.group(2), match.group(3) or ""
        clean_title = html.unescape(_TAG_RE.sub("", title)).strip()
        if not clean_title:
            continue
        results.append(
            {
                "title": clean_title,
                "url": html.unescape(link),
                "snippet": html.unescape(_TAG_RE.sub("", snippet)).strip()[:300],
            }
        )
        if len(results) >= limit:
            break
    return results


def download(url: str, max_bytes: int = 8_000_000) -> Optional[tuple[bytes, str]]:
    """Stream a binary down with a hard size cap."""
    try:
        with requests.get(url, headers=_HEADERS, timeout=TIMEOUT, stream=True) as response:
            response.raise_for_status()
            media_type = response.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(65536):
                total += len(chunk)
                if total > max_bytes:
                    return None
                chunks.append(chunk)
            return b"".join(chunks), media_type
    except requests.RequestException:
        return None
