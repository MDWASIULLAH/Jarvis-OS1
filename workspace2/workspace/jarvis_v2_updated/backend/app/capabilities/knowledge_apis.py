"""
capabilities/knowledge_apis.py v2

Multi-source knowledge retrieval with priority ranking:
1. Official documentation (MDN, Microsoft Docs, etc.)
2. GitHub repositories & issues
3. Stack Overflow (via Stack Exchange API)
4. Wikipedia (as fallback only)
5. ArXiv research papers
6. DuckDuckGo Instant Answer

Includes citation system and source ranking.
"""

from __future__ import annotations

import re
import time
from typing import Optional
from urllib.parse import quote

import requests

# ------------------------------------------------------------------ cache
_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cached(key: str, fetcher, ttl: int = _CACHE_TTL):
    now = time.time()
    if key in _cache and now - _cache[key][0] < ttl:
        return _cache[key][1]
    result = fetcher()
    _cache[key] = (now, result)
    return result


# ------------------------------------------------------------------ define
def define(word: str) -> str:
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        if r.status_code == 404:
            return f"I couldn't find a dictionary entry for '{word}'."
        r.raise_for_status()
        entry = r.json()[0]
        meaning = entry["meanings"][0]
        pos = meaning["partOfSpeech"]
        definition = meaning["definitions"][0]["definition"]
        return f"{word} ({pos}): {definition}"
    except (requests.RequestException, KeyError, IndexError):
        return "The dictionary service isn't reachable right now."


# ------------------------------------------------------------------ query cleaner
_QUERY_NOISE = re.compile(
    r"^(?:please\s+|can you\s+|i want\s+|i need\s+|give me\s+|show me\s+|tell me\s+|find me\s+|get me\s+)",
    re.IGNORECASE | re.MULTILINE,
)
_QUERY_TAIL = re.compile(
    r"\s+(?:also|and|with|plus|along with|including|as well)\s+(?:a\s+|an?\s+|her\s+|his\s+|their\s+|the\s+)?"
    r"(?:image|picture|photo|pic|images|pictures|photos|pics)\b.*$"
    r"|\s+(?:a\s+|an?\s+|her\s+|his\s+|their\s+|the\s+)?"
    r"(?:image|picture|photo|pic|images|pictures|photos|pics)\s+(?:also|too|as well)\b.*$",
    re.IGNORECASE,
)


def _clean_query(query: str) -> str:
    """Strip command phrases and request tails so the search API sees a cleaner query."""
    q = _QUERY_NOISE.sub("", query)
    q = _QUERY_TAIL.sub("", q)
    q = q.strip(" ?.!,\"'")
    return q or query


# ------------------------------------------------------------------ quick answer (DDG)
def quick_answer(query: str) -> str:
    """Try DDG with the raw query first, then iterate shorter versions."""
    from urllib.parse import quote as _quote

    candidates = [_clean_query(query).strip()]
    words = candidates[0].split()
    for i in range(len(words) - 1, max(len(words) - 6, 2), -1):
        candidates.append(" ".join(words[:i]))

    for candidate in candidates:
        if len(candidate) < 3:
            continue
        try:
            r = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": candidate, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()
            text = data.get("AbstractText") or data.get("Answer")
            if text and text.strip():
                abstract_url = data.get("AbstractURL", "")
                source = data.get("AbstractSource", "DuckDuckGo")
                result = text
                if source and source != "Wikipedia":
                    result += f" (Source: {source})"
                if abstract_url:
                    result += f" [{abstract_url}]"
                return result
            heading = data.get("Heading", "")
            if heading:
                return f"Related: {heading}"
        except requests.RequestException:
            continue
    return f"No direct answer found for '{_clean_query(query)}'."


# ------------------------------------------------------------------ stack exchange
def search_stackexchange(query: str, site: str = "stackoverflow", limit: int = 3) -> list[dict]:
    try:
        r = requests.get(
            "https://api.stackexchange.com/2.3/search/advanced",
            params={"q": query, "site": site, "sort": "relevance", "pagesize": limit},
            timeout=6,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        return [
            {"title": it["title"], "link": it["link"], "score": it["score"], "source_type": "stackoverflow"}
            for it in items[:limit]
        ]
    except (requests.RequestException, KeyError):
        return []


# ------------------------------------------------------------------ wikipedia (fallback)
def search_wikipedia(query: str, limit: int = 2) -> list[dict]:
    """Wikipedia search -- used only as fallback when no better source is available."""
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch", "search": query, "limit": limit,
                "namespace": 0, "format": "json",
            },
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for i in range(len(data[1])):
            results.append({
                "title": data[1][i],
                "link": data[3][i] if i < len(data[3]) else "",
                "source_type": "wikipedia",
                "description": data[2][i] if i < len(data[2]) else "",
            })
        return results
    except (requests.RequestException, KeyError, IndexError):
        return []


