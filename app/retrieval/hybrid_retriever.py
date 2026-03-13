"""
app/retrieval/hybrid_retriever.py
───────────────────────────────────
Fuses BM25 hits and PageIndex nodes using Reciprocal Rank Fusion (RRF).

Architecture:
  BM25Retriever  ──┐
                   ├──▶ HybridRetriever ──▶ list[HybridHit]
  PIRetriever    ──┘

RRF formula:
  RRF_score(d) = Σ  1 / (k + rank_i(d))
  where k=60 (default), rank_i(d) is 1-based rank of doc d in list i.

After RRF we apply alpha weighting:
  final_score = (1 - alpha) * bm25_norm + alpha * pi_norm

alpha=0.0 → pure BM25
alpha=1.0 → pure PageIndex
alpha=0.5 → equal weight (default)
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.pageindex_retriever import PageIndexRetriever
from app.indexing.bm25 import BM25Hit
from app.pageindex.client import PINode

logger = logging.getLogger(__name__)

_RRF_K = 60  # standard RRF constant


@dataclass
class HybridHit:
    """A single result from hybrid fusion, ready for LLM context."""
    page_id: int                         # local SQLite page id
    rrf_score: float
    bm25_score: float = 0.0
    pi_score: float = 0.0
    matched_bm25_terms: list[str] = field(default_factory=list)
    # PageIndex node info (may be empty if only BM25 matched)
    pi_node_title: str = ""
    pi_node_id: str = ""
    pi_page_index: int = 0               # 1-based PDF page from PageIndex
    pi_relevant_content: str = ""        # snippet from PageIndex node


class HybridRetriever:
    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        pi_retriever: PageIndexRetriever,
        alpha: float = 0.5,
        final_top_k: int = 5,
    ):
        self._bm25 = bm25_retriever
        self._pi = pi_retriever
        self.alpha = alpha
        self.final_top_k = final_top_k

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        doc_ids: list[int] | None = None,
        pi_doc_ids: list[str] | None = None,
    ) -> list[HybridHit]:
        """
        Run BM25 and PageIndex retrieval in parallel, fuse with RRF.

        Args:
            query:       Natural language question.
            session:     Async DB session (for BM25).
            doc_ids:     Optional local document ID filter for BM25.
            pi_doc_ids:  Optional PageIndex doc IDs to query. If None,
                         PageIndex is skipped (BM25 only).
        Returns:
            List of HybridHit sorted by descending RRF score.
        """
        # ── Run both retrievers concurrently ──────────────────────────
        bm25_task = self._bm25.retrieve(query, session, doc_ids)
        async def _empty():
            return []
        pi_task = (
            self._pi.retrieve(query, pi_doc_ids)
            if pi_doc_ids
            else _empty()
                
        )

        bm25_hits: list[BM25Hit]
        pi_nodes: list[PINode]
        bm25_hits, pi_nodes = await asyncio.gather(bm25_task, pi_task)

        logger.info(f"[Hybrid] BM25={len(bm25_hits)} PI={len(pi_nodes)} hits")

        # ── Build page_id → hit map from BM25 ─────────────────────────
        bm25_by_page: dict[int, BM25Hit] = {h.page_id: h for h in bm25_hits}

        # ── Map PageIndex nodes to local page_ids via page_index ───────
        # PageIndex returns page_index (PDF page number, 1-based).
        # We map it to our local Page row via (document.pi_doc_id, page_number).
        pi_page_map = await self._map_pi_nodes_to_pages(session, pi_nodes, pi_doc_ids or [])

        # ── RRF scoring ───────────────────────────────────────────────
        all_page_ids: set[int] = set(bm25_by_page.keys()) | set(pi_page_map.keys())

        # Build rank dicts (1-based)
        bm25_ranks = {h.page_id: i + 1 for i, h in enumerate(bm25_hits)}
        pi_page_ids_ordered = list(pi_page_map.keys())
        pi_ranks = {pid: i + 1 for i, pid in enumerate(pi_page_ids_ordered)}

        hits: list[HybridHit] = []
        for pid in all_page_ids:
            bm25_rank = bm25_ranks.get(pid)
            pi_rank = pi_ranks.get(pid)

            bm25_rrf = 1 / (_RRF_K + bm25_rank) if bm25_rank else 0.0
            pi_rrf = 1 / (_RRF_K + pi_rank) if pi_rank else 0.0

            # Weighted combination
            rrf = (1 - self.alpha) * bm25_rrf + self.alpha * pi_rrf

            bm25_hit = bm25_by_page.get(pid)
            pi_info = pi_page_map.get(pid)

            hits.append(HybridHit(
                page_id=pid,
                rrf_score=rrf,
                bm25_score=bm25_hit.score if bm25_hit else 0.0,
                pi_score=pi_info.get("pi_score", 0.0) if pi_info else 0.0,
                matched_bm25_terms=bm25_hit.matched_terms if bm25_hit else [],
                pi_node_title=pi_info.get("title", "") if pi_info else "",
                pi_node_id=pi_info.get("node_id", "") if pi_info else "",
                pi_page_index=pi_info.get("page_index", 0) if pi_info else 0,
                pi_relevant_content=pi_info.get("relevant_content", "") if pi_info else "",
            ))

        hits.sort(key=lambda h: h.rrf_score, reverse=True)
        return hits[: self.final_top_k]

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    async def _map_pi_nodes_to_pages(
        session: AsyncSession,
        nodes: list[PINode],
        pi_doc_ids: list[str],
    ) -> dict[int, dict]:
        """
        Map PageIndex nodes to local page IDs.
        Looks up Page rows by (document.pi_doc_id, page_number).
        Returns {local_page_id: {title, node_id, page_index, relevant_content, pi_score}}
        """
        if not nodes:
            return {}

        from sqlalchemy import select
        from app.db.models import Page, Document

        result_map: dict[int, dict] = {}
        for i, node in enumerate(nodes):
            for rc in node.relevant_contents:
                # Find the local page with matching page_number in documents
                # that have pi_doc_id matching one of the queried pi_doc_ids
                r = await session.execute(
                    select(Page.id)
                    .join(Document, Page.document_id == Document.id)
                    .where(
                        Document.pi_doc_id.in_(pi_doc_ids),
                        Page.page_number == rc.page_index,
                    )
                    .limit(1)
                )
                row = r.scalar_one_or_none()
                if row and row not in result_map:
                    result_map[row] = {
                        "title": node.title,
                        "node_id": node.node_id,
                        "page_index": rc.page_index,
                        "relevant_content": rc.relevant_content,
                        "pi_score": 1.0 / (i + 1),  # positional decay
                    }
        return result_map
