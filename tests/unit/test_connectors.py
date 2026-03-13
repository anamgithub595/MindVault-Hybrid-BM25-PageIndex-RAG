"""tests/unit/test_connectors.py — connector parsing tests"""

import pytest

from app.connectors.markdown_connector import MarkdownConnector


@pytest.mark.asyncio
async def test_markdown_no_headings():
    c = MarkdownConnector()
    doc = await c.extract(b"Hello world. This is a plain text document.", "test.md")
    assert len(doc.pages) == 1
    assert "Hello" in doc.pages[0].content


@pytest.mark.asyncio
async def test_markdown_heading_split():
    md = b"# Section A\nContent A\n\n## Section B\nContent B"
    c = MarkdownConnector()
    doc = await c.extract(md, "test.md")
    assert len(doc.pages) == 2
    assert doc.pages[0].section_heading == "Section A"
    assert doc.pages[1].section_heading == "Section B"


@pytest.mark.asyncio
async def test_markdown_title_from_h1():
    c = MarkdownConnector()
    doc = await c.extract(b"# My Document\nContent here", "test.md")
    assert doc.title == "My Document"


@pytest.mark.asyncio
async def test_markdown_invalid_encoding():
    from app.core.exceptions import ParseError

    c = MarkdownConnector()
    with pytest.raises(ParseError):
        await c.extract(b"\xff\xfe invalid bytes", "bad.md")