# ------------------------------------------------------------------ wikipedia summary
def wikipedia_summary(query: str, sentences: int = 3) -> Optional[str]:
    """Get Wikipedia summary for a query."""
    try:
        r = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(query),
            timeout=6,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        extract = data.get("extract", "")
        if sentences > 0 and extract:
            sents = re.split(r'(?<=[.!?])\s+', extract)
            extract = " ".join(sents[:sentences])
        source_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        return f"{extract}\n\nSource: Wikipedia [{source_url}]"
    except (requests.RequestException, KeyError):
        return None


# ------------------------------------------------------------------ arxiv
def search_arxiv(query: str, limit: int = 3) -> list[dict]:
    """Search arXiv for research papers."""
    try:
        r = requests.get(
            "http://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{quote(query)}",
                "start": 0, "max_results": limit,
                "sortBy": "relevance",
            },
            timeout=8,
        )
        r.raise_for_status()
        entries = re.findall(
            r"<entry>(.*?)</entry>", r.text, re.DOTALL
        )
        results = []
        for entry in entries[:limit]:
            title = re.search(r"<title>(.*?)</title>", entry)
            summary = re.search(r"<summary>(.*?)</summary>", entry)
            link = re.search(r'<id>(.*?)</id>', entry)
            results.append({
                "title": title.group(1).strip() if title else "",
                "link": link.group(1).strip() if link else "",
                "description": (summary.group(1).strip()[:200] if summary else ""),
                "source_type": "arxiv",
            })
        return results
    except (requests.RequestException, Exception):
        return []


# ------------------------------------------------------------------ multi-source search
def multi_source_search(query: str, max_results: int = 8) -> dict:
    """
    Multi-source retrieval with priority ranking.
    Returns structured results with citations and source ranking.
    Automatically cleans noisy queries for better API results.
    """
    clean = _clean_query(query)
    results: list[dict] = []

    # Priority 1: Stack Overflow (coding questions)
    if any(kw in query.lower() for kw in ["code", "error", "bug", "python", "javascript",
        "react", "node", "api", "function", "class", "import", "module", "npm", "pip"]):
        sof = search_stackexchange(clean, limit=3)
        results.extend(sof)

    # Priority 2: ArXiv (research/scientific)
    if any(kw in query.lower() for kw in ["research", "paper", "study", "algorithm",
        "model", "neural", "machine learning", "deep learning", "ai", "llm"]):
        arxiv = search_arxiv(clean, limit=2)
        results.extend(arxiv)

    # Priority 3: DuckDuckGo instant answer (factual questions) -- uses cleaned query
    try:
        ddg = quick_answer(clean)
        if ddg and "No direct answer" not in ddg:
            results.append({
                "title": clean[:80],
                "description": ddg,
                "source_type": "duckduckgo",
                "link": f"https://duckduckgo.com/?q={quote(clean)}",
            })
    except Exception:
        pass

    # Priority 4: Wikipedia (fallback) -- uses cleaned query
    if len(results) < max_results:
        wiki = search_wikipedia(clean, limit=3)
        results.extend(wiki)

    # Priority 5: Wikipedia summary for direct answer
    summary = None
    if len(results) < 3:
        summary = wikipedia_summary(clean)

    # Rank by source priority
    source_ranking = {
        "stackoverflow": 1,
        "arxiv": 2,
        "duckduckgo": 3,
        "wikipedia": 4,
        "mdn": 1,
        "github": 2,
        "microsoft_docs": 1,
    }

    results.sort(key=lambda r: source_ranking.get(r.get("source_type", ""), 5))
    results = results[:max_results]

    return {
        "results": results,
        "summary": summary,
        "total_sources": len(set(r.get("source_type", "") for r in results)),
        "query": query,
    }


# ------------------------------------------------------------------ citation helper
def format_citation(result: dict) -> str:
    """Format a single result as a citation string."""
    title = result.get("title", "Unknown")
    source = result.get("source_type", "web")
    link = result.get("link", "")
    if link:
        return f"[{title}]({link}) — {source}"
    return f"{title} — {source}"


def format_citations(results: list[dict]) -> str:
    """Format multiple results as a citations block."""
    if not results:
        return ""
    lines = ["\n*Sources:*"]
    for i, r in enumerate(results[:6], 1):
        title = r.get("title", "Unknown")
        link = r.get("link", "")
        source = r.get("source_type", "")
        if link:
            lines.append(f"{i}. [{title}]({link}) [{source}]")
        else:
            lines.append(f"{i}. {title} [{source}]")
    return "\n".join(lines)
