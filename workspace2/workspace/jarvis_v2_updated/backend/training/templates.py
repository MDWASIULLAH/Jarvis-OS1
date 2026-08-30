"""
training/templates.py

The seed corpus for JARVIS's intent model.

This is real, reproducible training data: templates x slot values expand into
thousands of labelled utterances, which `build_dataset.py` writes to CSV and
`train_intents.py` trains a Naive Bayes classifier on. Everything runs
offline in under a second on a CPU -- no GPU, no downloads, no API keys.

Why this instead of "fine-tune an LLM on Kaggle data": an 8B model cannot be
trained here, and pretending otherwise would produce a broken artifact. What
*is* honest and useful is a small supervised classifier that decides which of
JARVIS's ~30 capabilities a request needs. That decision is what was actually
missing -- the assistant used to send everything straight to a chat model.

You can still add external data: drop any CSV with `text,intent` columns into
`training/datasets/extra/` (Kaggle exports work if you rename the columns) and
`build_dataset.py` will merge it in automatically.
"""

from __future__ import annotations

import itertools
import random

# ---------------------------------------------------------------- slot values

PEOPLE = [
    "shah rukh khan", "srk", "albert einstein", "virat kohli", "elon musk",
    "marie curie", "cristiano ronaldo", "apj abdul kalam", "taylor swift",
    "steve jobs", "lata mangeshkar", "sachin tendulkar",
    # A wider spread of eras and regions so the classifier learns the *question
    # shape* rather than memorising a handful of familiar names.
    "alan turing", "ada lovelace", "isaac newton", "nikola tesla",
    "mahatma gandhi", "nelson mandela", "cleopatra", "leonardo da vinci",
    "rosalind franklin", "srinivasa ramanujan", "cv raman", "homi bhabha",
    "ratan tata", "lionel messi", "serena williams", "mary shelley",
    "frida kahlo", "confucius", "ibn sina", "katherine johnson",
]

PLACES = [
    "mount everest", "the taj mahal", "paris", "tokyo", "kerala", "iceland",
    "the eiffel tower", "goa", "the grand canyon", "dubai", "leh ladakh",
]

THINGS = [
    "a red panda", "a black hole", "the space shuttle", "a lamborghini",
    "a peacock", "the northern lights", "a formula 1 car", "a blue whale",
    "cherry blossoms", "a mechanical keyboard",
    "photosynthesis", "vaccines", "quantum computing", "the internet",
    "solar panels", "dna", "earthquakes", "machine learning", "gravity",
    "the immune system", "blockchain", "nuclear fusion", "monsoons",
]

APPS = [
    "chrome", "google chrome", "notepad", "calculator", "spotify", "vs code",
    "visual studio code", "terminal", "file explorer", "settings", "firefox",
    "whatsapp", "youtube app", "camera",
]

SITES = [
    "youtube", "github", "google", "wikipedia", "gmail", "stack overflow",
    "reddit", "linkedin", "twitter",
]

CITIES = ["delhi", "mumbai", "london", "new york", "bangalore", "tokyo", "sydney", "berlin"]

TOPICS = ["technology", "sports", "world news", "science", "business", "cricket", "ai", "space"]

WORDS = ["serendipity", "photosynthesis", "entropy", "algorithm", "monsoon", "quantum", "recursion"]

LANGS = ["hindi", "spanish", "french", "german", "japanese", "tamil", "arabic"]

MATHS = [
    "23 * 47", "15% of 2400", "sqrt(144)", "2^10", "(45+55)/4", "9 factorial",
    "18 + 27 * 3", "120 / 8 - 5",
]

CODE_TASKS = [
    "reverse a linked list in python", "a python script to rename files",
    "why my for loop is off by one", "a regex for email validation",
    "fix this stack trace", "a fastapi endpoint for uploads",
    "unit tests for my parser",
]

DOC_TASKS = [
    "a report about renewable energy", "a resume for a data analyst",
    "meeting minutes from my notes", "an essay on climate change",
]

FACTS = [
    "how tall is mount everest", "who invented the telephone",
    "what is the capital of australia", "how far is the moon",
    "when did india gain independence", "what causes rainbows",
    "how many bones are in the human body", "what is the speed of light",
    "who wrote the mahabharata", "why is the sky blue",
]

PREFS = [
    ("my favourite colour is blue", "colour"),
    ("i work as a backend developer", "job"),
    ("i live in pune", "city"),
    ("my birthday is on 3rd april", "birthday"),
    ("i prefer dark mode", "theme"),
    ("i am allergic to peanuts", "allergy"),
]

# ---------------------------------------------------------------- templates
# Each entry: intent -> list of (template, slot_pool) pairs. `{}` is filled
# from the pool; a pool of None means the template is already a full utterance.

