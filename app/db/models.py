"""
app/db/models.py
─────────────────
SQLAlchemy ORM models.

Tables:
  documents    — one row per ingested source file
  pages        — one row per chunk extracted from a document  (BM25 source)
  page_index   — inverted BM25 index: (term, page_id, tf)
  pi_docs      — maps our document_id → PageIndex doc_id (cloud)
  query_log    — full audit trail of every query + response
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ── Documents ─────────────────────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)  # pdf|md|notion|docx
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    # bm25_status: local index build status
    bm25_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|indexed|error
    # pi_status: PageIndex cloud processing status
    pi_status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending|processing|completed|failed|skipped
    pi_doc_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # pi-abc123...
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pages: Mapped[list[Page]] = relationship(
        "Page", back_populates="document", cascade="all, delete-orphan"
    )


# ── Pages (BM25 chunks) ───────────────────────────────────────────────────
class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_heading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped[Document] = relationship("Document", back_populates="pages")
    index_entries: Mapped[list[PageIndexEntry]] = relationship(
        "PageIndexEntry", back_populates="page", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_pages_document_id", "document_id"),)


# ── BM25 Inverted Index ───────────────────────────────────────────────────
class PageIndexEntry(Base):
    """
    One row per (term, page) pair.
    IDF is computed at query time from doc_freq counts.
    """

    __tablename__ = "page_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(256), nullable=False)
    page_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False
    )
    tf: Mapped[float] = mapped_column(Float, nullable=False)
    term_count: Mapped[int] = mapped_column(Integer, default=1)

    page: Mapped[Page] = relationship("Page", back_populates="index_entries")

    __table_args__ = (
        UniqueConstraint("term", "page_id", name="uq_term_page"),
        Index("ix_pi_term", "term"),
        Index("ix_pi_page_id", "page_id"),
    )


# ── Query Audit Log ───────────────────────────────────────────────────────
class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Which document_ids were scoped (JSON list or empty = all)
    scoped_doc_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sources used
    bm25_page_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    pi_node_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    final_page_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
