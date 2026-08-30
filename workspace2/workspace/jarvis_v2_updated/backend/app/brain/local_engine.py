"""
brain/local_engine.py

JARVIS's own answer engine -- the reason the assistant no longer needs Ollama
to be useful.

The old `MockBackend` replied "[mock response] I heard: ..." whenever no local
model was running, which is exactly the "it doesn't answer anything" problem.
This replaces it with something that actually answers, by composing:

* deterministic skills (arithmetic, dates, unit-free maths, summarising),
* evidence the Brain Core gathered from tools (Wikipedia, weather, news,
  memory, documents, launched apps),
* the user's own local memory and knowledge base.

It is a *composer*, not a text predictor. It will never invent a fact: if the
evidence is empty it says so and offers the next useful step. When a real LLM
(Ollama / any OpenAI-compatible endpoint) is available, the Brain Core hands
composition to that model instead and this engine becomes the fallback -- the
rest of the pipeline is identical either way.
"""

from __future__ import annotations

import random
import re
from typing import Iterator, Optional

from . import skills
from .llm_interface import LLMBackend

_IDENTITY = (
    "I'm JARVIS -- a local-first assistant that runs entirely on your machine. "
    "My Brain Core handles intent analysis, planning, tool selection, execution and "
    "verification myself; a language model is optional and only used for wording."
)

_CAPABILITIES = """Here's what I can actually do right now:

**Answer & research** - factual questions via Wikipedia and instant answers, definitions, live weather, news headlines, currency, translation, exact maths and dates.
**Images** - find real photos of a person, place or thing and show them inline, or generate an image/logo/poster/wallpaper locally.
**See** - OCR and read text from photos, screenshots, PDFs and DOCX files you attach.
**Act on this computer** - open apps, websites, folders; take screenshots; request system actions behind a confirmation gate.
**Read the web** - pull the text and images out of any URL you give me.
**Remember** - store facts and preferences encrypted locally, recall them later, and forget them on request.
**Plan & execute** - break a goal into a dependency-ordered plan, run the steps, verify the result, and keep the task list.
**Code & documents** - draft and run Python in a sandbox, write reports to PDF/DOCX.

Ask normally - "show me pictures of Ladakh", "open chrome", "weather in Pune",
"remember I prefer dark mode", "plan my exam revision" - I pick the tools myself."""

_GREETINGS = (
    "Good to see you. What are we working on?",
    "Online and listening. What do you need?",
    "All systems nominal. How can I help?",
    "Ready when you are.",
)

_THANKS = (
    "Any time.",
    "Happy to help.",
    "That's what I'm here for.",
    "Glad that worked.",
)

_BYE = (
    "Talk soon. I'll keep everything running.",
    "Signing off. Your memory and tasks are saved locally.",
    "Until next time.",
)