TEMPLATES: dict[str, list[tuple[str, list | None]]] = {
    "smalltalk.greeting": [
        ("hi", None), ("hello", None), ("hey jarvis", None), ("good morning", None),
        ("good evening jarvis", None), ("yo", None), ("hey there", None),
        ("hello are you online", None), ("jarvis you there", None), ("namaste", None),
        ("wake up jarvis", None), ("hi buddy", None),
    ],
    "smalltalk.thanks": [
        ("thanks", None), ("thank you so much", None), ("thanks a lot jarvis", None),
        ("appreciate it", None), ("that was helpful thanks", None), ("perfect thanks", None),
        ("nice work", None), ("great job", None),
    ],
    "smalltalk.bye": [
        ("bye", None), ("goodbye jarvis", None), ("see you later", None),
        ("good night", None), ("i am logging off", None), ("talk to you tomorrow", None),
        ("shutting down for today", None),
    ],
    "smalltalk.identity": [
        ("who are you", None), ("what are you", None), ("what is your name", None),
        ("are you an ai", None), ("tell me about yourself", None),
        ("are you jarvis", None), ("who made you", None), ("what model are you", None),
    ],
    "smalltalk.capabilities": [
        ("what can you do", None), ("list your features", None),
        ("what are your capabilities", None), ("help", None), ("how do i use you", None),
        ("show me what you can do", None), ("what commands do you support", None),
        ("can you do tasks for me", None),
    ],
    "info.factual": [
        ("{}", FACTS),
        ("tell me about {}", PEOPLE + PLACES),
        # Past-tense forms were missing entirely, so "who was Alan Turing" --
        # one of the commonest ways to ask about a historical figure -- had no
        # matching example and drifted to whatever label the character n-grams
        # of the unfamiliar name happened to favour.
        ("who is {}", PEOPLE),
        ("who was {}", PEOPLE),
        ("who were {}", PEOPLE),
        ("what is {}", THINGS),
        ("what was {}", THINGS),
        ("what are {}", THINGS),
        ("give me information on {}", PLACES + THINGS),
        ("explain {} to me", THINGS),
        ("explain {}", THINGS),
        ("i want details about {}", PLACES),
        ("tell me more about {}", PEOPLE + THINGS),
        ("what do you know about {}", PEOPLE + PLACES + THINGS),
        ("how does {} work", THINGS),
        ("how do {} work", THINGS),
        ("why is {} important", THINGS + PEOPLE),
        ("where is {}", PLACES),
        ("history of {}", PLACES + THINGS),
        ("facts about {}", PEOPLE + PLACES + THINGS),
        ("summarise {} for me", THINGS),
        ("give me a quick overview of {}", THINGS + PLACES),
    ],
    "info.definition": [
        ("define {}", WORDS),
        ("what does {} mean", WORDS),
        ("meaning of {}", WORDS),
        ("definition of the word {}", WORDS),
        ("give me the dictionary meaning of {}", WORDS),
    ],
    "info.news": [
        ("what's the news today", None),
        ("latest {} news", TOPICS),
        ("show me headlines about {}", TOPICS),
        ("any updates on {}", TOPICS),
        ("top stories right now", None),
        ("brief me on today's headlines", None),
    ],
    "info.weather": [
        ("what's the weather", None),
        ("weather in {}", CITIES),
        ("is it going to rain in {}", CITIES),
        ("temperature in {} right now", CITIES),
        ("do i need an umbrella today", None),
        ("how hot is it in {}", CITIES),
        ("forecast for {}", CITIES),
    ],
    "info.time": [
        ("what time is it", None), ("what's today's date", None),
        ("what day is it today", None), ("tell me the current time", None),
        ("how many days until new year", None), ("what's the time in tokyo", None),
    ],
    "info.math": [
        ("calculate {}", MATHS),
        ("what is {}", MATHS),
        ("solve {}", MATHS),
        ("compute {} for me", MATHS),
        ("{} equals what", MATHS),
    ],
    "info.translate": [
        ("translate good morning to {}", LANGS),
        ("how do you say thank you in {}", LANGS),
        ("translate this sentence into {}", LANGS),
        ("what is water in {}", LANGS),
    ],
    "info.currency": [
        ("convert 100 usd to inr", None), ("how much is 50 euro in dollars", None),
        ("exchange rate for gbp to inr", None), ("convert 2000 inr to yen", None),
    ],
    "media.image_search": [
        ("show me a picture of {}", PEOPLE + PLACES + THINGS),
        ("show me images of {}", PLACES + THINGS),
        ("i want to see {}", PLACES + THINGS),
        ("find photos of {}", PEOPLE + PLACES),
        ("who is {} show me his image", PEOPLE),
        ("send me pictures of {}", PLACES),
        ("what does {} look like", PEOPLE + THINGS),
        ("image of {}", PEOPLE + PLACES + THINGS),
        ("show his photo", None),
        ("show me her picture", None),
        ("get me a gallery of {}", PLACES),
    ],
    "media.image_generate": [
        ("generate an image of {}", THINGS + PLACES),
        ("create a picture of {}", THINGS),
        ("draw {}", THINGS),
        ("design a logo for my startup", None),
        ("make a wallpaper of {}", PLACES),
        ("create a poster for a music festival", None),
        ("visualize {} in neon style", THINGS),
        ("paint {} as digital art", THINGS),
        ("ai generate {}", THINGS),
        ("make me an image of a futuristic city", None),
    ],
    "media.video_search": [
        ("play a video about {}", TOPICS),
        ("find a youtube video on {}", TOPICS),
        ("show me a tutorial for {}", CODE_TASKS),
        ("play some music video", None),
    ],
    "action.open_app": [
        ("open {}", APPS),
        ("launch {}", APPS),
        ("start {} for me", APPS),
        ("can you open {}", APPS),
        ("run {}", APPS),
        ("open the {} app", APPS),
    ],
    "action.web_open": [
        ("open {}", SITES),
        ("go to {}", SITES),
        ("open {} in the browser", SITES),
        ("take me to {}", SITES),
        ("browse to {}.com", SITES),
    ],
    "action.system_control": [
        ("shutdown the computer", None), ("restart my pc", None),
        ("lock the screen", None), ("increase the volume", None),
        ("mute the sound", None), ("put the laptop to sleep", None),
        ("turn off wifi", None),
    ],
    "action.screenshot": [
        ("take a screenshot", None), ("capture my screen", None),
        ("screenshot this window", None), ("grab a picture of the screen", None),
    ],
    "memory.remember": [
        ("remember that {}", [p[0] for p in PREFS]),
        ("note that {}", [p[0] for p in PREFS]),
        ("save this: {}", [p[0] for p in PREFS]),
        ("keep in mind {}", [p[0] for p in PREFS]),
        ("don't forget that {}", [p[0] for p in PREFS]),
    ],
    "memory.recall": [
        ("what do you remember about me", None),
        ("what is my favourite colour", None),
        ("where do i live", None),
        ("do you know my job", None),
        ("recall my preferences", None),
        ("what did i tell you earlier", None),
    ],
    "memory.forget": [
        ("forget my favourite colour", None), ("delete what you know about me", None),
        ("remove that memory", None), ("erase my saved city", None),
    ],
    "task.plan": [
        ("plan my week", None),
        ("help me organize a birthday party", None),
        ("break this project into steps", None),
        ("make a roadmap to learn machine learning", None),
        ("i need a study schedule for exams", None),
        ("create a task list for the website launch", None),
        ("prioritize these tasks for me", None),
    ],
    "task.code": [
        ("write code to {}", CODE_TASKS),
        ("help me with {}", CODE_TASKS),
        ("debug {}", CODE_TASKS),
        ("show me python for {}", CODE_TASKS),
        ("run this python snippet", None),
        ("review my function", None),
    ],
    "doc.write": [
        ("write {}", DOC_TASKS),
        ("draft {}", DOC_TASKS),
        ("create a pdf with {}", DOC_TASKS),
        ("make a word document about renewable energy", None),
        ("summarize this into a report", None),
    ],
    "doc.read": [
        ("read this pdf", None), ("summarize the attached document", None),
        ("what does this file say", None), ("extract the text from this docx", None),
        ("go through this report and tell me the key points", None),
    ],
    "vision.analyze": [
        ("what is in this image", None), ("describe this photo", None),
        ("read the text in this picture", None), ("what does this screenshot show", None),
        ("scan this receipt", None), ("ocr this image", None),
        ("analyse the chart in this image", None),
    ],
    "web.browse": [
        ("search the web for {}", TOPICS),
        ("look up {} online", PEOPLE + TOPICS),
        ("find articles about {}", TOPICS),
        ("what does wikipedia say about {}", PLACES + PEOPLE),
        ("get the content of this url", None),
        ("open this link and summarize it", None),
    ],
    "email.draft": [
        ("draft an email to my boss about leave", None),
        ("write a mail to the client", None),
        ("reply to this email politely", None),
        ("compose an email requesting a meeting", None),
    ],
}

# Light surface noise so the model does not overfit to perfect phrasing.
PREFIXES = ["", "jarvis ", "hey jarvis ", "please ", "could you ", "can you ", "ok jarvis "]
SUFFIXES = ["", " please", " now", " for me", " quickly", "?", " thanks"]


def generate(seed: int = 7, per_template: int = 6) -> list[tuple[str, str]]:
    """Expand the templates into labelled (text, intent) rows."""
    rng = random.Random(seed)
    rows: list[tuple[str, str]] = []
    for intent, entries in TEMPLATES.items():
        for template, pool in entries:
            values = pool if pool else [None]
            picks = values if len(values) <= per_template else rng.sample(values, per_template)
            for value in picks:
                base = template.format(value) if value is not None else template
                for prefix, suffix in itertools.product(
                    rng.sample(PREFIXES, 3), rng.sample(SUFFIXES, 3)
                ):
                    rows.append(((prefix + base + suffix).strip(), intent))
    # De-duplicate while keeping order stable for reproducible training runs.
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for text, intent in rows:
        key = f"{text}|{intent}"
        if key in seen:
            continue
        seen.add(key)
        unique.append((text, intent))
    rng.shuffle(unique)
    return unique


INTENTS = tuple(sorted(TEMPLATES))
