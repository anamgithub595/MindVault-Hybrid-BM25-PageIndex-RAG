"""
app/db/repositories/index_repo.py
───────────────────────────────────
Data access for the BM25 inverted index (`page_index` table).
Handles bulk inserts and term-lookup queries.
"""
from __future__ import annotations
from collections import defaultdict
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Page, PageIndexEntry


class IndexRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ── Write ─────────────────────────────────────────────────────────
    async def bulk_upsert(self, entries: list[dict]) -> None:
        """entries: [{"term", "page_id", "tf", "term_count"}]"""
        if not entries:
            return
        page_ids = {e["page_id"] for e in entries}
        await self._s.execute(delete(PageIndexEntry).where(PageIndexEntry.page_id.in_(page_ids)))
        self._s.add_all([PageIndexEntry(**e) for e in entries])

    async def delete_by_document(self, doc_id: int) -> None:
        subq = select(Page.id).where(Page.document_id == doc_id).scalar_subquery()
        await self._s.execute(delete(PageIndexEntry).where(PageIndexEntry.page_id.in_(subq)))

    # ── Read ──────────────────────────────────────────────────────────
    async def get_postings(
        self, terms: list[str], doc_ids: list[int] | None = None
    ) -> dict[str, list[tuple[int, float, int]]]:
        """
        Returns {term: [(page_id, tf, term_count), ...]}
        Optionally scoped to pages belonging to specific documents.
        """
        if not terms:
            return {}
        q = select(PageIndexEntry.term, PageIndexEntry.page_id,
                   PageIndexEntry.tf, PageIndexEntry.term_count
                   ).where(PageIndexEntry.term.in_(terms))
        if doc_ids:
            subq = select(Page.id).where(Page.document_id.in_(doc_ids)).scalar_subquery()
            q = q.where(PageIndexEntry.page_id.in_(subq))
        rows = (await self._s.execute(q)).all()
        result: dict[str, list] = defaultdict(list)
        for term, page_id, tf, tc in rows:
            result[term].append((page_id, tf, tc))
        return dict(result)

    async def get_document_frequencies(
        self, terms: list[str], doc_ids: list[int] | None = None
    ) -> dict[str, int]:
        q = (
            select(PageIndexEntry.term, func.count(PageIndexEntry.page_id).label("df"))
            .where(PageIndexEntry.term.in_(terms))
        )
        if doc_ids:
            subq = select(Page.id).where(Page.document_id.in_(doc_ids)).scalar_subquery()
            q = q.where(PageIndexEntry.page_id.in_(subq))
        q = q.group_by(PageIndexEntry.term)
        rows = (await self._s.execute(q)).all()
        return {r.term: r.df for r in rows}

    async def get_total_page_count(self, doc_ids: list[int] | None = None) -> int:
        q = select(func.count()).select_from(Page)
        if doc_ids:
            q = q.where(Page.document_id.in_(doc_ids))
        return (await self._s.execute(q)).scalar_one() or 0

    async def get_average_page_length(self, doc_ids: list[int] | None = None) -> float:
        q = select(func.avg(Page.token_count)).select_from(Page)
        if doc_ids:
            q = q.where(Page.document_id.in_(doc_ids))
        return float((await self._s.execute(q)).scalar_one() or 0)

    async def get_stats(self) -> dict:
        unique = (await self._s.execute(
            select(func.count(func.distinct(PageIndexEntry.term)))
        )).scalar_one()
        total = (await self._s.execute(
            select(func.count()).select_from(PageIndexEntry)
        )).scalar_one()
        return {"unique_terms": unique, "total_index_entries": total}
