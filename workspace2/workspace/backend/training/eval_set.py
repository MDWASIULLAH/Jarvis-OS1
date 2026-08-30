"""
training/eval_set.py

A hand-written, held-out evaluation set.

Why this file exists: `templates.py` generates training rows from templates, so
a random train/test split of that data scores ~100% simply because the test
rows share templates with the training rows. That number measures memorisation,
not skill, and reporting it would be misleading.

Every utterance below is written by hand in phrasing that does NOT appear in
templates.py, using entities the model was never trained on. It includes typos,
Hinglish, terse commands, and deliberately ambiguous requests -- the things real
users type. This is the number worth quoting.
"""

from __future__ import annotations

# (utterance, expected_intent)
EVAL_ROWS: list[tuple[str, str]] = [
    # -- smalltalk ------------------------------------------------------------
    ("yo jarvis you up", "smalltalk.greeting"),
    ("morning", "smalltalk.greeting"),
    ("heyy", "smalltalk.greeting"),
    ("cheers mate that worked", "smalltalk.thanks"),
    ("ty", "smalltalk.thanks"),
    ("catch you later", "smalltalk.bye"),
    ("im off to bed", "smalltalk.bye"),
    ("so what exactly are you", "smalltalk.identity"),
    ("do you have a name", "smalltalk.identity"),
    ("which llm is running you", "smalltalk.identity"),
    ("give me a rundown of your skills", "smalltalk.capabilities"),
    ("what all can i ask you", "smalltalk.capabilities"),

    # -- factual / definition (entities never seen in training) --------------
    ("who was ludwig van beethoven", "info.factual"),
    ("tell me about the great barrier reef", "info.factual"),
    ("what do you know about jupiter", "info.factual"),
    ("how does a refrigerator work", "info.factual"),
    ("why do leaves change colour in autumn", "info.factual"),
    ("how deep is the mariana trench", "info.factual"),
    ("what is the population of canada", "info.factual"),
    ("define ephemeral", "info.definition"),
    ("whats the meaning of ubiquitous", "info.definition"),
    ("dictionary meaning of pragmatic", "info.definition"),

    # -- news / weather / time ----------------------------------------------
    ("anything happening in the world today", "info.news"),
    ("give me todays headlines", "info.news"),
    ("whats new in formula 1", "info.news"),
    ("will it rain tomorrow in chennai", "info.weather"),
    ("hows the weather looking in oslo", "info.weather"),
    ("is it cold outside", "info.weather"),
    ("whats the time in singapore", "info.time"),
    ("what date is it", "info.time"),
    ("how long until christmas", "info.time"),

    # -- math ----------------------------------------------------------------
    ("whats 87 times 14", "info.math"),
    ("work out 30 percent of 900", "info.math"),
    ("square root of 625", "info.math"),
    ("add 450 and 275", "info.math"),

    # -- translate / currency -----------------------------------------------
    ("say hello in portuguese", "info.translate"),
    ("how do i write goodbye in korean", "info.translate"),
    ("whats 75 pounds in rupees", "info.currency"),
    ("convert 300 aud to usd", "info.currency"),

    # -- media ---------------------------------------------------------------
    ("show me what a narwhal looks like", "media.image_search"),
    ("i wanna see pics of santorini", "media.image_search"),
    ("pull up photos of the golden gate bridge", "media.image_search"),
    ("picture of a snow leopard", "media.image_search"),
    ("make me an image of a dragon over a castle", "media.image_generate"),
    ("draw a watercolour of a rainy street", "media.image_generate"),
    ("generate artwork of an underwater city", "media.image_generate"),
    ("find me a video on sourdough baking", "media.video_search"),

    # -- actions -------------------------------------------------------------
    ("open vlc", "action.open_app"),
    ("fire up spotify", "action.open_app"),
    ("launch the calculator app", "action.open_app"),
    ("open notepad pls", "action.open_app"),
    ("jump over to the bbc website", "action.web_open"),
    ("open reddit in chrome", "action.web_open"),
    ("pull up github", "action.web_open"),
    ("turn the volume down", "action.system_control"),
    ("lock my laptop", "action.system_control"),
    ("reboot the machine", "action.system_control"),
    ("grab a screenshot for me", "action.screenshot"),
    ("capture whats on screen", "action.screenshot"),

    # -- memory --------------------------------------------------------------
    ("remember that i drive a swift", "memory.remember"),
    ("make a note that my manager is priya", "memory.remember"),
    ("do you recall anything about me", "memory.recall"),
    ("whats my job again", "memory.recall"),
    ("wipe what you saved about my car", "memory.forget"),

    # -- tasks ---------------------------------------------------------------
    ("help me lay out a plan for my thesis", "task.plan"),
    ("split this migration into stages", "task.plan"),
    ("write me a python function to dedupe a list", "task.code"),
    ("whats wrong with my recursion", "task.code"),

    # -- documents / vision --------------------------------------------------
    ("draft a cover letter for a design role", "doc.write"),
    ("put together a report on water scarcity", "doc.write"),
    ("whats in this attached pdf", "doc.read"),
    ("pull the key points out of this file", "doc.read"),
    ("describe whats in this picture", "vision.analyze"),
    ("read the writing in this photo", "vision.analyze"),

    # -- web / email ---------------------------------------------------------
    ("look online for reviews of the pixel", "web.browse"),
    ("fetch this page and summarise it", "web.browse"),
    ("write an email asking for a deadline extension", "email.draft"),
    ("compose a thank you note to the interviewer", "email.draft"),

    # -- typos and Hinglish (robustness) ------------------------------------
    ("scrensht please", "action.screenshot"),
    ("wat is the wether in delhi", "info.weather"),
    ("chrome kholo", "action.open_app"),
    ("mujhe taj mahal ki photo dikhao", "media.image_search"),
    ("calulate 45*3", "info.math"),
]


def rows() -> list[tuple[str, str]]:
    return list(EVAL_ROWS)
