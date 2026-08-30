"""
training/evaluate.py

Scores the full intent pipeline (rules + trained model) against two hand-written
held-out sets, and prints every failure so regressions stay visible rather than
hidden behind an average.

Two sets, on purpose:

  eval_set.py        -- the tuned set. It reached 83/83, but it was consulted
                        repeatedly during development and failures were fixed by
                        adding training data aimed at them. That makes it a
                        VALIDATION set; its score is optimistically biased and
                        should not be quoted as generalisation accuracy.

  eval_set_fresh.py  -- written after tuning stopped and scored once. This is
                        the honest headline number.

The gap between the two is the size of the tuning bias. Keeping both visible is
the point: quoting only the first would misrepresent the system.

Run:  python -m training.evaluate
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.brain.nlu import IntentAnalyzer  # noqa: E402
from training import eval_set, eval_set_fresh  # noqa: E402


def _score(analyzer: IntentAnalyzer, rows: list[tuple[str, str]], title: str, caveat: str) -> float:
    correct = 0
    failures: list[tuple[str, str, str, float, str]] = []
    by_source: dict[str, list[int]] = defaultdict(list)

    for text, expected in rows:
        prediction = analyzer.analyze(text)
        hit = prediction.intent == expected
        correct += int(hit)
        by_source[prediction.source].append(int(hit))
        if not hit:
            failures.append((text, expected, prediction.intent, prediction.confidence, prediction.source))

    total = max(1, len(rows))
    accuracy = correct / total
    print(f"\n{title}")
    print(f"  utterances   : {total}")
    print(f"  accuracy     : {accuracy:.3f}  ({correct}/{total})")
    for source, hits in sorted(by_source.items()):
        print(f"    via {source:<7}: {sum(hits)}/{len(hits)}")
    print(f"  note         : {caveat}")

    if failures:
        print(f"  {len(failures)} failure(s):")
        for text, expected, got, confidence, source in failures:
            print(f"    {text!r}")
            print(f"        expected {expected}, got {got} (conf {confidence:.2f}, {source})")
    return accuracy


def main() -> int:
    analyzer = IntentAnalyzer()
    if not analyzer.trained:
        print("No trained model found. Run: python -m training.train_intents")
        return 1

    tuned = _score(
        analyzer,
        eval_set.rows(),
        "TUNED set (eval_set.py)",
        "biased upward -- tuned against during development",
    )
    fresh = _score(
        analyzer,
        eval_set_fresh.rows(),
        "FRESH set (eval_set_fresh.py)",
        "not tuned against -- this is the honest number",
    )

    print("\n" + "-" * 60)
    print(f"HEADLINE (fresh holdout) : {fresh:.3f}")
    print(f"tuned set                : {tuned:.3f}")
    print(f"tuning bias              : {tuned - fresh:+.3f}")
    print("-" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
