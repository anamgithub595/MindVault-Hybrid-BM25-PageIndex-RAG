"""
app/retrieval/pageindex_retriever.py
──────────────────────────────────────
Converts a query string → PageIndex node hits via the PageIndex API.
Has zero knowledge of BM25 or the local SQLite database.
"""
from __future__ import annotations
import asyncio
import logging
from app.pageindex.client import PageIndexAPIClient, PINode
from app.core.exceptions import PageIndexRetrievalError

logger = logging.getLogger(__name__)


class PageIndexRetriever:
    def __init__(self, client: PageIndexAPIClient, top_k: int = 5):
        self._client = client
        self._top_k = top_k

    async def retrieve(
        self,
        query: str,
        pi_doc_ids: list[str],
        thinking: bool = False,
    ) -> list[PINode]:
        """
        Runs PageIndex retrieval against each pi_doc_id concurrently,
        merges and de-duplicates results, returns top_k nodes.
        """
        if not pi_doc_ids:
            return []

        tasks = [
            self._client.retrieve(pid, query, thinking)
            for pid in pi_doc_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        nodes: list[PINode] = []
        seen_ids: set[str] = set()
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"[PIRetriever] doc {pi_doc_ids[i]} error: {r}")
                continue
            for node in r:
                if node.node_id not in seen_ids:
                    seen_ids.add(node.node_id)
                    nodes.append(node)

        # Sort by position in the document (page_index) as a proxy for relevance
        nodes.sort(key=lambda n: len(n.relevant_contents), reverse=True)
        logger.debug(f"[PIRetriever] {len(nodes)} unique nodes across {len(pi_doc_ids)} docs")
        return nodes[: self._top_k]
