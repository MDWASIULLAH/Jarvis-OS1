"""
brain/nlu.py

The Intent Analysis module of the Brain Core.

A dependency-free multinomial Naive Bayes classifier over word unigrams,
bigrams, and character 4-grams. It is trained offline (see
`training/train_intents.py`) and shipped as a small JSON model so the very
first run needs no training step, no network, and no model download.

Two-stage design, on purpose:

1. High-precision rules run first. "open chrome" must ALWAYS route to the app
   launcher -- a statistical model that is right 96% of the time is not good
   enough for an action that the user can see fail.
2. The trained model handles everything else, and reports a confidence so the
   Decision Engine can fall back to broad reasoning when the model is unsure.

Nothing here calls a language model. Intent classification stays local,
deterministic, and inspectable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .classifier import AveragedPerceptron

MODEL_PATH = Path(__file__).resolve().parent / "models" / "intent_model.json"

_TOKEN_RE = re.compile(r"[a-z0-9']+")



def tokenize(text: str) -> list[str]:
    """Word unigrams + bigrams + char 4-grams (raw feature names)."""
    lowered = text.lower().strip()
    words = _TOKEN_RE.findall(lowered)
    features = list(words)
    features += [f"{a}_{b}" for a, b in zip(words, words[1:])]
    condensed = " ".join(words)
    features += [f"#{condensed[i:i + 4]}" for i in range(max(0, len(condensed) - 3))]
    return features


def featurize(text: str) -> list[tuple[str, float]]:
    """Turns text into (feature, value) pairs for the linear classifier.

    Three deliberate choices, each fixing an observed failure:

    1. Char n-grams are down-weighted relative to words. Otherwise a long
       unfamiliar proper noun emits ~25 char features against 3 real intent
       words and decides the label by sheer count.
    2. Each feature *group* is L2-normalised, so a seven-word question and a
       one-word command ("morning") carry comparable total magnitude. Without
       this, short utterances could never accumulate enough score to win.
    3. A bias feature per utterance lets the model learn label priors properly
       instead of inferring them from template frequency.
    """
    lowered = text.lower().strip()
    words = _TOKEN_RE.findall(lowered)
    if not words:
        return [("__bias__", 1.0)]

    unigrams = list(words)
    bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
    condensed = " ".join(words)
    chars = [f"#{condensed[i:i + 4]}" for i in range(max(0, len(condensed) - 3))]
    # First/last word markers: "open ..." and "... please" are strong cues that
    # get diluted when position is thrown away entirely.
    positional = [f"^{words[0]}", f"${words[-1]}"]

    features: list[tuple[str, float]] = [("__bias__", 1.0)]
    for group, weight in ((unigrams, 1.0), (bigrams, 0.9), (chars, 0.35), (positional, 0.8)):
        if not group:
            continue
        scale = weight / (len(group) ** 0.5)
        counts: dict[str, float] = {}
        for name in group:
            counts[name] = counts.get(name, 0.0) + scale
        features.extend(counts.items())
    return features


@dataclass
class IntentPrediction:
    intent: str
    confidence: float
    source: str  # "rule" | "model" | "fallback"
    slots: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)


class IntentModel:
    """Trainable intent classifier: an averaged perceptron over sparse features.

    This replaced an earlier Naive Bayes implementation. NB looked fine on a
    random split of the generated corpus (~1.00) but scored only 0.58 on
    hand-written held-out phrasings, because its feature-independence
    assumption cannot cope with overlapping character n-grams. The perceptron
    is discriminative and measured far higher on the same held-out set; see
    `training/evaluate.py` for the reproducible comparison.
    """

    def __init__(self) -> None:
        self.core = AveragedPerceptron()

    @property
    def labels(self) -> list[str]:
        return self.core.labels

    @property
    def vocabulary(self) -> set[str]:
        return {name for table in self.core.weights.values() for name in table}

    # ---- training -------------------------------------------------------

    def train(self, rows: Iterable[tuple[str, str]], epochs: int = 14) -> "IntentModel":
        rows = list(rows)
        if not rows:
            raise ValueError("Cannot train an intent model on an empty dataset.")
        encoded = [(featurize(text), label) for text, label in rows]
        self.core.train(encoded, epochs=epochs)
        return self

    # ---- inference ------------------------------------------------------

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        features = featurize(text)
        best, raw = self.core.predict(features)
        if not best:
            return "unknown", 0.0, {}
        probabilities = self.core.probabilities(features)
        return best, probabilities.get(best, 0.0), probabilities

    # ---- persistence ----------------------------------------------------

    def to_dict(self) -> dict:
        return self.core.to_dict()

    def save(self, path: Path) -> Path:
        self.core.save(Path(path))
        return Path(path)

    @classmethod
    def load(cls, path: Path) -> "IntentModel":
        core = AveragedPerceptron.load(Path(path))
        if core is None:
            raise ValueError(f"Could not load an intent model from {path}")
        model = cls()
        model.core = core
        return model


# ------------------------------------------------------------------ rules

_IMAGE_SHOW = re.compile(
    r"\b(show|see|find|get|send|display|fetch)\b[^.?!]*\b(image|images|picture|pictures|pic|pics|photo|photos|gallery|wallpaper|look like)\b"
    r"|\b(image|images|photo|photos|picture|pictures|pics)\s+of\b"
    r"|\bwhat does .* look like\b",
    re.I,
)
_IMAGE_MAKE = re.compile(
    r"\b(generate|create|make|draw|paint|design|render|visuali[sz]e|sketch)\b[^.?!]*"
    r"\b(image|picture|photo|art|logo|poster|wallpaper|illustration|drawing|banner|icon|thumbnail)\b"
    r"|\b(draw|sketch|paint)\s+(me\s+)?(a|an|the)\b",
    re.I,
)
_OPEN_APP = re.compile(r"\b(open|launch|start|run|fire up)\b\s+(?:the\s+)?([a-z0-9 .+_-]{2,40})", re.I)
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_REMEMBER = re.compile(r"\b(remember|note down|note that|save this|keep in mind|don'?t forget)\b", re.I)
_FORGET = re.compile(r"\b(forget|erase|delete)\b.*\b(memory|remember|know about me|saved)\b", re.I)
_RECALL = re.compile(r"\b(what do you (remember|know) about me|recall my|what is my|where do i live|do you know my)\b", re.I)
_MATH = re.compile(r"^[\s\d+\-*/^%().,]+$")
# Word-form operators ("87 times 14", "add 450 and 275", "square root of 625")
# are extremely common and fully deterministic, so they belong in the rules
# layer rather than being left to a statistical model that got them wrong.
_MATH_ASK = re.compile(
    r"\b(calculate|calulate|compute|solve|what is|what'?s|how much is|work out)\b.*[\d)]\s*[-+*/^%]\s*[\d(]"
    r"|\b\d+\s*(%|percent)\s*of\s*\d+"
    r"|\b\d+\s*(times|multiplied by|divided by|plus|minus|over)\s*\d+"
    r"|\b(add|subtract|multiply|divide|sum)\b[^?]*\b\d+\b[^?]*\b\d+\b"
    r"|\b(square root|cube root|factorial|cube|square)\s+of\s+\d+"
    r"|\b\d+\s*(squared|cubed)\b"
    r"|\b(half|third|quarter|double|triple)\s+of\s+\d+"
    r"|\b\d+\s*to the (power|\w+)\b"
    r"|\baverage of\b[^?]*\d+",
    re.I,
)
_TIME = re.compile(
    r"\b(what('?s| is) the )?(time|date)\b|\bwhat day is it\b|\btoday'?s date\b"
    r"|\bwhat year is it\b|\bwhat month\b|\bclock\b|\btime check\b"
    r"|\bhow (long|many (days|hours|minutes|weeks))\b.*\b(until|till|to|left)\b",
    re.I,
)
_WEATHER = re.compile(r"\b(weather|temperature|forecast|raining|rainfall|humidity|how (hot|cold))\b", re.I)
_NEWS = re.compile(
    r"\b(news|headlines|top stories|breaking|current affairs|trending)\b"
    r"|\bwhat'?s (new|going on|happening)\b",
    re.I,
)
_SCREENSHOT = re.compile(
    r"\bscreen ?shots?\b|\bscreen ?grab\b|\bprint screen\b"
    r"|\b(capture|grab|snap|photograph)\b[^.?!]*\b(screen|display|window)\b"
    r"|\bpicture of (my |the )?screen\b",
    re.I,
)

# Words that are commonly mistyped and carry an unambiguous intent on their own.
# A hand-tuned regex for typos ("scrensht", "screnshot", "sceenshot") is a losing
# game, so these are matched by edit distance instead.
# NOTE: these must be canonical labels from INTENT_LABELS below. An earlier
# revision used "math.calculate", "text.translate" and "memory.store", none of
# which exist, so a typo'd command was routed to a handler that could never run.
# `_validate_rule_labels()` now fails loudly on that mistake.
_FUZZY_KEYWORDS = {
    "screenshot": "action.screenshot",
    "screenshots": "action.screenshot",
    "calculate": "info.math",
    "translate": "info.translate",
    "weather": "info.weather",
    "remember": "memory.remember",
}


def _edit_distance(a: str, b: str, limit: int = 2) -> int:
    """Levenshtein distance, abandoned early once it exceeds `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def _fuzzy_keyword_intent(text: str) -> Optional[str]:
    """Matches a mistyped single keyword, e.g. 'scrensht please'.

    Only applies to short utterances (<= 3 words) so that a typo buried in a
    long sentence cannot hijack an otherwise clear request.
    """
    words = _TOKEN_RE.findall(text.lower())
    if not words or len(words) > 3:
        return None
    for word in words:
        if len(word) < 5:
            continue
        if word in _FUZZY_KEYWORDS:
            return _FUZZY_KEYWORDS[word]
        for keyword, intent in _FUZZY_KEYWORDS.items():
            if _edit_distance(word, keyword) <= 2:
                return intent
    return None
_TRANSLATE = re.compile(
    r"\btranslate\b|\bhow do (you|i) (say|write)\b.*\bin\b"
    r"|\b(in|into|to)\s+(hindi|spanish|french|german|japanese|tamil|arabic|korean|italian|russian"
    r"|chinese|dutch|polish|greek|turkish|urdu|portuguese|swahili|bengali|telugu|marathi)\b",
    re.I,
)
_CURRENCY = re.compile(
    r"\bconvert\b[^?]*\b(usd|inr|eur|gbp|jpy|aud|cad|nzd|chf|yen|euro|dollar|rupee|pound|bitcoin)s?\b"
    r"|\bexchange rate\b"
    r"|\b\d+\s*(usd|inr|eur|gbp|jpy|aud|cad|nzd|chf|yen|euros?|dollars?|rupees?|pounds?|bitcoin)\b"
    r"[^?]*\b(in|to|into)\b"
    r"|\bhow (much|many)\b[^?]*\b(rupees?|dollars?|euros?|pounds?|yen)\b",
    re.I,
)
_DEFINE = re.compile(r"\b(define|definition of|meaning of|what does .* mean)\b", re.I)
_SYSTEM = re.compile(
    r"\b(shut ?down|restart|reboot|sleep mode|hibernate|log (me )?out|sign me out"
    r"|mute|unmute|volume (up|down)|turn off (wifi|bluetooth)|turn on (wifi|bluetooth))\b"
    # "lock the screen" / "lock my laptop" / "put my pc to sleep": an explicit
    # verb plus a device noun, which the model kept reading as a memory query
    # because of the possessive "my".
    r"|\b(lock|sleep|wake|power (off|down)|switch off)\b[^.?!]*"
    r"\b(screen|display|laptop|pc|computer|machine|desktop|system|device)\b"
    r"|\b(laptop|pc|computer|machine|desktop|system)\b[^.?!]*\b(to sleep|off now)\b",
    re.I,
)
_PLAN = re.compile(
    r"\b(plan|roadmap|schedule|break (this|it|down)|task list|prioriti[sz]e|organi[sz]e"
    r"|outline|checklist|steps to|split .* into (stages|steps|phases))\b",
    re.I,
)
# Short greetings with repeated letters ("heyy", "hiii") tokenize into features
# the model has never seen, so a tiny explicit matcher is more reliable.
_GREETING = re.compile(
    r"^(hi+|hey+|hello+|yo+|sup|hiya|howdy|namaste|morning|good (morning|afternoon|evening|day))"
    r"[\s!,.]*(jarvis|there|buddy|mate|again)?[\s!,.?]*$",
    re.I,
)
_IDENTITY = re.compile(
    r"\b(who are you|what are you|who made you|who built you|who created you"
    r"|your name|do you have a name|what should i call you|are you (an? )?(ai|robot|human|real|sentient)"
    r"|which (llm|model)|what model|introduce yourself|tell me who you are)\b",
    re.I,
)
_CAPABILITIES = re.compile(
    r"\b(what can you do|your (capabilities|abilities|skills|features)"
    r"|what (are you good at|features|tasks can you|should i ask|can i (ask|use))"
    r"|list (what you can do|your)|how can you help|rundown of your|show your abilities)\b",
    re.I,
)
# Hinglish/Hindi image requests ("mujhe ... photo dikhao", "chrome kholo").
_HINGLISH_IMAGE = re.compile(r"\b(photo|tasveer|image|pic)\b[^.?!]*\b(dikhao|dikha|bhejo|do)\b", re.I)
_HINGLISH_OPEN = re.compile(r"\b([a-z0-9 ._-]{2,30})\s+(kholo|khol do|chalu karo|start karo)\b", re.I)
_NAVIGATE = re.compile(
    r"\b(pull up|visit|navigate to|go to|take me to|jump (over )?to|load|browse to)\b", re.I
)
# "compose a thank you note" must beat the "thank you" smalltalk cue, so the
# writing verb plus a document noun is matched as a rule and checked first.
_EMAIL_DRAFT = re.compile(
    r"\b(draft|compose|write|type up|put together|prepare)\b[^.?!]*"
    r"\b(email|e-mail|mail|inbox|note|message|reply|memo|follow[- ]?up)\b",
    re.I,
)
# Long-form documents that also follow a writing verb. "draft a cover letter"
# and "write a complaint letter" are doc.write, not email.draft -- the bare word
# "letter" was previously enough to misroute them, so it is excluded above and
# handled here instead.
_DOC_WRITE = re.compile(
    r"\b(cover letter|complaint letter|formal letter|resignation letter|recommendation letter"
    r"|essay|proposal|report|thesis|dissertation|article|blog post|press release"
    r"|business plan|case study|white ?paper|summary document|spec(ification)?|brief"
    r"|application|resume|cv|contract|agreement|policy|manual|documentation)\b",
    re.I,
)
_SITE_WORD = re.compile(r"\b([a-z0-9-]{3,30})(?:\.com|\.org|\.net|\s+(?:website|site|homepage))\b", re.I)

_VOICE_CHANGE = re.compile(
    r"\b(change|switch|swap|set|update|modify|alter)\b[^.?!]*\b(voice|speech|accent|tone|sound|tts)\b"
    r"|\bvoice\s+(profile|change|switch|command)\b"
    r"|\b(speak|talk)\s+(differently|like|in)\b"
    r"|\b(male|female|robotic|natural|calm|friendly|professional|tony stark|tony)\s+(voice|speech|sound)\b",
    re.I,
)
_DOWNLOAD = re.compile(
    r"\b(download|install|get|fetch|grab)\b[^.?!]*\b(app|application|software|program|tool|editor|ide|browser|code|vs\s*code|vscode|pycharm|sublime|notepad)\b"
    r"|\binstall\b[^.?!]*\b(setup|configure)\b"
    r"|\b(install|download|set up)\b\s+([a-z0-9 .+\-]{2,30})\b"
    r"|\bdownlode\b",
    re.I,
)
_IMAGE_WITH = re.compile(
    r"\b(give|show|send|get|fetch)\s+(?:me\s+)?(?:a\s+|an?\s+|her\s+|his\s+|their\s+)?(?:picture|photo|image|pic)\b"
    r"|\b(?:image|picture|photo|pic)\s+(?:also|too|as well|too)\b"
    r"|\bwith\s+(?:her|his|their|its|a|an)\s+(?:image|picture|photo|pic)\b",
    re.I,
)

# Code generation: "write html css javascript code", "create a website", "build a react app"
_CODE_GEN = re.compile(
    r"\b(write|create|make|build|generate|code|develop|program|implement|craft|construct)\b[^.?!]*"
    r"\b(code|script|program|app|application|website|webpage|web page|site|function|component"
    r"|class|module|backend|frontend|api|rest api|endpoint|endpoints|server|landing page|dashboard"
    r"|portfolio|game|calculator|form|blog|chat|bot|tool)\b"
    r"|\b(html|css|javascript|js|react|node|python|typescript|vue|angular|next\s*\.?\s*js|nextjs"
    r"|tailwind|tailwindcss|bootstrap|flask|django|express|spring|go|lang|rust|php|ruby|swift|kotlin)\b"
    r"[^.?!]*\b(code|script|program|app|application|website|site)\b"
    r"|\b(create|build|make|write|generate)\b[^.?!]*"
    r"\b(html\s*css|css\s*html|static\s*site|single\s*page|web\s*app|landing|responsive)\b"
    r"|\b(write|code|generate)\s+(me\s+)?(a|an|some)\s+(code|script|program|function)\b"
    r"|\bhtml\s+(?:and|&|,)?\s*css\s+(?:and|&|,)?\s*(?:javascript|js)\b"
    r"|\b(create|build|make)\s+(?:a|an|the)\s+(?:fullstack|full stack|responsive|static|interactive|dynamic)\s+(?:website|site|webpage|app|application)\b",
    re.I,
)

_WEB_HOSTS = {
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "google": "https://www.google.com",
    "wikipedia": "https://www.wikipedia.org",
    "gmail": "https://mail.google.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
}


# Every intent the system can produce. The rules layer and the trained model
# must agree on this vocabulary; a rule returning a label outside this set would
# reach a handler that does not exist.
INTENT_LABELS = frozenset({
    "action.open_app", "action.screenshot", "action.system_control", "action.web_open",
    "doc.read", "doc.write", "email.draft",
    "info.currency", "info.definition", "info.factual", "info.math", "info.news",
    "info.time", "info.translate", "info.weather",
    "media.image_generate", "media.image_search", "media.video_search",
    "memory.forget", "memory.recall", "memory.remember",
    "smalltalk.bye", "smalltalk.capabilities", "smalltalk.greeting",
    "smalltalk.identity", "smalltalk.thanks",
    "task.code", "task.plan", "vision.analyze", "web.browse",
})


def _validate_rule_labels() -> None:
    """Catches hard-coded labels that are not real intents.

    This runs at import time because the alternative is a silent failure: a rule
    returns a plausible-looking label like "math.calculate", no handler matches,
    and the user gets a generic fallback reply with no error anywhere.
    """
    unknown = sorted(set(_FUZZY_KEYWORDS.values()) - INTENT_LABELS)
    if unknown:
        raise RuntimeError(
            f"nlu.py references intent label(s) that do not exist: {unknown}. "
            f"Use a label from INTENT_LABELS."
        )


_validate_rule_labels()


def _rule_intent(text: str) -> Optional[tuple[str, dict]]:
    stripped = text.strip()
    if _GREETING.match(stripped):
        return "smalltalk.greeting", {}
    if _URL.search(stripped):
        return "web.browse", {"url": _URL.search(stripped).group(0)}
    # Checked before the smalltalk cues below: "compose a thank you note"
    # contains "thank you" but is unmistakably a drafting request. Long-form
    # documents are tested first so "draft a cover letter" stays doc.write.
    if _DOC_WRITE.search(stripped) and re.search(
        r"\b(draft|compose|write|type up|put together|prepare|create|make|produce)\b", stripped, re.I
    ):
        return "doc.write", {}
    if _EMAIL_DRAFT.search(stripped):
        return "email.draft", {}
    fuzzy = _fuzzy_keyword_intent(stripped)
    if fuzzy:
        return fuzzy, {}
    if _IDENTITY.search(stripped):
        return "smalltalk.identity", {}
    if _CAPABILITIES.search(stripped):
        return "smalltalk.capabilities", {}
    if _HINGLISH_IMAGE.search(stripped):
        return "media.image_search", {}
    hinglish_open = _HINGLISH_OPEN.search(stripped)
    if hinglish_open:
        target = hinglish_open.group(1).strip()
        for host, url in _WEB_HOSTS.items():
            if target.startswith(host):
                return "action.web_open", {"target": host, "url": url}
        return "action.open_app", {"target": target}
    if _IMAGE_MAKE.search(stripped):
        return "media.image_generate", {}
    if _IMAGE_SHOW.search(stripped):
        return "media.image_search", {}
    # Code generation must be checked before the general model fallback
    if _CODE_GEN.search(stripped):
        return "task.code", {}
    if _SCREENSHOT.search(stripped):
        return "action.screenshot", {}
    if _FORGET.search(stripped):
        return "memory.forget", {}
    if _REMEMBER.search(stripped):
        return "memory.remember", {}
    if _RECALL.search(stripped):
        return "memory.recall", {}
    if _MATH.match(stripped) and any(c.isdigit() for c in stripped) and any(
        op in stripped for op in "+-*/^%"
    ):
        return "info.math", {"expression": stripped}
    if _MATH_ASK.search(stripped):
        return "info.math", {}
    if _CURRENCY.search(stripped):
        return "info.currency", {}
    if _TRANSLATE.search(stripped):
        return "info.translate", {}
    if _DEFINE.search(stripped):
        return "info.definition", {}
    if _TIME.search(stripped):
        return "info.time", {}
    if _WEATHER.search(stripped):
        return "info.weather", {}
    if _NEWS.search(stripped):
        return "info.news", {}
    if _SYSTEM.search(stripped):
        return "action.system_control", {}
    match = _OPEN_APP.search(stripped)
    if match:
        target = match.group(2).strip().rstrip("?.!").strip()
        for host, url in _WEB_HOSTS.items():
            if target.startswith(host):
                return "action.web_open", {"target": host, "url": url}
        if target:
            return "action.open_app", {"target": target}
    # A bare known-site name with a navigation verb ("pull up github", "visit
    # amazon", "jump over to the bbc website"). Matched after the generic
    # open/launch rule so "open github" still resolves through the branch above.
    navigate = _NAVIGATE.search(stripped)
    if navigate:
        lowered = stripped.lower()
        for host, url in _WEB_HOSTS.items():
            if re.search(rf"\b{re.escape(host)}\b", lowered):
                return "action.web_open", {"target": host, "url": url}
        site = _SITE_WORD.search(stripped)
        if site:
            return "action.web_open", {"target": site.group(1).strip()}
    if _PLAN.search(stripped):
        return "task.plan", {}
    if _VOICE_CHANGE.search(stripped):
        return "info.factual", {}
    if _DOWNLOAD.search(stripped):
        return "info.factual", {}
    if _IMAGE_WITH.search(stripped):
        return "media.image_search", {}
    return None


# ------------------------------------------------------------- public API


class IntentAnalyzer:
    """Rules first, trained model second, graceful fallback last."""

    def __init__(self, model_path: Path | None = None) -> None:
        self.model: Optional[IntentModel] = None
        self.model_path = Path(model_path or MODEL_PATH)
        self._load_or_train()

    def _load_or_train(self) -> None:
        try:
            if self.model_path.exists():
                self.model = IntentModel.load(self.model_path)
                return
        except (OSError, ValueError, KeyError):
            self.model = None
        # No shipped model (or a corrupt one): train from the seed corpus in
        # memory. Takes well under a second and keeps first-run behaviour sane.
        try:
            from training.templates import generate  # type: ignore

            self.model = IntentModel().train(generate())
        except Exception:  # noqa: BLE001 -- rules alone still work
            self.model = None

    def analyze(self, text: str) -> IntentPrediction:
        rule = _rule_intent(text)
        if rule:
            intent, slots = rule
            return IntentPrediction(intent=intent, confidence=0.99, source="rule", slots=slots)
        if self.model:
            intent, confidence, scores = self.model.predict(text)
            top = dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:3])
            return IntentPrediction(
                intent=intent, confidence=round(confidence, 4), source="model", scores=top
            )
        return IntentPrediction(intent="info.factual", confidence=0.0, source="fallback")

    @property
    def trained(self) -> bool:
        return self.model is not None

    def status(self) -> dict:
        return {
            "trained": self.trained,
            "label_count": len(self.model.labels) if self.model else 0,
            "labels": sorted(self.model.labels) if self.model else [],
            "features": len(self.model.vocabulary) if self.model else 0,
            "model_file": str(self.model_path) if self.model_path.exists() else "trained-in-memory",
        }
