"""
app/pageindex/client.py
────────────────────────
Thin async wrapper around the PageIndex REST API.
Uses the pageindex SDK where available; falls back to raw httpx.

Responsibilities:
  - submit_document(pdf_bytes, filename) → pi_doc_id
  - poll_until_ready(pi_doc_id) → tree result
  - retrieve(pi_doc_id, query) → list[PINode]
  - chat(messages, doc_ids) → str
  - delete_document(pi_doc_id)
  - list_documents()

This is the ONLY file in the project that talks to PageIndex APIs.
"""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from app.core.exceptions import (
    PageIndexSubmitError,
    PageIndexTimeoutError,
    PageIndexRetrievalError,
)

logger = logging.getLogger(__name__)

_BASE = "https://api.pageindex.ai"


@dataclass
class PIRelevantContent:
    page_index: int      # 1-based PDF page number
    relevant_content: str


@dataclass
class PINode:
    title: str
    node_id: str
    page_index: int
    relevant_contents: list[PIRelevantContent] = field(default_factory=list)
    # score injected by hybrid fusion
    pi_score: float = 0.0


class PageIndexAPIClient:
    """
    Async HTTP client for the PageIndex API.
    All methods are coroutines.
    """

    def __init__(
        self,
        api_key: str,
        poll_interval: float = 2.0,
        poll_timeout: float = 120.0,
    ):
        if not api_key:
            raise ValueError("PAGEINDEX_API_KEY is not set. Get it from https://dash.pageindex.ai")
        self._key = api_key
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._headers = {"api_key": api_key}

    # ── Document lifecycle ────────────────────────────────────────────

    async def submit_document(self, pdf_bytes: bytes, filename: str) -> str:
        """
        Upload a PDF to PageIndex for tree-index generation.
        Returns the pi_doc_id string (e.g. "pi-abc123").
        """
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(
                f"{_BASE}/doc/",
                headers=self._headers,
                files={"file": (filename, pdf_bytes, "application/pdf")},
            )
        if resp.status_code not in (200, 201):
            raise PageIndexSubmitError(
                f"PageIndex submit failed ({resp.status_code}): {resp.text}"
            )
        doc_id = resp.json().get("doc_id")
        if not doc_id:
            raise PageIndexSubmitError(f"No doc_id in response: {resp.text}")
        logger.info(f"[PageIndex] Submitted '{filename}' → {doc_id}")
        return doc_id

    async def poll_until_ready(self, pi_doc_id: str) -> dict:
        """
        Poll GET /doc/{id}/?type=tree until status == 'completed'.
        Returns the full response dict including 'result' tree.
        Raises PageIndexTimeoutError if it exceeds poll_timeout.
        """
        deadline = time.monotonic() + self._poll_timeout
        async with httpx.AsyncClient(timeout=30) as c:
            while time.monotonic() < deadline:
                resp = await c.get(
                    f"{_BASE}/doc/{pi_doc_id}/",
                    headers=self._headers,
                    params={"type": "tree"},
                )
                if resp.status_code != 200:
                    logger.warning(f"[PageIndex] poll {pi_doc_id}: HTTP {resp.status_code}")
                    await asyncio.sleep(self._poll_interval)
                    continue
                data = resp.json()
                status = data.get("status")
                if status == "completed":
                    logger.info(f"[PageIndex] {pi_doc_id} ready")
                    return data
                if status == "failed":
                    raise PageIndexRetrievalError(f"PageIndex processing failed for {pi_doc_id}")
                logger.debug(f"[PageIndex] {pi_doc_id} status={status}, waiting…")
                await asyncio.sleep(self._poll_interval)

        raise PageIndexTimeoutError(
            f"PageIndex did not complete within {self._poll_timeout}s for {pi_doc_id}"
        )

    async def get_document_metadata(self, pi_doc_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{_BASE}/doc/{pi_doc_id}/metadata", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def list_documents(self, limit: int = 50, offset: int = 0) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{_BASE}/docs",
                headers=self._headers,
                params={"limit": limit, "offset": offset},
            )
        resp.raise_for_status()
        return resp.json()

    async def delete_document(self, pi_doc_id: str) -> None:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.delete(f"{_BASE}/doc/{pi_doc_id}/", headers=self._headers)
        if resp.status_code not in (200, 204):
            logger.warning(f"[PageIndex] delete {pi_doc_id}: HTTP {resp.status_code}")

    # ── Retrieval (legacy) ────────────────────────────────────────────

    async def retrieve(self, pi_doc_id: str, query: str, thinking: bool = False) -> list[PINode]:
        """
        Submit a retrieval query and poll until results are ready.
        Returns a list of PINode objects with relevant_contents.
        """
        # 1. Check if ready
        async with httpx.AsyncClient(timeout=30) as c:
            tree_resp = await c.get(
                f"{_BASE}/doc/{pi_doc_id}/",
                headers=self._headers,
                params={"type": "tree"},
            )
        if not tree_resp.json().get("retrieval_ready"):
            logger.warning(f"[PageIndex] {pi_doc_id} not retrieval_ready — skipping")
            return []

        # 2. Submit retrieval task
        async with httpx.AsyncClient(timeout=30) as c:
            sub = await c.post(
                f"{_BASE}/retrieval/",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"doc_id": pi_doc_id, "query": query, "thinking": thinking},
            )
        if sub.status_code not in (200, 201):
            logger.error(f"[PageIndex] retrieval submit failed: {sub.text}")
            return []

        retrieval_id = sub.json().get("retrieval_id")
        if not retrieval_id:
            return []

        # 3. Poll for result
        deadline = time.monotonic() + self._poll_timeout
        async with httpx.AsyncClient(timeout=30) as c:
            while time.monotonic() < deadline:
                r = await c.get(
                    f"{_BASE}/retrieval/{retrieval_id}/",
                    headers=self._headers,
                )
                if r.status_code != 200:
                    await asyncio.sleep(self._poll_interval)
                    continue
                data = r.json()
                if data.get("status") == "completed":
                    return self._parse_nodes(data.get("retrieved_nodes", []))
                if data.get("status") == "failed":
                    logger.error(f"[PageIndex] retrieval {retrieval_id} failed")
                    return []
                await asyncio.sleep(self._poll_interval)

        raise PageIndexTimeoutError(f"Retrieval {retrieval_id} timed out")

    # ── Chat API ──────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        doc_ids: list[str] | str | None = None,
        stream: bool = False,
        temperature: float | None = None,
        enable_citations: bool = True,
    ) -> str:
        """
        Call PageIndex Chat API (non-streaming) and return answer text.
        """
        payload: dict = {"messages": messages, "stream": False}
        if doc_ids:
            payload["doc_id"] = doc_ids
        if temperature is not None:
            payload["temperature"] = temperature
        if enable_citations:
            payload["enable_citations"] = True

        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(
                f"{_BASE}/chat/completions",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code != 200:
            raise PageIndexRetrievalError(
                f"PageIndex Chat API error ({resp.status_code}): {resp.text}"
            )
        return resp.json()["choices"][0]["message"]["content"]

    # ── Parser ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_nodes(raw_nodes: list[dict]) -> list[PINode]:
        nodes = []
        for n in raw_nodes:
            contents = [
                PIRelevantContent(
                    page_index=rc.get("page_index", 0),
                    relevant_content=rc.get("relevant_content", ""),
                )
                for rc in n.get("relevant_contents", [])
            ]
            nodes.append(PINode(
                title=n.get("title", ""),
                node_id=n.get("node_id", ""),
                page_index=n.get("page_index", 0),
                relevant_contents=contents,
            ))
        return nodes
