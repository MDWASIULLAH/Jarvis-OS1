"""The "run/debug this code" path.

`capabilities/code_executor.run_python` existed, worked, and was imported by
nothing: the only handler for a coding request generated text, so pasting a
snippet and asking for its output returned a "tell me your requirements"
template. Worse, "run this: print(...)" classifies as `info.math`, so the
calculator took it and replied "I couldn't evaluate ..." for code that runs
fine, and a fenced block classifies as `unknown`, which fell through to a web
search.

These tests pin the behaviour that matters: real code produces real output,
broken code produces the real error, and prose is still never executed.
"""

from fastapi.testclient import TestClient

from app.brain.cognition import extract_python
from app.main import app

client = TestClient(app)


def _chat(text: str) -> dict:
    response = client.post("/v1/chat", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def _tools(body: dict) -> dict[str, tuple[bool, str]]:
    return {call["tool"]: (call["ok"], call["detail"]) for call in body["tools_used"]}


# ---------------------------------------------------------------- extraction

def test_extract_python_finds_snippets_without_matching_prose():
    # Fenced blocks and explicit run/debug lead-ins are code.
    assert extract_python("run this python: print(1 + 1)") == "print(1 + 1)"
    assert extract_python("output?\n```python\nprint(2**10)\n```") == "print(2**10)"
    assert extract_python("```\nfor i in range(2):\n    print(i)\n```") == "for i in range(2):\n    print(i)"

    # Prose describing code is not code. A false positive here would execute
    # something the user only meant as a description.
    assert extract_python("write me a function that reverses a string") is None
    assert extract_python("can you explain how decorators work") is None
    assert extract_python("run the tests for me please") is None
    assert extract_python("debug this: the app crashes on startup") is None
    # `compile()` accepts a bare word as an expression statement, so the
    # whole-message fallback must not fire on one.
    assert extract_python("hello") is None
    # Only Python is runnable here.
    assert extract_python("```js\nconsole.log(1)\n```") is None


def test_broken_snippet_is_still_extracted_so_it_can_be_diagnosed():
    """"debug this: <broken code>" is the whole point of the debug path, so the
    extractor must not require the snippet to compile."""
    assert extract_python("debug this:\ndef f(:\n    pass") == "def f(:\n    pass"


# ------------------------------------------------------------------ chat path

def test_pasted_snippet_actually_runs_and_reports_real_output():
    body = _chat("run this python: print(sum(i * i for i in range(1, 11)))")
    ok, detail = _tools(body)["code_execution"]
    assert ok is True and detail == "exit 0"
    # 385 is the real answer; it can only appear if the code ran.
    assert "385" in body["reply"]


def test_fenced_block_runs_even_though_it_classifies_as_unknown():
    body = _chat("what does this output?\n```python\nfor i in range(3):\n    print(i * 2)\n```")
    assert _tools(body)["code_execution"][0] is True
    assert "0" in body["reply"] and "2" in body["reply"] and "4" in body["reply"]


def test_crashing_snippet_reports_the_real_traceback_and_is_not_marked_ok():
    body = _chat("debug this:\nnums = [1, 2, 3]\nprint(nums[7])")
    ok, detail = _tools(body)["code_execution"]
    assert ok is False and detail == "exit 1"
    assert "IndexError" in body["reply"]
    # The tempfile path is an implementation detail; showing it makes the error
    # look like it came from a file the user has never seen.
    assert 'File "your snippet"' in body["reply"]
    assert "tmp" not in body["reply"]


def test_syntax_error_is_diagnosed_instead_of_executed():
    body = _chat("debug this:\ndef broken(:\n    return 1")
    ok, detail = _tools(body)["code_execution"]
    assert ok is True and detail == "syntax_error"
    assert "syntax error" in body["reply"].lower()


def test_prose_code_request_still_goes_to_generation_not_execution():
    body = _chat("write me a function that reverses a string")
    tools = _tools(body)
    assert "code_execution" not in tools
    assert "code_generation" in tools


def test_plain_arithmetic_still_uses_the_calculator():
    """info.math must keep its fast path; only pasted code diverts from it."""
    body = _chat("what is 17 * 23")
    tools = _tools(body)
    assert "code_execution" not in tools
    assert tools["calculator"][0] is True
    assert "391" in body["reply"]


def test_disabling_the_code_runner_tool_actually_stops_execution():
    """The toggle used to be cosmetic -- only `GET /v1/tools` ever read it, so
    switching it off changed nothing about what ran."""
    try:
        client.post("/v1/tools/toggle", json={"tool_id": "code_runner", "enabled": False})
        body = _chat("run this python: print(1 + 1)")
        ok, detail = _tools(body)["code_execution"]
        assert ok is False and detail == "disabled"
        assert "switched off" in body["reply"]
    finally:
        client.post("/v1/tools/toggle", json={"tool_id": "code_runner", "enabled": True})

    # And it runs again once re-enabled.
    body = _chat("run this python: print(1 + 1)")
    assert _tools(body)["code_execution"][0] is True
