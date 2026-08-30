import tempfile
from datetime import datetime
from pathlib import Path

from app.memory.memory_store import MemorySystem, PredictiveMemory, ShortTermMemory


def test_long_term_remember_and_recall():
    with tempfile.TemporaryDirectory() as tmp:
        mem = MemorySystem(Path(tmp))
        try:
            mem.long_term.remember("preferred_drink", "tea", category="preference")
            assert mem.long_term.recall("preferred_drink") == "tea"
        finally:
            mem.close()


def test_forget_removes_fact():
    with tempfile.TemporaryDirectory() as tmp:
        mem = MemorySystem(Path(tmp))
        try:
            mem.long_term.remember("favorite_color", "blue")
            assert mem.long_term.forget("favorite_color") is True
            assert mem.long_term.recall("favorite_color") is None
        finally:
            mem.close()


def test_facts_are_encrypted_at_rest():
    with tempfile.TemporaryDirectory() as tmp:
        mem = MemorySystem(Path(tmp))
        try:
            mem.long_term.remember("secret", "super-private-value")
            raw = (Path(tmp) / "long_term.db").read_bytes()
            assert b"super-private-value" not in raw
        finally:
            mem.close()


def test_short_term_caps_at_max_turns():
    stm = ShortTermMemory(max_turns=3)
    for i in range(5):
        stm.add("user", f"turn {i}")
    assert len(stm.recent()) == 3
    assert stm.recent()[0].content == "turn 2"


def test_predictive_routine_detection():
    with tempfile.TemporaryDirectory() as tmp:
        pred = PredictiveMemory(Path(tmp) / "pred.db")
        try:
            for _ in range(4):
                pred.log_action("check_email", when=datetime(2026, 1, 5, 9, 0))  # Monday 9am
            routines = pred.routine_for_hour(9, weekday=0, min_occurrences=3)
            assert "check_email" in routines
        finally:
            pred.close()
