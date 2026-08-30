"""
brain/skills.py

Deterministic language and math skills the Brain Core uses instead of asking a
model to do arithmetic, tell the time, or pad out a summary.

These are the pieces that make JARVIS useful with *no model installed at all*:
a safe expression evaluator, unit/percentage handling, date arithmetic, an
extractive summariser, and keyword utilities. They are exact, instant, and
testable -- three things a language model is not.
"""

from __future__ import annotations

import ast
import math
import operator
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ------------------------------------------------------------------- math

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_FUNCTIONS = {
    "sqrt": math.sqrt, "abs": abs, "round": round, "floor": math.floor,
    "ceil": math.ceil, "log": math.log, "log10": math.log10, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "factorial": math.factorial,
    "min": min, "max": max, "sum": lambda *a: sum(a), "pow": pow,
}
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}

_WORD_OPS = [
    (r"\bplus\b|\badd(ed)?( to)?\b", "+"),
    (r"\bminus\b|\bsubtract(ed)?( from)?\b|\bless\b", "-"),
    (r"\btimes\b|\bmultiplied by\b|\bmultiply by\b|\bx\b", "*"),
    (r"\bdivided by\b|\bover\b", "/"),
    (r"\bto the power of\b|\braised to\b", "**"),
    (r"\bsquared\b", "**2"),
    (r"\bcubed\b", "**3"),
]


class MathError(ValueError):
    pass


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise MathError("only numbers are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and (abs(left) > 1e6 or abs(right) > 256):
            raise MathError("that exponent is too large to evaluate safely")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.Name) and node.id.lower() in _CONSTANTS:
        return _CONSTANTS[node.id.lower()]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = _FUNCTIONS.get(node.func.id.lower())
        if not function:
            raise MathError(f"unknown function {node.func.id}")
        return function(*[_evaluate(arg) for arg in node.args])
    raise MathError("unsupported expression")


def normalize_expression(text: str) -> str:
    """Pull an arithmetic expression out of natural language."""
    working = text.lower().strip().rstrip("?.!")
    working = re.sub(
        r"^(hey |ok |please )*(jarvis[, ]*)?(calculate|compute|solve|evaluate|what is|what'?s|how much is|tell me)\s*",
        "", working,
    )
    percent_of = re.search(r"([\d.]+)\s*(?:%|percent)\s*of\s*([\d.,]+)", working)
    if percent_of:
        base = percent_of.group(2).replace(",", "")
        return f"({percent_of.group(1)}/100)*{base}"
    factorial = re.search(r"([\d]+)\s*(?:!|factorial)", working)
    if factorial:
        return f"factorial({factorial.group(1)})"
    for pattern, replacement in _WORD_OPS:
        working = re.sub(pattern, replacement, working)
    working = working.replace("^", "**").replace(",", "").replace("÷", "/").replace("×", "*")
    working = re.sub(r"\bsquare root of\b|\broot of\b", "sqrt", working)
    working = re.sub(r"\bsqrt\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", working)
    working = re.sub(r"[^0-9+\-*/%.()a-z_ ]", " ", working)
    return working.strip()


def solve_math(text: str) -> Optional[dict]:
    """Evaluate an expression. Returns None when there is nothing to compute."""
    expression = normalize_expression(text)
    if not expression or not any(char.isdigit() for char in expression):
        return None
    try:
        tree = ast.parse(expression, mode="eval")
        value = _evaluate(tree)
    except (SyntaxError, MathError, ZeroDivisionError, ValueError, TypeError, OverflowError, RecursionError) as exc:
        return {"expression": expression, "error": str(exc) or "that expression doesn't parse"}
    if isinstance(value, float):
        rounded = round(value, 10)
        display = f"{int(rounded)}" if rounded == int(rounded) and abs(rounded) < 1e15 else f"{rounded:,.6g}"
    else:
        display = f"{value:,}"
    return {"expression": expression, "value": value, "display": display}


# ------------------------------------------------------------------- time

_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
)


