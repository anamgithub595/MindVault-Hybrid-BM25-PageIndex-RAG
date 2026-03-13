"""
app/connectors/notion_connector.py
────────────────────────────────────
Pulls pages from the Notion API.
Splits at heading boundaries → one RawPage per section.
"""

from __future__ import annotations

import re

import httpx

from app.connectors.base import BaseConnector, RawDocument, RawPage
from app.core.config import get_settings
from app.core.exceptions import ParseError

_API = "https://api.notion.com/v1"
_VER = "2022-06-28"


class NotionConnector(BaseConnector):
    def __init__(self, token: str | None = None):
        self._token = token or get_settings().notion_token
        if not self._token:
            raise ParseError("NOTION_TOKEN is not set")

    async def extract(self, source: bytes | str, filename: str) -> RawDocument:
        page_id = self._parse_id(str(source))
        async with httpx.AsyncClient(timeout=30) as c:
            meta = await self._get(c, f"pages/{page_id}")
            blocks = await self._all_blocks(c, page_id)
        title = self._title(meta)
        pages = self._to_pages(blocks)
        return RawDocument(
            filename=filename or title or page_id,
            source_type="notion",
            title=title,
            pages=pages,
        )

    @property
    def _hdrs(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Notion-Version": _VER}

    async def _get(self, c: httpx.AsyncClient, path: str) -> dict:
        r = await c.get(f"{_API}/{path}", headers=self._hdrs)
        if r.status_code != 200:
            raise ParseError(f"Notion {path}: {r.status_code} {r.text}")
        return r.json()

    async def _all_blocks(self, c: httpx.AsyncClient, block_id: str) -> list[dict]:
        blocks, cursor = [], None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            r = await c.get(f"{_API}/blocks/{block_id}/children", headers=self._hdrs, params=params)
            if r.status_code != 200:
                break
            data = r.json()
            blocks.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return blocks

    @staticmethod
    def _parse_id(src: str) -> str:
        m = re.search(r"([a-f0-9]{32})", src.replace("-", ""))
        if m:
            raw = m.group(1)
            return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
        return src

    @staticmethod
    def _title(meta: dict) -> str | None:
        for key in ("title", "Name", "Title"):
            p = meta.get("properties", {}).get(key, {})
            if p.get("type") == "title":
                return "".join(t.get("plain_text", "") for t in p.get("title", [])) or None
        return None

    @staticmethod
    def _plain(block: dict) -> str:
        bt = block.get("type", "")
        return "".join(r.get("plain_text", "") for r in block.get(bt, {}).get("rich_text", []))

    def _to_pages(self, blocks: list[dict]) -> list[RawPage]:
        pages: list[RawPage] = []
        heading: str | None = None
        lines: list[str] = []

        def flush():
            nonlocal lines, heading
            c = "\n".join(lines).strip()
            if c:
                pages.append(
                    RawPage(page_number=len(pages) + 1, content=c, section_heading=heading)
                )
            lines = []

        for b in blocks:
            bt = b.get("type", "")
            if bt in ("heading_1", "heading_2"):
                flush()
                heading = self._plain(b)
            else:
                t = self._plain(b)
                if t:
                    lines.append(t)
        flush()
        return pages or [RawPage(page_number=1, content="(empty)", section_heading=None)]
