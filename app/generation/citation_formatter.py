"""
app/generation/citation_formatter.py
──────────────────────────────────────
Wraps the raw LLM answer with structured source metadata.
Zero LLM calls — pure post-processing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from app.generation.prompt_builder import PageContext


@dataclass
class CitedSource:
    document_title: str
    filename: str
    page_number: int
    section_heading: str | None
    pi_node_title: str
    rrf_score: float
    bm25_score: float
    pi_score: float = 0.0


@dataclass
class AnswerResult:
    answer: str
    sources: list[CitedSource] = field(default_factory=list)
    bm25_terms_matched: list[str] = field(default_factory=list)
    retrieved_page_ids: list[int] = field(default_factory=list)
    pi_node_ids: list[str] = field(default_factory=list)


class CitationFormatter:
    def format(
        self,
        raw_answer: str,
        pages: list[PageContext],
        bm25_hits_by_page: dict[int, list[str]],   # page_id → matched terms
        pi_node_ids: list[str],
    ) -> AnswerResult:
        sources = [
            CitedSource(
                document_title=p.document_title,
                filename=p.filename,
                page_number=p.page_number,
                section_heading=p.section_heading,
                pi_node_title=p.pi_node_title,
                rrf_score=round(p.rrf_score, 5),
                bm25_score=round(p.bm25_score, 4),
            )
            for p in pages
        ]
        all_terms = sorted({
            t for terms in bm25_hits_by_page.values() for t in terms
        })
        return AnswerResult(
            answer=raw_answer.strip(),
            sources=sources,
            bm25_terms_matched=all_terms,
            retrieved_page_ids=[p.page_id for p in pages],
            pi_node_ids=pi_node_ids,
        )
