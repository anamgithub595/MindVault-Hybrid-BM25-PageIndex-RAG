"""
app/api/routes/ingest.py
─────────────────────────
POST /ingest/upload  — file upload (PDF, MD, TXT)
POST /ingest/notion  — Notion page by URL or ID
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_pageindex_client, get_tokeniser
from app.core.exceptions import FileTooLargeError, ParseError, UnsupportedFileTypeError
from app.db.repositories.document_repo import DocumentRepository
from app.indexing.tokeniser import Tokeniser
from app.ingestion.pipeline import IngestionPipeline
from app.pageindex.client import PageIndexAPIClient
from app.schemas.document import IngestResponse, NotionIngestRequest

router = APIRouter(prefix="/ingest", tags=["Ingestion"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    tokeniser: Tokeniser = Depends(get_tokeniser),
    pi_client: PageIndexAPIClient = Depends(get_pageindex_client),
):
    """
    Upload a document (PDF, Markdown, TXT).

    - PDF:  BM25 indexed immediately + submitted to PageIndex in the background.
    - MD/TXT: BM25 indexed immediately (PageIndex is PDF-only).
    """
    content = await file.read()
    pipeline = IngestionPipeline(session=db, tokeniser=tokeniser, pi_client=pi_client)

    try:
        doc_id = await pipeline.ingest_file(
            filename=file.filename or "upload",
            content=content,
        )
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e)) from e
    except FileTooLargeError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e)) from e
    except ParseError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Unexpected ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Ingestion failed unexpectedly.") from e

    doc_repo = DocumentRepository(db)
    doc = await doc_repo.get_by_id(doc_id)

    return IngestResponse(
        document_id=doc_id,
        filename=doc.filename,
        total_pages=doc.total_pages,
        total_tokens=doc.total_tokens,
        bm25_status=doc.bm25_status,
        pi_status=doc.pi_status,
        pi_doc_id=doc.pi_doc_id,
        message=(
            "BM25 indexed. PageIndex processing in background (PDF only)."
            if doc.pi_status == "processing"
            else "BM25 indexed. PageIndex skipped (non-PDF)."
        ),
    )


@router.post("/notion", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_notion(
    req: NotionIngestRequest,
    db: AsyncSession = Depends(get_db),
    tokeniser: Tokeniser = Depends(get_tokeniser),
    pi_client: PageIndexAPIClient = Depends(get_pageindex_client),
):
    """Ingest a Notion page by its URL or page ID (BM25 only — no PDF)."""
    pipeline = IngestionPipeline(session=db, tokeniser=tokeniser, pi_client=pi_client)
    try:
        doc_id = await pipeline.ingest_notion_page(req.page_id_or_url)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Notion ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Notion ingestion failed.") from e

    doc_repo = DocumentRepository(db)
    doc = await doc_repo.get_by_id(doc_id)
    return IngestResponse(
        document_id=doc_id,
        filename=doc.filename,
        total_pages=doc.total_pages,
        total_tokens=doc.total_tokens,
        bm25_status=doc.bm25_status,
        pi_status=doc.pi_status,
        message="Notion page BM25 indexed. PageIndex skipped (non-PDF).",
    )