class LocalReasoningBackend(LLMBackend):
    """Always-available, offline answer composer.

    Satisfies the same `LLMBackend` interface as Ollama so `ModelRouter`,
    `AgentOrchestrator`, and the legacy routes can use it unchanged.
    """

    name = "jarvis-local-engine"
    kind = "local_engine"

    def __init__(self, knowledge=None, memory=None, seed: Optional[int] = None):
        self.knowledge = knowledge
        self.memory = memory
        self._rng = random.Random(seed)

    # ---- LLMBackend surface --------------------------------------------

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        return self.answer(prompt)

    def generate_stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        text = self.answer(prompt)
        # Word-level chunks so the UI's streaming path behaves the same as a
        # real model's token stream.
        buffer: list[str] = []
        for word in text.split(" "):
            buffer.append(word)
            if len(buffer) >= 4:
                yield " ".join(buffer) + " "
                buffer = []
        if buffer:
            yield " ".join(buffer)

    # ---- direct answering ----------------------------------------------

    def answer(self, prompt: str) -> str:
        """Best effort without any gathered evidence (legacy callers)."""
        maths = skills.solve_math(prompt)
        if maths and "value" in maths:
            return f"{maths['expression'].strip()} = **{maths['display']}**"
        if re.search(r"\b(what|current)\b.*\b(time|date)\b|\btoday\b", prompt, re.I):
            return skills.time_answer(prompt)
        if re.search(r"\b(who|what) are you\b|\byour name\b", prompt, re.I):
            return _IDENTITY
        if re.search(r"\bwhat can you do\b|\bcapabilities\b|^help$", prompt.strip(), re.I):
            return _CAPABILITIES
        local = self._from_local_stores(prompt)
        if local:
            return local
        return self.compose(prompt, evidence=[], intent="info.factual")

    # ---- composition used by the Brain Core ----------------------------

    def compose(self, question: str, evidence: list[dict], intent: str = "info.factual") -> str:
        """Write the final answer from gathered evidence.

        `evidence` items look like {"kind", "title", "text", "url", "source"}.
        """
        if intent == "smalltalk.greeting":
            return self._rng.choice(_GREETINGS)
        if intent == "smalltalk.thanks":
            return self._rng.choice(_THANKS)
        if intent == "smalltalk.bye":
            return self._rng.choice(_BYE)
        if intent == "smalltalk.identity":
            return _IDENTITY
        if intent == "smalltalk.capabilities":
            return _CAPABILITIES

        useful = [item for item in evidence if (item.get("text") or "").strip()]
        if not useful:
            return self._nothing_found(question, intent)

        # Direct-answer evidence (a tool that already produced final prose:
        # weather, time, maths, launcher, memory) is returned as-is.
        direct = [item for item in useful if item.get("kind") == "direct"]
        if direct:
            body = "\n\n".join(item["text"].strip() for item in direct)
            extra = [item for item in useful if item.get("kind") != "direct"]
            if extra:
                body += "\n\n" + self._reference_block(extra)
            return body

        primary = useful[0]
        summary = skills.summarize(primary["text"], max_sentences=4, query=question)
        if not summary:
            summary = skills.shorten(primary["text"], 500)

        lines: list[str] = []
        title = primary.get("title")
        if title and title.lower() not in question.lower():
            lines.append(f"**{title}**")
        lines.append(summary)

        supporting = [item for item in useful[1:] if item.get("text")]
        if supporting:
            points: list[str] = []
            for item in supporting[:4]:
                snippet = skills.summarize(item["text"], max_sentences=1, query=question) or skills.shorten(item["text"], 180)
                label = item.get("title") or item.get("source") or "note"
                points.append(f"**{label}** — {skills.shorten(snippet, 220)}")
            if points:
                lines.append("")
                lines.append(skills.bulletize(points))

        sources = self._reference_block(useful)
        if sources:
            lines.append("")
            lines.append(sources)
        return "\n".join(lines).strip()

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _reference_block(items: list[dict]) -> str:
        links: list[str] = []
        seen: set[str] = set()
        for item in items:
            url = item.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            label = item.get("title") or item.get("source") or url
            links.append(f"[{skills.shorten(str(label), 60)}]({url})")
            if len(links) >= 3:
                break
        return f"*Sources: {' · '.join(links)}*" if links else ""

    def _from_local_stores(self, prompt: str) -> Optional[str]:
        if self.knowledge:
            try:
                hits = self.knowledge.search(prompt, 3)
            except Exception:  # noqa: BLE001
                hits = []
            if hits:
                text = " ".join(hit.get("text", "") for hit in hits)
                summary = skills.summarize(text, max_sentences=3, query=prompt)
                if summary:
                    title = hits[0].get("title", "your knowledge base")
                    return f"From **{title}** in your local knowledge base:\n\n{summary}"
        return None

    def _nothing_found(self, question: str, intent: str) -> str:
        topic = skills.shorten(question.strip(), 80)
        if intent.startswith("media.image"):
            return (
                f"I couldn't retrieve an image for “{topic}”. The image sources I use "
                "(Wikimedia and Openverse) need a network connection — if you're offline, "
                "ask me to *generate* one instead and I'll render it locally."
            )
        if intent == "info.weather":
            return (
                "I couldn't get live weather. Tell me the city name and I'll geocode it, "
                "or check that this machine is online."
            )
        if intent in {"info.factual", "web.browse", "info.definition"}:
            terms = ", ".join(skills.keywords(question, 4)) or topic
            return (
                f"I don't have a reliable source for “{topic}” right now, and I won't guess.\n\n"
                f"Next steps I can take: search the web again with narrower terms ({terms}), "
                "read a specific URL if you paste one, or search anything you've already "
                "ingested into your local knowledge base."
            )
        return (
            f"I understood that as **{intent.replace('.', ' → ')}** but didn't get a usable "
            "result from the tools I tried. Give me one more detail and I'll retry."
        )