def time_answer(text: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now().astimezone()
    lowered = text.lower()

    match = re.search(r"how many days (?:until|till|to) (?:the )?([a-z0-9 ]+)", lowered)
    if match:
        phrase = match.group(1).strip()
        target = _parse_future_date(phrase, now)
        if target:
            days = (target.date() - now.date()).days
            label = phrase.title()
            if days == 0:
                return f"{label} is today."
            return f"{days} day{'s' if days != 1 else ''} until {label} ({target.strftime('%d %B %Y')})."

    # Handles "time in Tokyo", "what time is it in Tokyo", "Tokyo time".
    # The previous pattern required the literal substring "time in", so the
    # most natural phrasing ("what time is it in Tokyo") silently fell through
    # and answered with local time instead.
    zone = (
        re.search(r"\btime\b(?:\s+is\s+it)?(?:\s+right\s+now)?\s+in\s+([a-z /_'-]+)", lowered)
        or re.search(r"\bin\s+([a-z /_'-]+?)\s+(?:time|right now)\b", lowered)
        or re.match(r"\s*([a-z /_'-]+?)\s+time\b", lowered)
    )
    if zone:
        place = zone.group(1).strip(" ?.!")
        shifted = _time_in_zone(place, now)
        if shifted:
            return (
                f"It is {shifted.strftime('%I:%M %p').lstrip('0')} on "
                f"{shifted.strftime('%A, %d %B %Y')} in {place.title()} "
                f"(UTC{shifted.strftime('%z')[:3]}:{shifted.strftime('%z')[3:]})."
            )

    parts = []
    if re.search(r"\btime\b", lowered) or not re.search(r"\b(date|day)\b", lowered):
        parts.append(f"It's {now.strftime('%I:%M %p').lstrip('0')} ({now.tzname() or 'local time'})")
    if re.search(r"\b(date|day|today)\b", lowered) or not parts:
        parts.append(f"today is {now.strftime('%A, %d %B %Y')}")
    sentence = ", and ".join(parts)
    return sentence[0].upper() + sentence[1:] + "."


def _parse_future_date(phrase: str, now: datetime) -> Optional[datetime]:
    lowered = phrase.lower().strip()
    fixed = {
        "new year": (1, 1), "new years": (1, 1), "new year's": (1, 1),
        "christmas": (12, 25), "diwali": None, "independence day": (8, 15),
        "republic day": (1, 26), "halloween": (10, 31), "valentines day": (2, 14),
    }
    if lowered in fixed and fixed[lowered]:
        month, day = fixed[lowered]
        candidate = now.replace(month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
        if candidate.date() < now.date():
            candidate = candidate.replace(year=candidate.year + 1)
        return candidate
    match = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)", lowered)
    if match and match.group(2) in _MONTHS:
        month = _MONTHS.index(match.group(2)) + 1
        candidate = now.replace(month=month, day=int(match.group(1)), hour=0, minute=0, second=0, microsecond=0)
        if candidate.date() < now.date():
            candidate = candidate.replace(year=candidate.year + 1)
        return candidate
    return None


# Real IANA zone names, resolved through the standard library's tz database,
# so daylight saving is correct year-round. The previous fixed UTC offsets
# were wrong for roughly half the year in every DST-observing city (London in
# summer, New York in summer, Sydney in their summer, and so on).
_ZONE_NAMES = {
    "utc": "UTC", "gmt": "UTC",
    "london": "Europe/London", "uk": "Europe/London", "england": "Europe/London",
    "lisbon": "Europe/Lisbon", "dublin": "Europe/Dublin",
    "paris": "Europe/Paris", "france": "Europe/Paris",
    "berlin": "Europe/Berlin", "germany": "Europe/Berlin",
    "madrid": "Europe/Madrid", "spain": "Europe/Madrid",
    "rome": "Europe/Rome", "italy": "Europe/Rome",
    "amsterdam": "Europe/Amsterdam", "zurich": "Europe/Zurich",
    "stockholm": "Europe/Stockholm", "athens": "Europe/Athens",
    "cairo": "Africa/Cairo", "lagos": "Africa/Lagos",
    "johannesburg": "Africa/Johannesburg", "nairobi": "Africa/Nairobi",
    "moscow": "Europe/Moscow", "istanbul": "Europe/Istanbul", "turkey": "Europe/Istanbul",
    "dubai": "Asia/Dubai", "uae": "Asia/Dubai", "riyadh": "Asia/Riyadh",
    "tehran": "Asia/Tehran", "karachi": "Asia/Karachi", "pakistan": "Asia/Karachi",
    "india": "Asia/Kolkata", "delhi": "Asia/Kolkata", "new delhi": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "bengaluru": "Asia/Kolkata",
    "kolkata": "Asia/Kolkata", "chennai": "Asia/Kolkata", "hyderabad": "Asia/Kolkata",
    "ist": "Asia/Kolkata", "pune": "Asia/Kolkata",
    "colombo": "Asia/Colombo", "kathmandu": "Asia/Kathmandu",
    "dhaka": "Asia/Dhaka", "bangladesh": "Asia/Dhaka",
    "bangkok": "Asia/Bangkok", "thailand": "Asia/Bangkok",
    "jakarta": "Asia/Jakarta", "hanoi": "Asia/Ho_Chi_Minh",
    "singapore": "Asia/Singapore", "kuala lumpur": "Asia/Kuala_Lumpur",
    "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai", "china": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong", "taipei": "Asia/Taipei", "manila": "Asia/Manila",
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "seoul": "Asia/Seoul", "korea": "Asia/Seoul",
    "perth": "Australia/Perth", "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne", "brisbane": "Australia/Brisbane",
    "auckland": "Pacific/Auckland", "new zealand": "Pacific/Auckland",
    "honolulu": "Pacific/Honolulu", "hawaii": "Pacific/Honolulu",
    "anchorage": "America/Anchorage", "alaska": "America/Anchorage",
    "los angeles": "America/Los_Angeles", "california": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles",
    "la": "America/Los_Angeles", "vancouver": "America/Vancouver",
    "denver": "America/Denver", "phoenix": "America/Phoenix",
    "chicago": "America/Chicago", "dallas": "America/Chicago", "houston": "America/Chicago",
    "mexico city": "America/Mexico_City",
    "new york": "America/New_York", "nyc": "America/New_York", "boston": "America/New_York",
    "washington": "America/New_York", "miami": "America/New_York", "atlanta": "America/New_York",
    "toronto": "America/Toronto", "montreal": "America/Toronto",
    "sao paulo": "America/Sao_Paulo", "brazil": "America/Sao_Paulo",
    "buenos aires": "America/Argentina/Buenos_Aires", "lima": "America/Lima",
    "bogota": "America/Bogota", "santiago": "America/Santiago",
}


def _time_in_zone(place: str, now: datetime) -> Optional[datetime]:
    key = re.sub(r"\s+", " ", place.lower().strip().rstrip("?.!"))
    name = _ZONE_NAMES.get(key)
    if not name:
        return None
    try:
        return now.astimezone(ZoneInfo(name))
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None


# -------------------------------------------------------------- summarise

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "of", "to", "in",
    "on", "for", "with", "as", "at", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "it", "its", "this", "that", "these", "those", "he",
    "she", "they", "them", "his", "her", "their", "which", "who", "whom", "what",
    "when", "where", "how", "why", "not", "no", "also", "can", "could", "would",
    "should", "will", "may", "might", "must", "there", "here", "you", "your",
    "i", "we", "our", "us", "has", "have", "had", "do", "does", "did", "about",
    "into", "over", "after", "before", "between", "more", "most", "such", "some",
}


