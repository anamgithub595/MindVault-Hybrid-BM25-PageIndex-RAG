"""
app/indexing/index_writer.py
─────────────────────────────
Orchestrates: RawDocument → tokenise each page → write BM25 index to SQLite.
This is the only indexing module that touches the database.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import RawDocument
from app.db.models import Page
from app.db.repositories.document_repo import DocumentRepository, PageRepository
from app.db.repositories.index_repo import IndexRepository
from app.indexing.tokeniser import Tokeniser

logger = logging.getLogger(__name__)


class IndexWriter:
    def __init__(self, session: AsyncSession, tokeniser: Tokeniser):
        self._session = session
        self._tok = tokeniser
        self._doc_repo = DocumentRepository(session)
        self._page_repo = PageRepository(session)
        self._idx_repo = IndexRepository(session)

    async def write(self, raw_doc: RawDocument) -> int:
        """
        Persist document + pages + BM25 index entries.
        Returns the local document_id.
        """
        doc = await self._doc_repo.create(
            filename=raw_doc.filename,
            source_type=raw_doc.source_type,
            title=raw_doc.title,
        )
        doc_id = doc.id
        logger.info(f"[IndexWriter] doc_id={doc_id} filename={raw_doc.filename}")

        try:
            page_orms: list[Page] = []
            total_tokens = 0

            for rp in raw_doc.pages:
                tc = self._tok.count_tokens(rp.content)
                total_tokens += tc
                page_orms.append(Page(
                    document_id=doc_id,
                    page_number=rp.page_number,
                    section_heading=rp.section_heading,
                    content=rp.content,
                    token_count=tc,
                    char_count=len(rp.content),
                ))

            await self._page_repo.bulk_create(page_orms)

            index_entries: list[dict] = []
            for page_orm, rp in zip(page_orms, raw_doc.pages, strict=False):
                tf_dict, count_dict = self._tok.term_frequencies(rp.content)
                for term, tf in tf_dict.items():
                    index_entries.append({
                        "term": term,
                        "page_id": page_orm.id,
                        "tf": tf,
                        "term_count": count_dict.get(term, 1),
                    })

            await self._idx_repo.bulk_upsert(index_entries)
            await self._doc_repo.mark_bm25_indexed(doc_id, len(page_orms), total_tokens)

            logger.info(
                f"[IndexWriter] Indexed doc={doc_id}: "
                f"{len(page_orms)} pages, {len(index_entries)} terms"
            )
            return doc_id

        except Exception as exc:
            await self._doc_repo.mark_error(doc_id, str(exc))
            raise
