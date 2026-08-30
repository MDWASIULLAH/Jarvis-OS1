"""
training/eval_set_fresh.py

A SECOND held-out set, written after tuning finished.

Why this file exists
--------------------
`eval_set.py` reached 83/83, but that number is optimistically biased: it was
consulted repeatedly while adding training data, and failures were fixed by
targeting them specifically. That process turns a holdout into a *validation*
set. Reporting 1.000 from it as a generalisation figure would overstate the
system's real accuracy.

These utterances were written afterwards and scored ONCE. Whatever they produce
is the honest headline number. Do not add training data aimed at these lines --
if you tune against this file, it stops being a holdout too, and you should
write `eval_set_fresh_2.py` instead.
"""

from __future__ import annotations

ROWS: list[tuple[str, str]] = [
    # smalltalk
    ("alright jarvis you there", "smalltalk.greeting"),
    ("cheers for sorting that", "smalltalk.thanks"),
    ("right im off then", "smalltalk.bye"),
    ("are you some kind of assistant", "smalltalk.identity"),
    ("give me the rundown of your features", "smalltalk.capabilities"),

    # information
    ("how deep is the mariana trench", "info.factual"),
    ("who invented the telephone", "info.factual"),
    ("what does ephemeral mean", "info.definition"),
    ("anything worth reading in the news", "info.news"),
    ("is it going to be chilly tomorrow", "info.weather"),
    ("what is 64 divided by 4", "info.math"),
    ("nineteen times six", "info.math"),
    ("what is the time in berlin", "info.time"),
    ("how do i say goodbye in portuguese", "info.translate"),
    ("convert 300 euros into pounds", "info.currency"),

    # media
    ("show me what a narwhal looks like", "media.image_search"),
    ("pictures of the taj mahal please", "media.image_search"),
    ("generate artwork of an underwater city", "media.image_generate"),
    ("make me an image of a clockwork bird", "media.image_generate"),
    ("find me a video on knot tying", "media.video_search"),

    # actions
    ("fire up spotify", "action.open_app"),
    ("open the calculator app", "action.open_app"),
    ("head over to reddit", "action.web_open"),
    ("bring up linkedin", "action.web_open"),
    ("send this machine to sleep", "action.system_control"),
    ("crank the volume up", "action.system_control"),
    ("grab a shot of my display", "action.screenshot"),

    # memory
    ("keep a note that my passport expires in june", "memory.remember"),
    ("what do you have saved about my diet", "memory.recall"),
    ("scrub the note about my old job", "memory.forget"),

    # tasks and documents
    ("map out how to redecorate my kitchen", "task.plan"),
    ("help me structure a study timetable", "task.plan"),
    ("show me how to reverse a linked list in python", "task.code"),
    ("my docker build keeps failing why", "task.code"),
    ("put together a white paper on water scarcity", "doc.write"),
    ("draft a reference letter for a colleague", "doc.write"),
    ("boil this attached contract down for me", "doc.read"),
    ("what is going on in this photo", "vision.analyze"),
    ("read the label in this image", "vision.analyze"),

    # web and email
    ("dig around the web for camping gear prices", "web.browse"),
    ("https://news.ycombinator.com", "web.browse"),
    ("write an email to the council about parking", "email.draft"),
    ("compose a quick note to my manager", "email.draft"),
]


def rows() -> list[tuple[str, str]]:
    return list(ROWS)