def keywords(text: str, limit: int = 8) -> list[str]:
    counts: dict[str, int] = {}
    for word in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", text.lower()):
        if word in _STOPWORDS:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    return [s.strip() for s in _SENTENCE_RE.split(cleaned) if len(s.strip()) > 2]


def summarize(text: str, max_sentences: int = 3, query: str = "") -> str:
    """Frequency-scored extractive summary, optionally biased toward a query.

    Extractive on purpose: every sentence returned is one that genuinely
    appeared in the source, so a summary can never invent a fact.
    """
    items = sentences(text)
    if len(items) <= max_sentences:
        return " ".join(items)

    frequencies: dict[str, int] = {}
    for word in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", text.lower()):
        if word not in _STOPWORDS:
            frequencies[word] = frequencies.get(word, 0) + 1
    peak = max(frequencies.values()) if frequencies else 1
    query_words = {w for w in re.findall(r"[a-z']{3,}", query.lower()) if w not in _STOPWORDS}

    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(items):
        words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", sentence.lower())
        if not words:
            continue
        score = sum(frequencies.get(word, 0) / peak for word in words) / math.sqrt(len(words))
        if query_words:
            score += 1.4 * len(query_words.intersection(words))
        score += max(0.0, 0.6 - index * 0.08)  # early sentences carry the thesis
        scored.append((score, index, sentence))

    top = sorted(scored, key=lambda item: -item[0])[:max_sentences]
    return " ".join(sentence for _, _, sentence in sorted(top, key=lambda item: item[1]))


def shorten(text: str, limit: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit]
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: boundary + 1] if boundary > limit * 0.5 else cut.rstrip() + "…").strip()


def bulletize(items: list[str], limit: int = 6) -> str:
    return "\n".join(f"- {item}" for item in items[:limit] if item)
