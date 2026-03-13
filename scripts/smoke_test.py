"""
scripts/smoke_test.py
──────────────────────
Quick end-to-end smoke test using the FastAPI TestClient.
Tests BM25 indexing + query path (PageIndex is mocked).

Usage:
    python scripts/smoke_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Minimal env before imports
import os

os.environ.setdefault("PAGEINDEX_API_KEY", "pi-test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/smoke_test.db")

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def run_smoke():
    # Patch external calls
    with (
        patch(
            "app.pageindex.client.PageIndexAPIClient.submit_document",
            new_callable=AsyncMock,
            return_value="pi-test123",
        ),
        patch(
            "app.pageindex.client.PageIndexAPIClient.poll_until_ready",
            new_callable=AsyncMock,
            return_value={"status": "completed"},
        ),
        patch(
            "app.pageindex.client.PageIndexAPIClient.retrieve",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("app.generation.llm_client.LLMClient.complete", new_callable=AsyncMock) as mock_llm,
    ):
        from app.generation.llm_client import LLMResponse

        mock_llm.return_value = LLMResponse(
            content="MindVault handles enterprise knowledge retrieval using both BM25 and PageIndex.",
            input_tokens=100,
            output_tokens=20,
            model="test-model",
        )

        from app.main import app

        with TestClient(app) as client:
            print("1. Health check…", end=" ")
            r = client.get("/health")
            assert r.status_code == 200
            print("✅")

            print("2. Ingest markdown…", end=" ")
            md_content = b"# Enterprise RAG\n\nMindVault uses hybrid BM25 and PageIndex retrieval.\n\n## Architecture\n\nBM25 handles exact keyword matching. PageIndex handles semantic tree search."
            r = client.post(
                "/ingest/upload", files={"file": ("test.md", md_content, "text/markdown")}
            )
            assert r.status_code == 201, f"Got {r.status_code}: {r.text}"
            doc_id = r.json()["document_id"]
            print(f"✅  (doc_id={doc_id})")

            print("3. List documents…", end=" ")
            r = client.get("/documents")
            assert r.status_code == 200
            assert len(r.json()) >= 1
            print("✅")

            print("4. Index stats…", end=" ")
            r = client.get("/documents/index/stats")
            assert r.status_code == 200
            stats = r.json()
            print(f"✅  ({stats['unique_bm25_terms']} terms)")

            print("5. Query (hybrid)…", end=" ")
            r = client.post("/query", json={"query": "enterprise RAG retrieval"})
            assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
            result = r.json()
            assert len(result["answer"]) > 0
            print(f"✅  latency={result['latency_ms']}ms")
            print(f"   Answer: {result['answer'][:80]}…")
            print(f"   Sources: {[s['filename'] for s in result['sources']]}")

            print("6. Delete document…", end=" ")
            with patch(
                "app.pageindex.client.PageIndexAPIClient.delete_document", new_callable=AsyncMock
            ):
                r = client.delete(f"/documents/{doc_id}")
                assert r.status_code == 204
            print("✅")

    # Cleanup test DB
    try:
        Path("./data/smoke_test.db").unlink(missing_ok=True)
    except Exception:
        pass

    print("\n✅  All smoke tests passed!")


if __name__ == "__main__":
    run_smoke()
