"""tests/unit/test_bm25.py — BM25 pure-math tests (no DB needed)"""

from app.indexing.bm25 import BM25Scorer
from app.indexing.tokeniser import Tokeniser


class TestTokeniser:
    def setup_method(self):
        self.tok = Tokeniser()

    def test_stopwords_removed(self):
        tokens = self.tok.tokenise("the cat sat on the mat")
        assert "the" not in tokens
        assert "cat" in tokens

    def test_lowercase(self):
        assert "hello" in self.tok.tokenise("HELLO World")

    def test_tf_sums_close_to_one(self):
        tf, _ = self.tok.term_frequencies("cat cat dog bird")
        assert abs(sum(tf.values()) - 1.0) < 0.01

    def test_count_tokens(self):
        assert self.tok.count_tokens("one two three") == 3


class TestBM25:
    def setup_method(self):
        self.scorer = BM25Scorer(k1=1.5, b=0.75)

    def test_idf_positive(self):
        assert self.scorer.idf(1, 100) > 0

    def test_idf_decreases_with_frequency(self):
        assert self.scorer.idf(1, 100) > self.scorer.idf(50, 100)

    def test_rank_returns_top_k(self):
        postings = {"rag": [(1, 0.3, 3), (2, 0.1, 1)], "search": [(1, 0.2, 2)]}
        doc_freqs = {"rag": 2, "search": 1}
        hits = self.scorer.rank(
            query_terms=["rag", "search"],
            postings=postings,
            doc_freqs=doc_freqs,
            page_lengths={1: 30, 2: 20},
            avg_page_length=25.0,
            N=5,
            top_k=2,
        )
        assert len(hits) <= 2
        if len(hits) == 2:
            assert hits[0].score >= hits[1].score

    def test_multi_term_page_scores_higher(self):
        postings = {"cat": [(1, 0.5, 5), (2, 0.2, 2)], "dog": [(1, 0.3, 3)]}
        doc_freqs = {"cat": 2, "dog": 1}
        hits = self.scorer.rank(
            query_terms=["cat", "dog"],
            postings=postings,
            doc_freqs=doc_freqs,
            page_lengths={1: 30, 2: 20},
            avg_page_length=25.0,
            N=3,
        )
        p1 = next(h for h in hits if h.page_id == 1)
        p2 = next(h for h in hits if h.page_id == 2)
        assert p1.score > p2.score
