"""tests/unit/test_hybrid_fusion.py — RRF fusion logic tests"""


def rrf_score(bm25_rank, pi_rank, alpha=0.5, k=60):
    bm25 = 1 / (k + bm25_rank) if bm25_rank else 0
    pi = 1 / (k + pi_rank) if pi_rank else 0
    return (1 - alpha) * bm25 + alpha * pi


def test_both_sources_score_higher_than_single():
    score_both = rrf_score(1, 1)
    score_bm25_only = rrf_score(1, None)
    score_pi_only = rrf_score(None, 1)
    assert score_both > score_bm25_only
    assert score_both > score_pi_only


def test_alpha_zero_ignores_pi():
    score = rrf_score(1, 1, alpha=0.0)
    score_no_pi = rrf_score(1, None, alpha=0.0)
    assert abs(score - score_no_pi) < 1e-9


def test_alpha_one_ignores_bm25():
    score = rrf_score(1, 1, alpha=1.0)
    score_no_bm25 = rrf_score(None, 1, alpha=1.0)
    assert abs(score - score_no_bm25) < 1e-9


def test_rank_1_beats_rank_10():
    assert rrf_score(1, None) > rrf_score(10, None)
