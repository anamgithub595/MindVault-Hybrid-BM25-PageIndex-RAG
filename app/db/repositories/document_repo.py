"""
app/db/repositories/document_repo.py
──────────────────────────────────────
Data access for `documents` and `pages` tables.
Zero business logic — pure DB I/O.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.models import Document, Page


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def create(self, filename: str, source_type: str, title: str | None = None) -> Document:
        doc = Document(filename=filename, source_type=source_type, title=title)
        self._s.add(doc)
        await self._s.flush()
        return doc

    async def get_by_id(self, doc_id: int) -> Document | None:
        r = await self._s.execute(
            select(Document).options(selectinload(Document.pages)).where(Document.id == doc_id)
        )
        return r.scalar_one_or_none()

    async def list_all(self) -> Sequence[Document]:
        r = await self._s.execute(select(Document).order_by(Document.created_at.desc()))
        return r.scalars().all()

    async def mark_bm25_indexed(self, doc_id: int, total_pages: int, total_tokens: int) -> None:
        await self._s.execute(
            update(Document).where(Document.id == doc_id).values(
                bm25_status="indexed",
                total_pages=total_pages,
                total_tokens=total_tokens,
                indexed_at=datetime.now(timezone.utc),
            )
        )

    async def set_pi_status(self, doc_id: int, status: str, pi_doc_id: str | None = None) -> None:
        vals: dict = {"pi_status": status}
        if pi_doc_id is not None:
            vals["pi_doc_id"] = pi_doc_id
        await self._s.execute(update(Document).where(Document.id == doc_id).values(**vals))

    async def mark_error(self, doc_id: int, message: str) -> None:
        await self._s.execute(
            update(Document).where(Document.id == doc_id).values(
                bm25_status="error", pi_status="failed", error_message=message
            )
        )

    async def delete(self, doc_id: int) -> None:
        doc = await self.get_by_id(doc_id)
        if doc:
            await self._s.delete(doc)


class PageRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def bulk_create(self, pages: list[Page]) -> None:
        self._s.add_all(pages)
        await self._s.flush()

    async def get_by_ids(self, ids: list[int]) -> Sequence[Page]:
        if not ids:
            return []
        r = await self._s.execute(select(Page).where(Page.id.in_(ids)))
        return r.scalars().all()

    async def get_by_document(self, doc_id: int) -> Sequence[Page]:
        r = await self._s.execute(
            select(Page).where(Page.document_id == doc_id).order_by(Page.page_number)
        )
        return r.scalars().all()
