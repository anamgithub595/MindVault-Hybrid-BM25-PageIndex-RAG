"""
app/ingestion/pipeline.py
──────────────────────────
Top-level ingestion orchestrator.

For each uploaded document it does TWO things in parallel:
  1. BM25 path:      connector → raw pages → BM25 IndexWriter → SQLite
  2. PageIndex path: upload PDF bytes → PageIndex API → poll until ready

Both paths use the same document_id in our local DB.
Route handlers call this — they never touch connectors or writers directly.
"""
from __future__ import annotations
import asyncio
import logging
import tempfile
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import BaseConnector
from app.connectors.pdf_connector import PDFConnector
from app.connectors.markdown_connector import MarkdownConnector
from app.connectors.notion_connector import NotionConnector
from app.core.config import get_settings
from app.core.exceptions import UnsupportedFileTypeError, FileTooLargeError, ParseError
from app.db.repositories.document_repo import DocumentRepository
from app.indexing.index_writer import IndexWriter
from app.indexing.tokeniser import Tokeniser
from app.pageindex.client import PageIndexAPIClient

logger = logging.getLogger(__name__)

_CONNECTOR_MAP: dict[str, type[BaseConnector]] = {
    ".pdf": PDFConnector,
    ".md": MarkdownConnector,
    ".markdown": MarkdownConnector,
    ".txt": MarkdownConnector,
}


class IngestionPipeline:
    def __init__(
        self,
        session: AsyncSession,
        tokeniser: Tokeniser,
        pi_client: PageIndexAPIClient,
    ):
        self._session = session
        self._tok = tokeniser
        self._pi = pi_client
        self._settings = get_settings()

    async def ingest_file(self, filename: str, content: bytes) -> int:
        """
        Full pipeline for an uploaded file.
        Returns local document_id.
        """
        self._validate_size(content)
        ext = Path(filename).suffix.lower()
        connector_cls = _CONNECTOR_MAP.get(ext)
        if connector_cls is None:
            raise UnsupportedFileTypeError(ext)

        connector = connector_cls()

        # ── Step 1: Extract text ─────────────────────────────────────
        raw_doc = await connector.extract(source=content, filename=filename)

        # ── Step 2: BM25 index (SQLite) ───────────────────────────────
        writer = IndexWriter(session=self._session, tokeniser=self._tok)
        doc_id = await writer.write(raw_doc)
        logger.info(f"[Pipeline] BM25 indexed doc_id={doc_id}")

        # ── Step 3: PageIndex (PDF only, fire-and-forget background) ──
        if ext == ".pdf":
            asyncio.create_task(
                self._submit_to_pageindex(doc_id=doc_id, pdf_bytes=content, filename=filename)
            )
        else:
            # For non-PDF: mark as skipped so the retriever knows
            doc_repo = DocumentRepository(self._session)
            await doc_repo.set_pi_status(doc_id, "skipped")

        return doc_id

    async def ingest_notion_page(self, page_id_or_url: str) -> int:
        connector = NotionConnector()
        raw_doc = await connector.extract(source=page_id_or_url, filename="notion")
        writer = IndexWriter(session=self._session, tokeniser=self._tok)
        doc_id = await writer.write(raw_doc)
        # Notion export is text only — mark PageIndex as skipped
        doc_repo = DocumentRepository(self._session)
        await doc_repo.set_pi_status(doc_id, "skipped")
        return doc_id

    # ── Private ───────────────────────────────────────────────────────

    async def _submit_to_pageindex(self, doc_id: int, pdf_bytes: bytes, filename: str) -> None:
        """
        Background task: submit PDF to PageIndex and poll until ready.
        Updates pi_status in local DB.
        This runs outside the original request's DB session,
        so it uses a new session from the engine.
        """
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_session:
            doc_repo = DocumentRepository(bg_session)
            try:
                await doc_repo.set_pi_status(doc_id, "processing")
                await bg_session.commit()

                pi_doc_id = await self._pi.submit_document(pdf_bytes, filename)
                await doc_repo.set_pi_status(doc_id, "processing", pi_doc_id=pi_doc_id)
                await bg_session.commit()

                await self._pi.poll_until_ready(pi_doc_id)

                await doc_repo.set_pi_status(doc_id, "completed", pi_doc_id=pi_doc_id)
                await bg_session.commit()
                logger.info(f"[Pipeline] PageIndex ready: doc_id={doc_id} pi_doc_id={pi_doc_id}")

            except Exception as exc:
                logger.error(f"[Pipeline] PageIndex failed for doc_id={doc_id}: {exc}")
                await doc_repo.set_pi_status(doc_id, "failed")
                await bg_session.commit()

    def _validate_size(self, content: bytes) -> None:
        if len(content) > self._settings.max_upload_bytes:
            raise FileTooLargeError(len(content), self._settings.max_upload_bytes)
