"""
app/connectors/markdown_connector.py
──────────────────────────────────────
Splits Markdown / plain-text files at H1/H2 heading boundaries.
"""

from __future__ import annotations

import re

from app.connectors.base import BaseConnector, RawDocument, RawPage
from app.core.exceptions import ParseError

_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)


class MarkdownConnector(BaseConnector):
    async def extract(self, source: bytes | str, filename: str) -> RawDocument:
        try:
            text = source.decode("utf-8") if isinstance(source, bytes) else source
        except UnicodeDecodeError as e:
            raise ParseError(f"Cannot decode '{filename}' as UTF-8") from e

        text = self._clean(text)
        title = self._h1(text) or filename
        pages = self._split(text)
        return RawDocument(filename=filename, source_type="markdown", title=title, pages=pages)

    @staticmethod
    def _h1(text: str) -> str | None:
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _split(text: str) -> list[RawPage]:
        splits = [m.start() for m in _HEADING_RE.finditer(text)]
        if not splits:
            return [RawPage(page_number=1, content=text)]
        splits.append(len(text))
        pages: list[RawPage] = []
        for i, start in enumerate(splits[:-1]):
            section = text[start : splits[i + 1]].strip()
            if not section:
                continue
            hm = _HEADING_RE.match(section)
            pages.append(
                RawPage(
                    page_number=len(pages) + 1,
                    content=section,
                    section_heading=hm.group(2).strip() if hm else None,
                )
            )
        return pages
