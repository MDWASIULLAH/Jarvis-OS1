"""
brain/classifier.py

A dependency-free averaged-perceptron text classifier.

Why not Naive Bayes (the first attempt): NB assumes features are independent.
That assumption is badly violated by character n-grams, which are hugely
correlated with each other and with the words they come from. In practice a
single high-frequency word could dominate an entire prediction -- "how does a
refrigerator work" classified as "thanks" purely because "work" appears in
"nice work". Measured on the hand-written held-out set, NB scored 0.58 on the
utterances that reached the model.

An averaged perceptron is discriminative: it only adjusts weights when it makes
a mistake, so it learns that "work" is *not* decisive once it sees the word in
several intents. Averaging the weights over all updates gives most of the
generalisation benefit of a large-margin method in a few lines of code.

Still pure Python, still trains in seconds on CPU, still ships as plain JSON.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Iterable, Optional, Sequence


class AveragedPerceptron:
    """Multiclass averaged perceptron over sparse named features."""

    def __init__(self) -> None:
        # weights[label][feature] -> float
        self.weights: dict[str, dict[str, float]] = {}
        self.labels: list[str] = []
        self.feature_scale: dict[str, float] = {}

    # ------------------------------------------------------------------ score
    def _scores(self, features: Sequence[tuple[str, float]]) -> dict[str, float]:
        totals = {label: 0.0 for label in self.labels}
        for label in self.labels:
            table = self.weights[label]
            total = 0.0
            for name, value in features:
                weight = table.get(name)
                if weight:
                    total += weight * value
            totals[label] = total
        return totals

    def predict(self, features: Sequence[tuple[str, float]]) -> tuple[str, dict[str, float]]:
        scores = self._scores(features)
        if not scores:
            return "", {}
        best = max(scores, key=lambda label: scores[label])
        return best, scores

    def probabilities(self, features: Sequence[tuple[str, float]]) -> dict[str, float]:
        """Softmax over the margins, used only as a calibrated-ish confidence.

        A perceptron has no native probability. Squashing the margins gives the
        Decision Engine a usable "how sure am I" signal for choosing between a
        specific handler and general reasoning; it is not a true likelihood and
        is not presented to the user as one.
        """
        scores = self._scores(features)
        if not scores:
            return {}
        top = max(scores.values())
        # Temperature matters here. Perceptron margins on L2-normalised features
        # are small in absolute terms, so dividing by 2.0 flattened every
        # distribution into 0.03-0.20 and made the numbers useless for deciding
        # whether to trust the label. Scaling by the observed margin spread
        # instead produces a usable separation between confident and unsure
        # predictions. This is a heuristic confidence, not a true probability.
        ordered = sorted(scores.values(), reverse=True)
        spread = (ordered[0] - ordered[min(len(ordered) - 1, 4)]) or 1.0
        temperature = max(0.15, spread / 3.0)
        exponentials = {
            label: math.exp((value - top) / temperature) for label, value in scores.items()
        }
        total = sum(exponentials.values()) or 1.0
        return {label: value / total for label, value in exponentials.items()}

    # ------------------------------------------------------------------ train
    def train(
        self,
        rows: Sequence[tuple[Sequence[tuple[str, float]], str]],
        epochs: int = 12,
        seed: int = 7,
    ) -> None:
        self.labels = sorted({label for _, label in rows})
        self.weights = {label: {} for label in self.labels}
        totals: dict[str, dict[str, float]] = {label: {} for label in self.labels}
        stamps: dict[str, dict[str, int]] = {label: {} for label in self.labels}
        step = 1
        rng = random.Random(seed)
        order = list(rows)

        def adjust(label: str, name: str, delta: float) -> None:
            table = self.weights[label]
            total_table = totals[label]
            stamp_table = stamps[label]
            current = table.get(name, 0.0)
            last = stamp_table.get(name, 0)
            total_table[name] = total_table.get(name, 0.0) + (step - last) * current
            stamp_table[name] = step
            table[name] = current + delta

        for _ in range(epochs):
            rng.shuffle(order)
            for features, gold in order:
                guess, _ = self.predict(features)
                if guess != gold:
                    for name, value in features:
                        adjust(gold, name, value)
                        if guess:
                            adjust(guess, name, -value)
                step += 1

        # Average: this is what makes the model generalise instead of chasing
        # the last few training examples it happened to see.
        for label in self.labels:
            table = self.weights[label]
            total_table = totals[label]
            stamp_table = stamps[label]
            averaged: dict[str, float] = {}
            for name, weight in table.items():
                accumulated = total_table.get(name, 0.0) + (step - stamp_table.get(name, 0)) * weight
                value = accumulated / step
                if abs(value) > 1e-6:
                    averaged[name] = round(value, 6)
            self.weights[label] = averaged

    # ------------------------------------------------------------------- i/o
    def to_dict(self) -> dict:
        return {"format": "averaged_perceptron_v1", "labels": self.labels, "weights": self.weights}

    @classmethod
    def from_dict(cls, payload: dict) -> "AveragedPerceptron":
        model = cls()
        model.labels = list(payload.get("labels", []))
        model.weights = {label: dict(table) for label, table in payload.get("weights", {}).items()}
        for label in model.labels:
            model.weights.setdefault(label, {})
        return model

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Optional["AveragedPerceptron"]:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

    @property
    def feature_count(self) -> int:
        return len({name for table in self.weights.values() for name in table})
