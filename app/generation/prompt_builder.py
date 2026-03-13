"""
app/generation/prompt_builder.py
──────────────────────────────────
Assembles the LLM prompt from hybrid retrieval results.
No DB calls — receives pre-fetched page + node data.

Each page context shows:
  - Document title + filename
  - Page number (BM25 source)
  - PageIndex node title + relevant snippet (if available)
  - Full raw page text (BM25 source)
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PageContext:
    page_id: int
    page_number: int
    document_title: str
    filename: str
    section_heading: str | None
    content: str            # full BM25 page text
    rrf_score: float
    bm25_score: float
    pi_node_title: str      # "" if no PI match
    pi_relevant_content: str  # PI snippet — often more focused than full page


SYSTEM_PROMPT = """\
You are MindVault, an enterprise knowledge base assistant for Acme Technologies.

Your job is to answer questions accurately using ONLY the document context provided below.

RESPONSE RULES:
1. Always cite your sources inline using [Doc: "<title>", Page <n>] after every factual claim.
2. If a PageIndex excerpt is available for a page, use it as the primary source — it is the most relevant snippet.
3. Structure your answer clearly. For questions about people or employees, use a ranked list with reasoning.
4. When recommending a person or resource, explicitly state WHY — reference their specific skills, experience level, certifications, current workload, or project history from the documents.
5. If the documents do not contain enough information to answer confidently, say exactly: "I could not find a confident answer in the indexed documents." Do not guess.
6. Never mention BM25, PageIndex, RRF, or any internal system names.
7. Never fabricate names, scores, dates, or facts not present in the context.
8. Keep answers professional, direct, and enterprise-appropriate.
"""

USER_TEMPLATE = """\
Question: {query}

─── Retrieved Context (ranked by hybrid BM25 + PageIndex score) ───
{context_block}
─── End of Context ───

Answer with citations:"""


class PromptBuilder:
    def build(self, query: str, pages: list[PageContext]) -> tuple[str, str]:
        """Returns (system_prompt, user_message)."""
        context_block = "\n\n".join(self._format_page(i + 1, p) for i, p in enumerate(pages))
        return SYSTEM_PROMPT, USER_TEMPLATE.format(query=query, context_block=context_block)

    @staticmethod
    def _format_page(rank: int, p: PageContext) -> str:
        lines = [
            f"[{rank}] \"{p.document_title}\" | File: {p.filename} | Page {p.page_number}"
            f"  (RRF={p.rrf_score:.4f}  BM25={p.bm25_score:.3f})",
        ]
        if p.section_heading:
            lines.append(f"  Section: {p.section_heading}")
        if p.pi_node_title:
            lines.append(f"  PageIndex Node: {p.pi_node_title}")
        if p.pi_relevant_content:
            lines.append(f"  PI Excerpt: {p.pi_relevant_content.strip()}")
        lines.append(f"  Full text: {p.content.strip()[:800]}")  # cap at 800 chars per page
        return "\n".join(lines)
