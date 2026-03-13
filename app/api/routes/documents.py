"""
app/api/routes/documents.py
────────────────────────────
GET  /documents          — list all documents
GET  /documents/{id}     — detail
DELETE /documents/{id}   — delete document + index + PageIndex cloud entry
GET  /documents/index/stats

Also:
GET  /health
GET  /
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_pageindex_client
from app.db.models import Document
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.index_repo import IndexRepository
from app.pageindex.client import PageIndexAPIClient
from app.schemas.document import DocumentSummary, DocumentDetail, IndexStatsResponse

docs_router = APIRouter(prefix="/documents", tags=["Documents"])
health_router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


# ── Documents ──────────────────────────────────────────────────────────────

@docs_router.get("", response_model=list[DocumentSummary])
async def list_documents(db: AsyncSession = Depends(get_db)):
    docs = await DocumentRepository(db).list_all()
    return [DocumentSummary.model_validate(d) for d in docs]


@docs_router.get("/index/stats", response_model=IndexStatsResponse, tags=["Index"])
async def index_stats(db: AsyncSession = Depends(get_db)):
    doc_repo = DocumentRepository(db)
    idx_repo = IndexRepository(db)
    docs = await doc_repo.list_all()
    stats = await idx_repo.get_stats()
    total_pages = await idx_repo.get_total_page_count()
    avg_len = await idx_repo.get_average_page_length()
    pi_count = sum(1 for d in docs if d.pi_status == "completed")
    return IndexStatsResponse(
        total_documents=len(docs),
        total_pages=total_pages,
        unique_bm25_terms=stats["unique_terms"],
        total_index_entries=stats["total_index_entries"],
        avg_page_length_tokens=round(avg_len, 1),
        pi_indexed_documents=pi_count,
    )


@docs_router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await DocumentRepository(db).get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return DocumentDetail.model_validate(doc)


@docs_router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    pi_client: PageIndexAPIClient = Depends(get_pageindex_client),
):
    doc_repo = DocumentRepository(db)
    doc = await doc_repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    # Delete from PageIndex cloud if applicable
    if doc.pi_doc_id:
        try:
            await pi_client.delete_document(doc.pi_doc_id)
            logger.info(f"Deleted PageIndex doc {doc.pi_doc_id}")
        except Exception as e:
            logger.warning(f"PageIndex delete failed (non-fatal): {e}")

    # Delete local BM25 index + DB records (cascade)
    await IndexRepository(db).delete_by_document(doc_id)
    await doc_repo.delete(doc_id)


# ── Health ─────────────────────────────────────────────────────────────────

@health_router.get("/health")
async def health():
    return {"status": "ok", "service": "MindVault"}


@health_router.get("/")
async def root():
    return {
        "service": "MindVault",
        "description": "Hybrid BM25 + PageIndex Enterprise RAG",
        "docs": "/docs",
        "pipeline": "BM25 (local SQLite) + PageIndex (cloud tree) → RRF fusion → LLM",
    }
