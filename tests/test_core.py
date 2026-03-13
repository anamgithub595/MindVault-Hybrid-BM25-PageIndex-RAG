"""
tests/unit/test_tokeniser.py  +  tests/unit/test_bm25.py (combined)
Run with: pytest tests/unit/ -v
"""
import pytest
from app.indexing.tokeniser import Tokeniser
from app.indexing.bm25 import BM25Scorer, ScoredPage


# ── Tokeniser Tests ───────────────────────────────────────────────────────

class TestTokeniser:
    def setup_method(self):
        self.tok = Tokeniser(lowercase=True, remove_stopwords=True, stemming=False)

    def test_basic_tokenisation(self):
        tokens = self.tok.tokenise("Hello World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_stopword_removal(self):
        tokens = self.tok.tokenise("the cat sat on the mat")
        assert "the" not in tokens
        assert "on" not in tokens
        assert "cat" in tokens
        assert "mat" in tokens

    def test_short_token_filter(self):
        tokens = self.tok.tokenise("I am a developer")
        assert "am" not in tokens   # length < 2 ... wait, "am" is 2 chars
        # min_token_length=2, "a" is 1 char → removed
        assert "a" not in tokens

    def test_hyphenated_tokens(self):
        tokens = self.tok.tokenise("state-of-the-art approach")
        # regex keeps hyphenated runs as single tokens
        assert any("state" in t or "state-of-the-art" in t for t in tokens)

    def test_term_frequencies_sum_to_one(self):
        tf_dict, _ = self.tok.term_frequencies("cat cat dog")
        total = sum(tf_dict.values())
        assert abs(total - 1.0) < 0.001

    def test_count_tokens(self):
        n = self.tok.count_tokens("one two three four five")
        assert n == 5


# ── BM25 Tests ────────────────────────────────────────────────────────────

class TestBM25Scorer:
    def setup_method(self):
        self.scorer = BM25Scorer(k1=1.5, b=0.75)

    def test_idf_positive(self):
        # IDF should always be positive with this formula
        assert self.scorer.idf(df=1, N=10) > 0
        assert self.scorer.idf(df=9, N=10) > 0

    def test_idf_decreases_with_df(self):
        idf_rare = self.scorer.idf(df=1, N=100)
        idf_common = self.scorer.idf(df=80, N=100)
        assert idf_rare > idf_common

    def test_rank_returns_top_k(self):
        postings = {
            "retrieval": [(1, 0.3, 5), (2, 0.1, 3), (3, 0.5, 8)],
            "rag": [(1, 0.2, 3), (3, 0.4, 6)],
        }
        doc_freqs = {"retrieval": 3, "rag": 2}
        page_lengths = {1: 30, 2: 20, 3: 40}

        results = self.scorer.rank(
            query_terms=["retrieval", "rag"],
            postings=postings,
            doc_freqs=doc_freqs,
            page_lengths=page_lengths,
            avg_page_length=30.0,
            N=5,
            top_k=2,
        )
        assert len(results) <= 2
        assert all(isinstance(r, ScoredPage) for r in results)
        # Scores should be descending
        if len(results) == 2:
            assert results[0].score >= results[1].score

    def test_page_matching_two_terms_scores_higher(self):
        postings = {
            "cat": [(1, 0.5, 5), (2, 0.2, 2)],
            "dog": [(1, 0.3, 3)],          # page 1 matches both
        }
        doc_freqs = {"cat": 2, "dog": 1}
        page_lengths = {1: 30, 2: 20}

        results = self.scorer.rank(
            query_terms=["cat", "dog"],
            postings=postings,
            doc_freqs=doc_freqs,
            page_lengths=page_lengths,
            avg_page_length=25.0,
            N=3,
            top_k=5,
        )
        page1_score = next(r.score for r in results if r.page_id == 1)
        page2_score = next(r.score for r in results if r.page_id == 2)
        assert page1_score > page2_score
