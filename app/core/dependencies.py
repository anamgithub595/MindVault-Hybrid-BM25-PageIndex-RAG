"""
app/core/dependencies.py
─────────────────────────
FastAPI Depends() providers.
Route handlers receive fully-constructed service objects — zero construction logic in routes.
"""
from __future__ import annotations
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, Settings
from app.db.database import AsyncSessionLocal
from app.indexing.tokeniser import Tokeniser
from app.indexing.bm25 import BM25Scorer
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.pageindex_retriever import PageIndexRetriever
from app.retrieval.hybrid_retriever import HybridRetriever
from app.generation.llm_client import LLMClient
from app.generation.prompt_builder import PromptBuilder
from app.generation.citation_formatter import CitationFormatter
from app.pageindex.client import PageIndexAPIClient


# ── DB session ────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Shared service factories ──────────────────────────────────────────────
def get_tokeniser() -> Tokeniser:
    return Tokeniser(lowercase=True, remove_stopwords=True, stemming=False)


def get_bm25_scorer() -> BM25Scorer:
    s = get_settings()
    return BM25Scorer(k1=s.bm25_k1, b=s.bm25_b)


def get_pageindex_client() -> PageIndexAPIClient:
    s = get_settings()
    return PageIndexAPIClient(
        api_key=s.pageindex_api_key,
        poll_interval=s.pi_poll_interval_sec,
        poll_timeout=s.pi_poll_timeout_sec,
    )


def get_bm25_retriever() -> BM25Retriever:
    s = get_settings()
    return BM25Retriever(
        tokeniser=get_tokeniser(),
        scorer=get_bm25_scorer(),
        top_k=s.bm25_top_k,
    )


def get_pi_retriever() -> PageIndexRetriever:
    s = get_settings()
    return PageIndexRetriever(
        client=get_pageindex_client(),
        top_k=s.pi_top_k,
    )


def get_hybrid_retriever() -> HybridRetriever:
    s = get_settings()
    return HybridRetriever(
        bm25_retriever=get_bm25_retriever(),
        pi_retriever=get_pi_retriever(),
        alpha=s.hybrid_alpha,
        final_top_k=s.final_top_k,
    )


def get_llm_client() -> LLMClient:
    s = get_settings()
    return LLMClient(
        provider=s.llm_provider,
        model=s.llm_model,
        api_key=s.active_llm_key,
        max_tokens=s.llm_max_tokens,
        temperature=s.llm_temperature,
    )


def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()


def get_citation_formatter() -> CitationFormatter:
    return CitationFormatter()
