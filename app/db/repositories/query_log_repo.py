"""
app/db/repositories/query_log_repo.py
───────────────────────────────────────
Write-only audit trail for every query.
"""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QueryLog


class QueryLogRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def log(
        self,
        query_text: str,
        scoped_doc_ids: list[int] | None,
        bm25_page_ids: list[int],
        pi_node_ids: list[str],
        final_page_ids: list[int],
        answer: str,
        latency_ms: int,
    ) -> None:
        entry = QueryLog(
            query_text=query_text,
            scoped_doc_ids=json.dumps(scoped_doc_ids) if scoped_doc_ids else None,
            bm25_page_ids=json.dumps(bm25_page_ids),
            pi_node_ids=json.dumps(pi_node_ids),
            final_page_ids=json.dumps(final_page_ids),
            answer=answer,
            latency_ms=latency_ms,
        )
        self._s.add(entry)
