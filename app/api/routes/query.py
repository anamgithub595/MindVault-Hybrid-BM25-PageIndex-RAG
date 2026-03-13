"""
app/api/routes/query.py
────────────────────────
POST /query

Full hybrid pipeline:
  1. Run BM25 + PageIndex retrieval in parallel
  2. Fuse via RRF
  3. Fetch full page text for top-K hits
  4. Build prompt → LLM → format citations
  5. Log to audit trail
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_citation_formatter,
    get_db,
    get_hybrid_retriever,
    get_llm_client,
    get_prompt_builder,
)
from app.core.exceptions import EmptyQueryError, LLMProviderError
from app.db.models import Document
from app.db.repositories.document_repo import DocumentRepository, PageRepository
from app.db.repositories.query_log_repo import QueryLogRepository
from app.generation.citation_formatter import CitationFormatter
from app.generation.llm_client import LLMClient
from app.generation.prompt_builder import PageContext, PromptBuilder
from app.retrieval.hybrid_retriever import HybridHit, HybridRetriever
from app.schemas.query import CitedSourceResponse, QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["Query"])
logger = logging.getLogger(__name__)


@router.post("", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
    hybrid: HybridRetriever = Depends(get_hybrid_retriever),
    llm: LLMClient = Depends(get_llm_client),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
    citation_formatter: CitationFormatter = Depends(get_citation_formatter),
):
    start = time.monotonic()

    # ── 1. Resolve document scoping ───────────────────────────────────
    doc_ids: list[int] | None = req.doc_ids
    pi_doc_ids: list[str] | None = None

    if doc_ids:
        # Get pi_doc_ids for scoped documents (for PageIndex retrieval)
        r = await db.execute(
            select(Document.pi_doc_id).where(
                Document.id.in_(doc_ids), Document.pi_status == "completed"
            )
        )
        pi_doc_ids = [row[0] for row in r.all() if row[0]]
    else:
        # All completed PageIndex documents
        r = await db.execute(select(Document.pi_doc_id).where(Document.pi_status == "completed"))
        pi_doc_ids = [row[0] for row in r.all() if row[0]]

    # ── 2. Override alpha if provided ─────────────────────────────────
    if req.alpha is not None:
        hybrid.alpha = req.alpha

    # ── 3. Hybrid retrieval ───────────────────────────────────────────
    try:
        hits: list[HybridHit] = await hybrid.retrieve(
            query=req.query,
            session=db,
            doc_ids=doc_ids,
            pi_doc_ids=pi_doc_ids or None,
        )
    except EmptyQueryError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is empty.")

    if not hits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No documents matched your query. Ingest some documents first.",
        )

    # ── 4. Fetch full page + document data ────────────────────────────
    page_ids = [h.page_id for h in hits]
    page_repo = PageRepository(db)
    doc_repo = DocumentRepository(db)

    pages = await page_repo.get_by_ids(page_ids)
    pages_by_id = {p.id: p for p in pages}

    unique_doc_ids = list({p.document_id for p in pages})
    docs_by_id: dict[int, Document] = {}
    for did in unique_doc_ids:
        d = await doc_repo.get_by_id(did)
        if d:
            docs_by_id[did] = d

    # Build PageContext list in hit-rank order
    page_contexts: list[PageContext] = []
    bm25_hits_by_page: dict[int, list[str]] = {}
    pi_node_ids: list[str] = []

    for hit in hits:
        page = pages_by_id.get(hit.page_id)
        if not page:
            continue
        doc = docs_by_id.get(page.document_id)
        page_contexts.append(
            PageContext(
                page_id=page.id,
                page_number=page.page_number,
                document_title=doc.title or doc.filename if doc else "Unknown",
                filename=doc.filename if doc else "unknown",
                section_heading=page.section_heading,
                content=page.content,
                rrf_score=hit.rrf_score,
                bm25_score=hit.bm25_score,
                pi_node_title=hit.pi_node_title,
                pi_relevant_content=hit.pi_relevant_content,
            )
        )
        bm25_hits_by_page[hit.page_id] = hit.matched_bm25_terms
        if hit.pi_node_id:
            pi_node_ids.append(hit.pi_node_id)

    # ── 5. LLM generation ─────────────────────────────────────────────
    system_prompt, user_msg = prompt_builder.build(req.query, page_contexts)
    try:
        llm_resp = await llm.complete(system_prompt, user_msg)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # ── 6. Format citations ───────────────────────────────────────────
    result = citation_formatter.format(
        raw_answer=llm_resp.content,
        pages=page_contexts,
        bm25_hits_by_page=bm25_hits_by_page,
        pi_node_ids=list(set(pi_node_ids)),
    )

    latency_ms = int((time.monotonic() - start) * 1000)

    # ── 7. Audit log ──────────────────────────────────────────────────
    try:
        log_repo = QueryLogRepository(db)
        await log_repo.log(
            query_text=req.query,
            scoped_doc_ids=doc_ids,
            bm25_page_ids=[h.page_id for h in hits if h.bm25_score > 0],
            pi_node_ids=result.pi_node_ids,
            final_page_ids=result.retrieved_page_ids,
            answer=result.answer,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        logger.warning(f"Audit log failed (non-fatal): {exc}")

    return QueryResponse(
        query=req.query,
        answer=result.answer,
        sources=[CitedSourceResponse(**s.__dict__) for s in result.sources],
        bm25_terms_matched=result.bm25_terms_matched,
        retrieved_page_ids=result.retrieved_page_ids,
        pi_node_ids=result.pi_node_ids,
        latency_ms=latency_ms,
    )
