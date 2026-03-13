"""
app/retrieval/bm25_retriever.py
────────────────────────────────
Converts a query string → BM25 ranked list of local page hits.
Touches the database but has zero knowledge of PageIndex.
"""
from __future__ import annotations
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Page
from app.db.repositories.index_repo import IndexRepository
from app.indexing.bm25 import BM25Scorer, BM25Hit
from app.indexing.tokeniser import Tokeniser
from app.core.exceptions import EmptyQueryError, NoResultsError

logger = logging.getLogger(__name__)


class BM25Retriever:
    def __init__(self, tokeniser: Tokeniser, scorer: BM25Scorer, top_k: int = 10):
        self._tok = tokeniser
        self._scorer = scorer
        self._top_k = top_k

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        doc_ids: list[int] | None = None,
    ) -> list[BM25Hit]:
        """
        Returns up to top_k BM25Hit objects sorted by descending score.
        Optionally scoped to a set of document IDs.
        """
        terms = self._tok.tokenise(query)
        if not terms:
            raise EmptyQueryError()

        repo = IndexRepository(session)
        N = await repo.get_total_page_count(doc_ids)
        if N == 0:
            return []

        avg_len = await repo.get_average_page_length(doc_ids)
        postings = await repo.get_postings(terms, doc_ids)
        doc_freqs = await repo.get_document_frequencies(terms, doc_ids)

        if not postings:
            return []

        candidate_ids = {
            pid for plist in postings.values() for pid, _, _ in plist
        }
        page_lengths = await self._fetch_lengths(session, list(candidate_ids))

        hits = self._scorer.rank(
            query_terms=terms,
            postings=postings,
            doc_freqs=doc_freqs,
            page_lengths=page_lengths,
            avg_page_length=avg_len,
            N=N,
            top_k=self._top_k,
        )
        logger.debug(f"[BM25] {len(hits)} hits for '{query[:60]}'")
        return hits

    @staticmethod
    async def _fetch_lengths(session: AsyncSession, ids: list[int]) -> dict[int, int]:
        if not ids:
            return {}
        r = await session.execute(select(Page.id, Page.token_count).where(Page.id.in_(ids)))
        return {row.id: row.token_count for row in r.all()}
