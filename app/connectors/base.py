"""
app/connectors/base.py
───────────────────────
Abstract base class + shared data types for all document connectors.
Connectors know nothing about indexing, the database, or PageIndex.
"""

from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field


@dataclass
class RawPage:
    page_number: int  # 1-based
    content: str
    section_heading: str | None = None


@dataclass
class RawDocument:
    filename: str
    source_type: str  # pdf | markdown | notion | docx
    title: str | None
    pages: list[RawPage] = field(default_factory=list)


class BaseConnector(abc.ABC):
    @abc.abstractmethod
    async def extract(self, source: bytes | str, filename: str) -> RawDocument: ...

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
