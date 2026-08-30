"""
memory/semantic_search.py

Lightweight semantic-ish search over long-term facts using TF-IDF.

It uses scikit-learn when it happens to be installed, and otherwise falls
back to an equivalent pure-Python TF-IDF with cosine similarity. That matters
because scikit-learn is a large build dependency, and importing it at module
scope previously made the whole backend fail to start on a clean machine --
`ModuleNotFoundError: No module named 'sklearn'` before a single route loaded.

Either path works fully offline with no model download. Swap in real sentence
embeddings later; the interface below stays the same, so nothing upstream
needs to change.
"""

from __future__ import annotations

import math
import re
from collections import Counter

try:  # optional acceleration
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    _SKLEARN = True
except ImportError:  # pragma: no cover - depends on the host environment
    _SKLEARN = False

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has", "have",
    "he", "her", "his", "i", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our",
    "she", "that", "the", "their", "them", "there", "they", "this", "to", "was", "we",
    "were", "what", "when", "where", "which", "who", "will", "with", "you", "your",
}
_TOKEN = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


class SemanticIndex:
    def __init__(self):
        self._keys: list[str] = []
        self._texts: list[str] = []
        self._vectorizer = None
        self._matrix = None
        self._vectors: list[dict[str, float]] = []
        self._idf: dict[str, float] = {}

    @property
    def backend(self) -> str:
        return "sklearn_tfidf" if _SKLEARN else "builtin_tfidf"

    def build(self, facts: dict) -> None:
        """facts: {key: text}. Call this whenever long-term memory changes."""
        self._keys = list(facts.keys())
        self._texts = [str(value) for value in facts.values()]
        if not self._texts:
            self._vectorizer, self._matrix, self._vectors, self._idf = None, None, [], {}
            return

        if _SKLEARN:
            self._vectorizer = TfidfVectorizer(stop_words="english")
            self._matrix = self._vectorizer.fit_transform(self._texts)
            return

        documents = [_tokens(text) for text in self._texts]
        appearances: Counter = Counter()
        for document in documents:
            appearances.update(set(document))
        total = len(documents)
        self._idf = {term: math.log((total + 1) / (count + 1)) + 1.0 for term, count in appearances.items()}
        self._vectors = [self._vector(document) for document in documents]

    def _vector(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        counts = Counter(tokens)
        longest = max(counts.values())
        weights = {term: (count / longest) * self._idf.get(term, 1.0) for term, count in counts.items()}
        norm = math.sqrt(sum(weight * weight for weight in weights.values())) or 1.0
        return {term: weight / norm for term, weight in weights.items()}

    def search(self, query: str, top_k: int = 3) -> list:
        if not self._texts:
            return []

        if _SKLEARN and self._vectorizer is not None:
            query_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(query_vec, self._matrix)[0]
        else:
            query_vector = self._vector(_tokens(query))
            scores = [
                sum(weight * document.get(term, 0.0) for term, weight in query_vector.items())
                for document in self._vectors
            ]

        ranked = sorted(zip(self._keys, self._texts, scores), key=lambda t: t[2], reverse=True)
        return [{"key": k, "text": t, "score": float(s)} for k, t, s in ranked[:top_k] if s > 0]
