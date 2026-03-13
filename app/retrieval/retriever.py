"""
app/retrieval/retriever.py
───────────────────────────
Orchestrates the full retrieval process:
  query string
    → tokenise
    → look up postings + corpus stats from DB
    → score via BM25
    → return ranked ScoredPage list

This is the only retrieval module that touches the database.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EmptyQueryError, NoResultsError
from app.db.models import Page
from app.db.repositories.index_repo import IndexRepository
from app.indexing.bm25 import BM25Scorer, ScoredPage
from app.indexing.tokeniser import Tokeniser

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(
        self,
        tokeniser: Tokeniser,
        scorer: BM25Scorer,
        top_k: int = 5,
    ) -> None:
        self._tokeniser = tokeniser
        self._scorer = scorer
        self._top_k = top_k

    async def retrieve(self, query: str, session: AsyncSession) -> list[ScoredPage]:
        """
        Main entry point.
        Returns up to top_k ScoredPage objects, descending by BM25 score.
        """
        # 1. Tokenise query
        query_terms = self._tokeniser.tokenise(query)
        if not query_terms:
            raise EmptyQueryError()

        logger.debug(f"[Retriever] Query terms: {query_terms}")

        index_repo = IndexRepository(session)

        # 2. Fetch corpus statistics
        N = await index_repo.get_total_page_count()
        if N == 0:
            raise NoResultsError()

        avg_len = await index_repo.get_average_page_length()

        # 3. Fetch postings and doc frequencies for query terms
        postings = await index_repo.get_postings(query_terms)
        doc_freqs = await index_repo.get_document_frequencies(query_terms)

        if not postings:
            raise NoResultsError()

        # 4. Build page_lengths map for candidate pages
        candidate_page_ids = {
            page_id for posting_list in postings.values() for page_id, _, _ in posting_list
        }
        page_lengths = await self._fetch_page_lengths(session, list(candidate_page_ids))

        # 5. Score and rank
        scored = self._scorer.rank(
            query_terms=query_terms,
            postings=postings,
            doc_freqs=doc_freqs,
            page_lengths=page_lengths,
            avg_page_length=avg_len,
            N=N,
            top_k=self._top_k,
        )

        logger.debug(f"[Retriever] Top scores: {[(s.page_id, round(s.score, 3)) for s in scored]}")
        return scored

    @staticmethod
    async def _fetch_page_lengths(session: AsyncSession, page_ids: list[int]) -> dict[int, int]:
        if not page_ids:
            return {}
        result = await session.execute(
            select(Page.id, Page.token_count).where(Page.id.in_(page_ids))
        )
        return {row.id: row.token_count for row in result.all()}
