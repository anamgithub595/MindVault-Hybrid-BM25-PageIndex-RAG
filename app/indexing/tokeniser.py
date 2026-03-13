"""
app/indexing/tokeniser.py
──────────────────────────
Stateless text → token list converter.
Used by both the index writer and the BM25 retriever.
No database, no BM25 math — pure text processing.
"""

from __future__ import annotations

import re
from collections import Counter

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "can",
        "could",
        "not",
        "no",
        "nor",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        "each",
        "than",
        "too",
        "very",
        "just",
        "as",
        "if",
        "then",
        "when",
        "where",
        "while",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "his",
        "her",
        "i",
        "my",
        "me",
    }
)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9]")


class Tokeniser:
    def __init__(
        self,
        lowercase: bool = True,
        remove_stopwords: bool = True,
        stemming: bool = False,
        min_len: int = 2,
    ):
        self.lowercase = lowercase
        self.remove_stopwords = remove_stopwords
        self.min_len = min_len
        self._stemmer = None
        if stemming:
            try:
                from nltk.stem import PorterStemmer

                self._stemmer = PorterStemmer()
            except ImportError:
                pass

    def tokenise(self, text: str) -> list[str]:
        if self.lowercase:
            text = text.lower()
        tokens = _TOKEN_RE.findall(text)
        if self.min_len > 1:
            tokens = [t for t in tokens if len(t) >= self.min_len]
        if self.remove_stopwords:
            tokens = [t for t in tokens if t not in _STOPWORDS]
        if self._stemmer:
            tokens = [self._stemmer.stem(t) for t in tokens]
        return tokens

    def term_frequencies(self, text: str) -> tuple[dict[str, float], dict[str, int]]:
        """Returns ({term: tf}, {term: raw_count})"""
        tokens = self.tokenise(text)
        if not tokens:
            return {}, {}
        counts = Counter(tokens)
        total = len(tokens)
        return {t: c / total for t, c in counts.items()}, dict(counts)

    def count_tokens(self, text: str) -> int:
        return len(text.split())
