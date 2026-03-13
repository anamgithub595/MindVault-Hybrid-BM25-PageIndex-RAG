"""
app/indexing/bm25.py
─────────────────────
Pure BM25 scoring — stateless, no I/O, no DB.

Formula:
  score(q,d) = Σ IDF(qi) · [tf·(k1+1)] / [tf + k1·(1−b + b·|d|/avgdl)]
  IDF(qi)    = log( (N − df + 0.5) / (df + 0.5) + 1 )
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class BM25Hit:
    page_id: int
    score: float
    matched_terms: list[str] = field(default_factory=list)


class BM25Scorer:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def idf(self, df: int, N: int) -> float:
        return math.log((N - df + 0.5) / (df + 0.5) + 1)

    def rank(
        self,
        query_terms: list[str],
        postings: dict[str, list[tuple[int, float, int]]],  # term → [(page_id, tf, tc)]
        doc_freqs: dict[str, int],
        page_lengths: dict[int, int],
        avg_page_length: float,
        N: int,
        top_k: int = 10,
    ) -> list[BM25Hit]:
        if N == 0 or avg_page_length == 0:
            return []

        page_scores: dict[int, float] = {}
        page_terms: dict[int, list[str]] = {}

        for term in query_terms:
            if term not in postings:
                continue
            df = doc_freqs.get(term, 0)
            if df == 0:
                continue
            idf = self.idf(df, N)
            for page_id, tf, _ in postings[term]:
                dl = page_lengths.get(page_id, avg_page_length)
                num = tf * (self.k1 + 1)
                den = tf + self.k1 * (1 - self.b + self.b * dl / avg_page_length)
                page_scores[page_id] = page_scores.get(page_id, 0.0) + idf * num / den
                page_terms.setdefault(page_id, []).append(term)

        hits = [
            BM25Hit(page_id=pid, score=sc, matched_terms=list(set(page_terms[pid])))
            for pid, sc in page_scores.items()
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]
