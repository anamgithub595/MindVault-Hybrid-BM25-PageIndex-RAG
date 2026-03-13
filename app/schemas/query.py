"""app/schemas/query.py — Pydantic request/response models for /query"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    doc_ids: list[int] | None = Field(None, description="Scope to specific local document IDs")
    alpha: float | None = Field(
        None, ge=0.0, le=1.0, description="Override hybrid alpha (0=BM25, 1=PI)"
    )
    top_k: int = Field(default=5, ge=1, le=20)
    pi_thinking: bool = Field(default=False, description="Enable deeper PageIndex retrieval")


class CitedSourceResponse(BaseModel):
    document_title: str
    filename: str
    page_number: int
    section_heading: str | None
    pi_node_title: str
    rrf_score: float
    bm25_score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[CitedSourceResponse]
    bm25_terms_matched: list[str]
    retrieved_page_ids: list[int]
    pi_node_ids: list[str]
    latency_ms: int
