"""app/schemas/document.py — Pydantic models for /ingest and /documents"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class IngestResponse(BaseModel):
    document_id: int
    filename: str
    total_pages: int
    total_tokens: int
    bm25_status: str
    pi_status: str
    pi_doc_id: str | None = None
    message: str = ""


class NotionIngestRequest(BaseModel):
    page_id_or_url: str


class DocumentSummary(BaseModel):
    id: int
    filename: str
    title: str | None
    source_type: str
    total_pages: int
    total_tokens: int
    bm25_status: str
    pi_status: str
    pi_doc_id: str | None
    created_at: datetime
    indexed_at: datetime | None

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentSummary):
    error_message: str | None


class IndexStatsResponse(BaseModel):
    total_documents: int
    total_pages: int
    unique_bm25_terms: int
    total_index_entries: int
    avg_page_length_tokens: float
    pi_indexed_documents: int
