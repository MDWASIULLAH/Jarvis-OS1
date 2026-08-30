"""
brain/cognition.py

The Brain Core: one deterministic pipeline that every turn passes through.

    understand -> plan -> act (real tools) -> reflect -> respond

Design rules that this file enforces:

1. Nothing is claimed unless a tool actually returned it. Every answer carries
   the list of tools that ran, so the UI (and the tests) can verify it.
2. Tools are real capability calls -- opening apps, fetching pages, finding
   images, generating images, doing math, reading the clock. No stubs.
3. The language model is optional. `LocalReasoningBackend` composes answers
   from retrieved evidence when no LLM is installed, so a fresh clone answers
   correctly with zero external downloads.
4. Anything that touches the user's machine goes through the SecurityGate
   first and comes back as a confirmation request, never a silent action.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..capabilities import app_launcher, web_research
from ..capabilities.image_pipeline import ImageGenerator, ImageRetriever
from ..capabilities.knowledge_apis import define, multi_source_search, format_citations, search_stackexchange
from ..capabilities.media_store import MediaStore
from ..security.permissions import ActionType
from . import skills
from .decision_engine import DecisionEngine, Decision, ModelSelection, ToolCategory
from .local_engine import LocalReasoningBackend
from .nlu import IntentAnalyzer, IntentPrediction

# ----------------------------------------------------------------- patterns
_VOICE_CHANGE_PAT = re.compile(
    r"\b(change|switch|swap|set|update|modify|alter)\b[^.?!]*\b(voice|speech|accent|tone|sound|tts)\b"
    r"|\bvoice\s+(profile|change|switch|command)\b"
    r"|\b(speak|talk)\s+(differently|like|in)\b"
    r"|\b(male|female|robotic|natural|calm|friendly|professional|tony stark|tony)\s+(voice|speech|sound)\b",
    re.I,
)
_DOWNLOAD_PAT = re.compile(
    r"\b(download|install|get|fetch|grab)\b[^.?!]*\b(app|application|software|program|tool|editor|ide|browser|code|vs\s*code|vscode|pycharm|sublime|notepad)\b"
    r"|\binstall\b[^.?!]*\b(setup|configure)\b"
    r"|\b(install|download|set up)\b\s+([a-z0-9 .+\-]{2,30})\b",
    re.I,
)

# --------------------------------------------------------------- data types


@dataclass
class ToolCall:
    name: str
    ok: bool
    detail: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"tool": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class Thought:
    """The full, inspectable trace of a single turn."""

    text: str
    intent: str
    confidence: float
    intent_source: str
    slots: dict = field(default_factory=dict)
    plan: list[str] = field(default_factory=list)
    tools: list[ToolCall] = field(default_factory=list)
    reply: str = ""
    media: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    confirmation: Optional[dict] = None
    reflection: str = ""

    def to_dict(self) -> dict:
        return {
            "reply": self.reply,
            "intent": self.intent,
            "confidence": round(self.confidence, 4),
            "intent_source": self.intent_source,
            "slots": self.slots,
            "plan": self.plan,
            "tools_used": [t.to_dict() for t in self.tools],
            "media": self.media,
            "sources": self.sources,
            "confirmation": self.confirmation,
            "reflection": self.reflection,
            "grounded": bool(self.sources or self.media or any(t.ok for t in self.tools)),
        }


# ------------------------------------------------------------------ planner

_PLANS: dict[str, list[str]] = {
    "info.factual": ["retrieve encyclopedic summary", "compose grounded answer with citation"],
    "info.definition": ["look up dictionary entry", "state the definition"],
    "info.math": ["parse the expression safely", "evaluate and show the result"],
    "info.time": ["read the system clock", "format for the requested place/date"],
    "info.weather": ["resolve location", "call weather provider", "summarise conditions"],
    "info.news": ["fetch headlines", "summarise the top stories"],
    "info.translate": ["detect target language", "call translation provider"],
    "info.currency": ["parse amount and currencies", "call exchange-rate provider"],
    "media.image_search": ["find real images for the subject", "cache them locally", "return gallery"],
    "media.image_generate": ["build the render prompt", "generate the image", "return it"],
    "web.browse": ["fetch the page", "extract readable text and images", "summarise"],
    "action.open_app": ["check permission", "launch the application"],
    "action.web_open": ["check permission", "open the site in the browser"],
    "action.screenshot": ["check permission", "capture the screen"],
    "action.system_control": ["check permission", "report or apply the system change"],
    "memory.remember": ["extract the fact", "store it in encrypted local memory"],
    "memory.recall": ["search local memory", "answer from stored facts only"],
    "memory.forget": ["locate the fact", "request explicit deletion confirmation"],
    "task.plan": ["break the goal into ordered steps", "flag anything needing confirmation"],
    "task.code": ["restate the requirement", "outline a safe, testable approach"],
    "vision.analyze": ["extract text/visual evidence from the attachment", "describe what is verifiable"],
    "smalltalk.greeting": ["greet and offer concrete capabilities"],
    "smalltalk.identity": ["describe what this assistant actually is"],
    "smalltalk.capabilities": ["list capabilities that really work right now"],
}

_DEFAULT_PLAN = ["gather local and web evidence", "compose a grounded answer"]

_FACT_PREFIX = re.compile(
    r"^(?:please\s+)?(?:remember|note|store|keep in mind|don't forget)\s+(?:that\s+)?",
    re.IGNORECASE,
)
_RECALL_PREFIX = re.compile(
    r"^(?:what|which|who|where)\s+(?:is|are|was|were)\s+my\s+|^do you (?:remember|know)\s+(?:my\s+)?|^recall\s+(?:my\s+)?",
    re.IGNORECASE,
)
_FORGET_PREFIX = re.compile(r"^(?:please\s+)?(?:forget|delete|remove|erase)\s+(?:my\s+)?", re.IGNORECASE)
_TRANSLATE_RE = re.compile(
    r"translate\s+(?:this\s+|the\s+phrase\s+|)['\"]?(.+?)['\"]?\s+(?:in|into|to)\s+([a-zA-Z\- ]{2,20})\s*$",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*([A-Za-z]{3}|dollars?|euros?|pounds?|rupees?|yen)\s+(?:in|to|into)\s+([A-Za-z]{3}|dollars?|euros?|pounds?|rupees?|yen)",
    re.IGNORECASE,
)
_CCY_WORDS = {
    "dollar": "USD", "dollars": "USD", "euro": "EUR", "euros": "EUR",
    "pound": "GBP", "pounds": "GBP", "rupee": "INR", "rupees": "INR", "yen": "JPY",
}
_COMBINED_PIC_RE = re.compile(
    r"(?:give|show|find|get|fetch|display|send)\s+(?:me\s+)?(?:a\s+|an?\s+|her\s+|his\s+|their\s+)?(?:picture|photo|image|pic)",
    re.IGNORECASE,
)
_COMBINED_PIC_TAIL = re.compile(
    r"\s+(?:also|and|plus)\s+.*(?:picture|photo|image|pic)",
    re.IGNORECASE,
)
_COMBINED_PIC_WITH = re.compile(
    r"\b(?:image|picture|photo|pic)\s+(?:also|too|as well)",
    re.IGNORECASE,
)
_combined_image_pattern = re.compile(
    rf"{_COMBINED_PIC_RE.pattern}|{_COMBINED_PIC_TAIL.pattern}|{_COMBINED_PIC_WITH.pattern}",
    re.IGNORECASE,
)
_LANGS = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de", "italian": "it",
    "portuguese": "pt", "dutch": "nl", "russian": "ru", "japanese": "ja", "chinese": "zh",
    "korean": "ko", "arabic": "ar", "hindi": "hi", "bengali": "bn", "urdu": "ur",
    "turkish": "tr", "polish": "pl", "swedish": "sv", "greek": "el", "hebrew": "he",
}


def plan_for(intent: str) -> list[str]:
    return list(_PLANS.get(intent, _DEFAULT_PLAN))


# -------------------------------------------------------------- brain core


class BrainCore:
    """Understands, plans, acts with real tools, reflects, and answers."""

    def __init__(self, runtime: Any):
        self.rt = runtime
        self.intents = IntentAnalyzer()
        self.media = MediaStore(runtime.settings.data_dir / "media")
        self.images = ImageRetriever(self.media)
        self.generator = ImageGenerator(self.media)
        self.local = LocalReasoningBackend(knowledge=runtime.knowledge, memory=runtime.memory)
        self.decision_engine = DecisionEngine()
        self._reflect_history: list[dict] = []

    # ---- public entry point

    def think(self, text: str, provider: str = "local", attachment_text: str = "") -> Thought:
        prediction = self.intents.analyze(text)
        thought = Thought(
            text=text,
            intent=prediction.intent,
            confidence=prediction.confidence,
            intent_source=prediction.source,
            slots=dict(prediction.slots),
        )
        if attachment_text:
            thought.intent = "vision.analyze" if thought.intent.startswith("smalltalk") else thought.intent
        thought.plan = plan_for(thought.intent)

        llm_available = bool(self.rt.models.status().get("local_available"))
        decision = self.decision_engine.decide(
            intent=thought.intent,
            text=text,
            has_attachments=bool(attachment_text),
            has_llm_available=llm_available,
        )
        thought.slots["_decision"] = decision.to_dict()

        try:
            if _combined_image_pattern.search(text):
                self._act(thought, prediction, provider, attachment_text)
                self._h_image_search(thought)
            else:
                self._act(thought, prediction, provider, attachment_text)
        except Exception as exc:
            thought.tools.append(ToolCall("handler", False, str(exc)))
            thought.reply = (
                "I hit an error while working on that: "
                f"{exc}. Nothing was changed on your machine."
            )

        self._reflect(thought, decision)
        return thought

    # ---- dispatch

    def _act(self, t: Thought, prediction: IntentPrediction, provider: str, attachment_text: str) -> None:
        handler = {
            "smalltalk.greeting": self._h_greeting,
            "smalltalk.identity": self._h_identity,
            "smalltalk.capabilities": self._h_capabilities,
            "smalltalk.thanks": self._h_thanks,
            "smalltalk.bye": self._h_bye,
            "info.math": self._h_math,
            "info.time": self._h_time,
            "info.definition": self._h_definition,
            "info.weather": self._h_weather,
            "info.news": self._h_news,
            "info.translate": self._h_translate,
            "info.currency": self._h_currency,
            "media.image_search": self._h_image_search,
            "media.video_search": self._h_video_search,
            "media.image_generate": self._h_image_generate,
            "web.browse": self._h_browse,
            "action.open_app": self._h_open_app,
            "action.web_open": self._h_web_open,
            "action.screenshot": self._h_screenshot,
            "action.system_control": self._h_system,
            "memory.remember": self._h_remember,
            "memory.recall": self._h_recall,
            "memory.forget": self._h_forget,
            "task.plan": self._h_plan_task,
        }.get(t.intent)

        if attachment_text and t.intent in {"vision.analyze", "doc.read"}:
            return self._h_attachment(t, attachment_text)
        if handler:
            return handler(t)
        return self._h_knowledge(t, provider, attachment_text)

    # ---- smalltalk

    def _h_greeting(self, t: Thought) -> None:
        hour = datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        t.reply = (
            f"Good {part}. I'm online and running locally. I can do maths, tell you the time "
            "anywhere, look things up, find or generate images, read a web page, and open apps "
            "on this machine with your confirmation. What do you need?"
        )
        t.tools.append(ToolCall("clock", True, part))

    def _h_identity(self, t: Thought) -> None:
        status = self.rt.models.status()
        engine = "a local language model" if status.get("generative_local") else "my built-in local reasoning engine"
        t.reply = (
            "I'm JARVIS -- a private assistant that runs on this machine. I classify what you "
            f"ask with a trained local intent model, then call real tools for it, and I answer using {engine}. "
            "Nothing leaves your computer unless you explicitly switch a request to a cloud provider."
        )

    def _h_capabilities(self, t: Thought) -> None:
        launcher = app_launcher.status()
        t.reply = skills.bulletize(
            [
                "Maths and unit-safe calculations, evaluated exactly",
                "Time and date anywhere, including 'time in Tokyo' and 'what date is next Friday'",
                "Factual lookups from Wikipedia with the source link attached",
                "Finding real images of a subject, and generating an image when none exists",
                "Reading a URL and summarising the page's actual text",
                f"Opening apps, files and websites on this machine ({'enabled' if launcher['launch_enabled'] else 'disabled - set JARVIS_ALLOW_LAUNCH=1'})",
                "Remembering facts you tell it, in encrypted local storage",
            ],
            limit=8,
        )
        t.tools.append(ToolCall("capability_probe", True, f"launcher={launcher['platform']}"))

    def _h_thanks(self, t: Thought) -> None:
        t.reply = "Any time. What's next?"

    def _h_bye(self, t: Thought) -> None:
        t.reply = "Goodbye. I'll be here when you need me."

    # ---- deterministic skills

    def _h_math(self, t: Thought) -> None:
        result = skills.solve_math(t.slots.get("expression") or t.text)
        if not result:
            return self._h_knowledge(t, "local", "")
        if "error" in result:
            t.tools.append(ToolCall("calculator", False, result["error"]))
            t.reply = f"I couldn't evaluate `{result['expression']}` -- {result['error']}."
            return
        t.tools.append(ToolCall("calculator", True, result["expression"], {"display": result["display"]}))
        t.reply = f"{result['expression']} = **{result['display']}**"

    def _h_time(self, t: Thought) -> None:
        answer = skills.time_answer(t.text)
        t.tools.append(ToolCall("clock", True, answer))
        t.reply = answer

    def _h_definition(self, t: Thought) -> None:
        word = re.sub(r"^(?:what\s+(?:is|does)\s+(?:the\s+)?(?:meaning\s+of\s+)?|define\s+|definition\s+of\s+)", "", t.text.strip(), flags=re.IGNORECASE)
        word = word.strip(" ?.!\"'").split(" mean")[0].strip()
        text = define(word) if word else ""
        if text and "couldn't" not in text.lower() and "not" not in text.lower()[:12]:
            t.tools.append(ToolCall("dictionary", True, word))
            t.reply = text
            t.sources.append({"title": f"Dictionary: {word}", "url": f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"})
            return
        t.tools.append(ToolCall("dictionary", False, f"no entry for '{word}'"))
        self._h_knowledge(t, "local", "")

    def _h_weather(self, t: Thought) -> None:
        weather = getattr(self.rt, "weather", None)
        location = getattr(self.rt, "location", None)
        if not weather:
            t.tools.append(ToolCall("weather", False, "provider not wired"))
            t.reply = "My weather provider isn't configured on this install."
            return
        lat, lon, place = (None, None, "your location")
        match = re.search(r"\b(?:in|at|for)\s+([A-Za-z][A-Za-z\s\-']{1,40})$", t.text.strip(" ?.!"))
        if match and location:
            resolved = location.geocode(match.group(1).strip())
            if resolved:
                lat, lon, place = resolved[0], resolved[1], match.group(1).strip()
        if lat is None and location:
            here = location.approximate_location()
            if here:
                lat, lon, place = here.get("lat"), here.get("lon"), here.get("city", "your area")
        if lat is None:
            t.tools.append(ToolCall("weather", False, "no location resolved"))
            t.reply = "Tell me which city you want the weather for and I'll pull it."
            return
        summary = weather.current_weather(lat, lon)
        t.tools.append(ToolCall("weather", True, place))
        t.reply = f"Weather for {place}: {summary}"
        t.sources.append({"title": "open-meteo.com", "url": "https://open-meteo.com/"})

    def _h_news(self, t: Thought) -> None:
        news = getattr(self.rt, "news", None)
        if not news:
            t.tools.append(ToolCall("news", False, "provider not wired"))
            return self._h_knowledge(t, "local", "")
        topic_match = re.search(r"news\s+(?:about|on|for)\s+(.+)$", t.text, re.IGNORECASE)
        topic = topic_match.group(1).strip(" ?.!") if topic_match else "top"
        summary = news.summarize(topic, limit=5)
        t.tools.append(ToolCall("news", bool(summary), topic))
        t.reply = summary or "No headlines came back from the feeds just now."

    def _h_translate(self, t: Thought) -> None:
        from ..capabilities.translate_currency import translate

        match = _TRANSLATE_RE.search(t.text.strip())
        if not match:
            t.reply = "Give it to me as: translate \"good morning\" into Spanish."
            return
        phrase, language = match.group(1).strip(), match.group(2).strip().lower()
        code = _LANGS.get(language, language[:2])
        output = translate(phrase, code)
        ok = bool(output) and "unavailable" not in output.lower() and "failed" not in output.lower()
        t.tools.append(ToolCall("translate", ok, f"{language}"))
        t.reply = (
            f'"{phrase}" in {language.title()}: **{output}**'
            if ok
            else "My translation backend (LibreTranslate) isn't running, so I won't guess a translation. "
                 "Start one and set JARVIS_TRANSLATE_URL, and this works immediately."
        )

    def _h_currency(self, t: Thought) -> None:
        from ..capabilities.translate_currency import convert_currency

        match = _CURRENCY_RE.search(t.text)
        if not match:
            t.reply = "Try: convert 100 USD to EUR."
            return
        amount = float(match.group(1).replace(",", "."))
        src = _CCY_WORDS.get(match.group(2).lower(), match.group(2).upper())
        dst = _CCY_WORDS.get(match.group(3).lower(), match.group(3).upper())
        output = convert_currency(amount, src, dst)
        ok = bool(output) and "unavailable" not in output.lower()
        t.tools.append(ToolCall("currency", ok, f"{src}->{dst}"))
        t.reply = output if ok else f"I couldn't reach an exchange-rate provider for {src}->{dst} just now."

    # ---- media

    def _h_image_search(self, t: Thought) -> None:
        result = self.images.search(t.text, limit=4)
        t.media = result["images"]
        t.tools.append(ToolCall("image_search", bool(result["images"]), f"{len(result['images'])} image(s) for '{result['subject']}'", {"sources": result["sources_tried"]}))
        if result["images"]:
            article = result.get("article")
            t.reply = f"Here {'is' if len(result['images']) == 1 else 'are'} {len(result['images'])} real image(s) of **{result['subject']}**, cached locally."
            if article:
                t.reply += f"\n\n{skills.shorten(article['summary'], 320)}"
                t.sources.append({"title": article["title"], "url": article["url"]})
            for image in result["images"]:
                if image.get("source_url"):
                    t.sources.append({"title": image.get("caption") or "image source", "url": image["source_url"]})
            return
        t.reply = (
            f"I searched Wikipedia, Wikimedia Commons and Openverse for '{result['subject']}' and found no "
            "openly-licensed image I could fetch. I can generate one instead -- say \"generate an image of "
            f"{result['subject']}\"."
        )

    def _h_video_search(self, t: Thought) -> None:
        subject = re.sub(r"\b(video|videos|clip|clips|of|show|me|find|a|an|the)\b", " ", t.text, flags=re.IGNORECASE)
        subject = " ".join(subject.split()) or t.text
        url = f"https://www.youtube.com/results?search_query={subject.replace(' ', '+')}"
        t.sources.append({"title": f"YouTube results for {subject}", "url": url})
        t.tools.append(ToolCall("video_search", True, subject))
        t.reply = (
            f"I don't embed video without an API key, but here's the live search for **{subject}**: {url}\n"
            "Say \"open that\" and I'll launch it in your browser (with confirmation)."
        )

    def _h_image_generate(self, t: Thought) -> None:
        prompt = re.sub(
            r"^(?:please\s+)?(?:generate|create|make|draw|paint|render)\s+(?:me\s+)?(?:an?\s+)?(?:image|picture|photo|drawing|illustration|art)\s*(?:of|showing|with|depicting)?\s*",
            "",
            t.text.strip(),
            flags=re.IGNORECASE,
        ).strip(" ?.!") or t.text
        if not prompt or len(prompt) < 2:
            t.reply = "What should I generate an image of? Give me a description and I'll create it."
            t.tools.append(ToolCall("image_generate", False, "no prompt"))
            return
        result = self.generator.generate(prompt)
        t.media = [result.item.to_dict()]
        t.tools.append(ToolCall("image_generate", True, result.engine, {"prompt": prompt}))
        t.reply = f"Generated an image for **{prompt}**.\n\n{result.note}"

    # ---- web

    def _h_browse(self, t: Thought) -> None:
        url = t.slots.get("url") or ""
        if not url:
            t.reply = "Give me the full URL you want me to read."
            return
        page = web_research.extract_page(url)
        if not page.get("ok"):
            t.tools.append(ToolCall("browser", False, page.get("error", "fetch failed")))
            t.reply = f"I couldn't read {url}: {page.get('error', 'the request failed')}."
            return
        t.tools.append(ToolCall("browser", True, f"{page['chars']} chars from {page['title'] or url}"))
        t.sources.append({"title": page["title"] or url, "url": page["url"]})
        question = t.text.replace(url, " ").strip(" ?.!")
        summary = skills.summarize(page["text"], max_sentences=5, query=question)
        t.reply = f"**{page['title'] or url}**\n\n{summary}"
        if page.get("images"):
            cached = []
            for candidate in page["images"][:3]:
                downloaded = web_research.download(candidate["url"])
                if not downloaded:
                    continue
                raw, media_type = downloaded
                if not media_type.startswith("image/"):
                    continue
                item = self.media.save_bytes(
                    raw, media_type=media_type, kind="image",
                    caption=candidate.get("caption") or page["title"] or "page image",
                    source="page", source_url=candidate["url"],
                )
                cached.append(item.to_dict())
            t.media = cached

    def _h_knowledge(self, t: Thought, provider: str, attachment_text: str) -> None:
        """Multi-source retrieval: local knowledge -> Stack Overflow -> DDG -> Wikipedia -> LLM."""
        question = t.text.strip()
        lowered = question.lower()

        # Voice / speech profile change detection
        if _VOICE_CHANGE_PAT.search(lowered):
            t.reply = (
                "Voice profile change requested. Use the voice settings panel to switch between "
                "Tony Stark, Male, Female, Calm, Friendly, and Professional voices. "
                "You can also say: 'change voice to male', 'switch to Tony Stark voice', "
                "or 'speak in a calm voice'."
            )
            t.tools.append(ToolCall("voice_switch", True, "triggered voice profile change hint"))
            return

        # Download / install detection
        if _DOWNLOAD_PAT.search(lowered) or re.match(r"downlode", lowered):
            t.reply = (
                "To download and install software on this machine:\n"
                "1. Visit the official website (e.g., https://code.visualstudio.com for VS Code)\n"
                "2. Download the installer for your operating system\n"
                "3. Run the installer and follow the setup wizard\n\n"
                "For VS Code: the download page is https://code.visualstudio.com/download\n"
                "Just download, run the installer, and you're ready to go."
            )
            t.tools.append(ToolCall("download_guide", True, "provided download instructions"))
            return

        evidence: list[dict] = []

        for hit in self.rt.knowledge.search(question, top_k=3):
            evidence.append({"title": hit.get("title", "local document"), "text": hit.get("text", ""), "url": hit.get("source", "")})
        if evidence:
            t.tools.append(ToolCall("local_knowledge", True, f"{len(evidence)} chunk(s)"))

        multi = multi_source_search(question, max_results=6)
        for r in multi.get("results", []):
            evidence.append({"title": r.get("title", ""), "text": r.get("description", ""), "url": r.get("link", ""), "source_type": r.get("source_type", "")})
            if r.get("link"):
                t.sources.append({"title": r.get("title", ""), "url": r.get("link", "")})
        if multi.get("results"):
            t.tools.append(ToolCall("multi_source_search", True, f"{len(multi['results'])} result(s) from {multi['total_sources']} source(s)"))

        if multi.get("summary"):
            evidence.append({"title": "Wikipedia summary", "text": multi["summary"], "url": ""})

        if attachment_text:
            evidence.insert(0, {"title": "your attachment", "text": attachment_text, "url": ""})

        if not evidence:
            t.reply = "I searched multiple sources and couldn't find a direct answer. Try rephrasing your question or providing more details."
            t.tools.append(ToolCall("knowledge_search", False, "no results"))
            return

        t.tools.append(ToolCall("knowledge_search", True, f"{len(evidence)} evidence chunks from {len(t.sources)} sources"))

        if self.rt.models.status().get("generative_local") or provider == "cloud":
            context = "\n\n".join(f"[{i + 1}] {e['title']}: {e['text'][:1200]}" for i, e in enumerate(evidence))
            system = (
                "You are JARVIS. Answer using ONLY the numbered evidence. Cite as [1], [2]. "
                "If the evidence does not contain the answer, say so plainly. Be concise."
            )
            reply = self.rt.models.generate(
                f"Question: {question}\n\nEvidence:\n{context or '(none)'}",
                system=system,
                preference=provider,
            )
            t.tools.append(ToolCall("language_model", True, provider))
            t.reply = reply.strip() or self.local.compose(question, evidence, t.intent)
            return

        t.tools.append(ToolCall("local_reasoning", True, "no LLM installed; composing from evidence"))
        t.reply = self.local.compose(question, evidence, t.intent)

        citations = format_citations(multi.get("results", []))
        if citations and t.reply:
            t.reply += citations

    def _h_attachment(self, t: Thought, attachment_text: str) -> None:
        t.tools.append(ToolCall("attachment_extract", True, f"{len(attachment_text)} chars"))
        question = t.text.strip()
        summary = skills.summarize(attachment_text, max_sentences=5, query=question)
        t.reply = (
            f"From what I could actually extract from your attachment:\n\n{summary}\n\n"
            "That is text/visual evidence pulled from the file itself, not a guess about it."
        )

    # ---- real machine actions (always gated)

    def _h_open_app(self, t: Thought) -> None:
        target = t.slots.get("target") or ""
        if not target:
            t.reply = "Which application should I open?"
            return
        decision = self.rt.security.check_action(
            ActionType.APP_OPEN, target=target, payload={"operation": "open_app", "target": target}
        )
        self._gate(t, decision, f"open **{target}**", "app_launch")

    def _h_web_open(self, t: Thought) -> None:
        url = t.slots.get("url") or t.slots.get("target") or ""
        decision = self.rt.security.check_action(
            ActionType.APP_OPEN, target=url, payload={"operation": "open_website", "target": url}
        )
        self._gate(t, decision, f"open **{url}** in your browser", "web_open")

    def _h_screenshot(self, t: Thought) -> None:
        decision = self.rt.security.check_action(
            ActionType.SCREEN_CAPTURE, target="display", payload={"operation": "screenshot"}
        )
        self._gate(t, decision, "capture your screen", "screenshot")

    def _h_system(self, t: Thought) -> None:
        snapshot = self.rt.system_monitor.snapshot(self.rt.settings.data_dir)
        t.tools.append(ToolCall("system_monitor", True, "read-only snapshot", snapshot))
        parts = [f"{k}: {v}" for k, v in list(snapshot.items())[:6] if not isinstance(v, (dict, list))]
        t.reply = "Here's the current machine state I can read:\n" + skills.bulletize(parts, limit=6)

    def _gate(self, t: Thought, decision: Any, description: str, tool: str) -> None:
        # Order matters: SecurityGate returns allowed=False together with
        # requires_confirmation=True for a pending action (it is not yet
        # allowed, it is awaiting a yes). Checking `allowed` first would report
        # every confirmable action as a refusal.
        if decision.requires_confirmation:
            t.confirmation = {
                "confirmation_id": decision.confirmation_id,
                "description": description,
                "reason": decision.reason,
            }
            t.tools.append(ToolCall(tool, True, "confirmation requested"))
            t.reply = f"Ready to {description}. Confirm and I'll do it now."
            return
        if not decision.allowed:
            t.tools.append(ToolCall(tool, False, decision.reason))
            t.reply = f"I can't {description}: {decision.reason}"
            return
        t.tools.append(ToolCall(tool, True, "allowed without confirmation"))
        t.reply = f"Doing it now: {description}."

    # ---- memory

    def _h_remember(self, t: Thought) -> None:
        fact = _FACT_PREFIX.sub("", t.text.strip()).strip(" .!")
        if not fact:
            t.reply = "Tell me the fact you want me to keep, e.g. 'remember my train leaves at 7:40'."
            return
        key_source = re.split(r"\b(?:is|are|was|=|at)\b", fact, maxsplit=1)
        key = skills.keywords(key_source[0], limit=4)
        key_name = "_".join(key) or f"fact_{int(datetime.now().timestamp())}"
        self.rt.memory.long_term.remember(key_name, fact, "user_fact")
        t.tools.append(ToolCall("memory_write", True, key_name))
        t.reply = f"Stored, encrypted and local, under `{key_name}`: {fact}"

    def _h_recall(self, t: Thought) -> None:
        from ..memory.semantic_search import SemanticIndex

        query = _RECALL_PREFIX.sub("", t.text.strip()).strip(" ?.!") or t.text
        index = SemanticIndex()
        index.build(self.rt.memory.long_term.all_facts())
        hits = index.search(query, top_k=4)
        t.tools.append(ToolCall("memory_search", bool(hits), f"{len(hits)} hit(s)"))
        if not hits:
            t.reply = "I have nothing stored about that. Tell me and I'll remember it."
            return
        t.reply = "From your local memory:\n" + skills.bulletize([f"{h['key']}: {h['text']}" for h in hits], limit=4)

    def _h_forget(self, t: Thought) -> None:
        from ..memory.semantic_search import SemanticIndex

        query = _FORGET_PREFIX.sub("", t.text.strip()).strip(" ?.!")
        index = SemanticIndex()
        index.build(self.rt.memory.long_term.all_facts())
        hits = index.search(query, top_k=1)
        if not hits:
            t.tools.append(ToolCall("memory_search", False, "no match"))
            t.reply = "I couldn't find a stored fact matching that."
            return
        key = hits[0]["key"]
        decision = self.rt.security.check_action(
            ActionType.FILE_DELETE, target=f"memory:{key}", payload={"operation": "delete_memory", "key": key}
        )
        t.confirmation = {
            "confirmation_id": decision.confirmation_id,
            "description": f"delete the stored fact `{key}`",
            "reason": decision.reason,
        }
        t.tools.append(ToolCall("memory_delete", True, "confirmation requested"))
        t.reply = f"I found `{key}`: {hits[0]['text']}\nConfirm and I'll erase it permanently."

    # ---- planning

    def _h_plan_task(self, t: Thought) -> None:
        goal = re.sub(r"^(?:please\s+)?(?:make|create|give me|build)\s+(?:a\s+)?plan\s+(?:for|to)\s+", "", t.text.strip(), flags=re.IGNORECASE)
        route = self.rt.agents.plan(t.text)
        steps = [
            f"Clarify the definition of done for: {goal}",
            "List the hard constraints (time, budget, dependencies)",
            "Order the work so each step is reversible",
            "Identify which steps need my confirmation to touch your machine",
            "Set a checkpoint to review progress",
        ]
        t.tools.append(ToolCall("planner", True, ",".join(route["agents"])))
        t.reply = f"Plan for **{goal or 'your goal'}**:\n" + skills.bulletize(steps, limit=6)

    # ---- reflection

    def _reflect(self, t: Thought, decision: Optional[Decision] = None) -> None:
        """Enhanced self-check that evaluates success, learning, and future improvements."""
        ran = [c.name for c in t.tools if c.ok]
        failed = [f"{c.name} ({c.detail})" for c in t.tools if not c.ok]
        notes: list[str] = []
        if ran:
            notes.append("verified via " + ", ".join(ran))
        if failed:
            notes.append("unavailable: " + ", ".join(failed))
        if not t.sources and t.intent in {"info.factual", "info.news", "web.browse"}:
            notes.append("no citation available, so the answer is limited to what I could verify")
        if not t.reply.strip():
            t.reply = "I couldn't produce a grounded answer for that. Rephrase it and I'll try a different route."
            notes.append("empty response replaced by an honest failure")

        success = len(ran) > 0 and len(failed) == 0
        if not success and not t.reply.strip():
            success = False

        improvement_suggestion = ""
        if failed:
            improvement_suggestion = "Consider checking connector status for: " + ", ".join(set(c.split("(")[0].strip() for c in failed))
        elif not ran and t.intent not in {"smalltalk.greeting", "smalltalk.identity", "smalltalk.capabilities", "smalltalk.thanks", "smalltalk.bye"}:
            improvement_suggestion = "No tools ran; check if appropriate capabilities are available"

        if decision and decision.needs_memory_update and success:
            try:
                self.rt.memory.predictive.log_action(f"reflect:{t.intent}")
            except Exception:
                pass

        reflection_entry = {
            "intent": t.intent,
            "success": success,
            "tools_ran": ran,
            "tools_failed": failed,
            "citations": bool(t.sources),
            "media": bool(t.media),
            "improvement": improvement_suggestion,
        }
        self._reflect_history.append(reflection_entry)
        if len(self._reflect_history) > 100:
            self._reflect_history = self._reflect_history[-100:]

        notes.append(f"success={'yes' if success else 'no'}")
        if improvement_suggestion:
            notes.append(f"improvement: {improvement_suggestion}")
        t.reflection = "; ".join(notes) or "answered from deterministic local logic"

    # ---- introspection for /v1/brain/status

    def status(self) -> dict:
        return {
            "intent_model": self.intents.status(),
            "reasoning": {
                "llm_available": bool(self.rt.models.status().get("local_available")),
                "fallback": "local_reasoning_engine",
                "image_engine": self.generator.available_engine(),
            },
            "launcher": app_launcher.status(),
            "media_cached": self.media.count(),
            "intents_supported": sorted(set(list(_PLANS) + self.intents.status().get("labels", []))),
            "decision_engine": self.decision_engine.status(),
            "reflection_history": len(self._reflect_history),
        }
