"""
app/connectors/pdf_connector.py
─────────────────────────────────
Extracts text from PDF files using pdfplumber.
One PDF page → one RawPage.
Also exports the raw bytes so PageIndex can ingest the original PDF.
"""
from __future__ import annotations
import io
from app.connectors.base import BaseConnector, RawDocument, RawPage
from app.core.exceptions import ParseError


class PDFConnector(BaseConnector):
    async def extract(self, source: bytes | str, filename: str) -> RawDocument:
        try:
            import pdfplumber
        except ImportError as e:
            raise ParseError("pdfplumber not installed") from e

        if not isinstance(source, bytes):
            raise ParseError("PDFConnector expects raw bytes")

        try:
            pages: list[RawPage] = []
            with pdfplumber.open(io.BytesIO(source)) as pdf:
                title = (pdf.metadata or {}).get("Title") or filename
                for i, pdf_page in enumerate(pdf.pages, start=1):
                    text = self._clean(pdf_page.extract_text() or "")
                    if text:
                        pages.append(RawPage(page_number=i, content=text))
            return RawDocument(filename=filename, source_type="pdf", title=title, pages=pages)
        except Exception as exc:
            raise ParseError(f"Failed to parse PDF '{filename}': {exc}") from exc
