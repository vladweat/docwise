"""Page-bounded chunking and meta headers."""

from __future__ import annotations

from app.services.ingestion.chunker import (
    CHUNK_MAX_TOKENS,
    CHUNK_MIN_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    citation_snippet,
    chunk_parsed_document,
    count_tokens,
    format_embed_text,
)
from app.services.ingestion.pdf_parser import PageBlock, ParsedDocument, ParsedPage, table_to_gfm
from app.services.text import ingest_tokens


def _block(
    text: str,
    *,
    y: float = 72.0,
    is_heading: bool = False,
    is_table: bool = False,
) -> PageBlock:
    bbox = (72.0, y, 500.0, y + 24.0)
    return PageBlock(
        text=text,
        bbox=bbox,
        font_size=18.0 if is_heading else 11.0,
        is_heading=is_heading,
        is_table=is_table,
        highlight_rects=(bbox,),
    )


def _page(*blocks: PageBlock, page_number: int = 1) -> ParsedPage:
    return ParsedPage(page_number=page_number, width=595.0, height=842.0, blocks=blocks)


def _words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i:04d}" for i in range(n))


def test_short_page_is_one_chunk_even_below_min():
    page = _page(_block("Leave Policy", is_heading=True), _block("Short body text."))
    chunks = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))
    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert chunks[0].section_title == "Leave Policy"
    assert chunks[0].token_count < CHUNK_MIN_TOKENS
    assert "Leave Policy" in chunks[0].content


def test_chunks_do_not_cross_page_boundary():
    page1 = _page(_block(_words(80, "p1")), page_number=1)
    page2 = _page(_block(_words(80, "p2")), page_number=2)
    chunks = chunk_parsed_document(ParsedDocument(total_pages=2, pages=(page1, page2)))
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    for chunk in chunks:
        tokens = ingest_tokens(chunk.content)
        if chunk.page_number == 1:
            assert all(token.startswith("p1") for token in tokens)
        else:
            assert all(token.startswith("p2") for token in tokens)


def test_section_split_stays_inside_page():
    page = _page(
        _block("Expenses", is_heading=True, y=72),
        _block(_words(40, "exp"), y=110),
        _block("Travel", is_heading=True, y=400),
        _block(_words(40, "trv"), y=440),
    )
    chunks = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))
    titles = [chunk.section_title for chunk in chunks]
    assert titles == ["Expenses", "Travel"]
    assert all(chunk.page_number == 1 for chunk in chunks)


def test_overlap_does_not_cross_sections():
    page = _page(
        _block("SecA", is_heading=True, y=72),
        _block(_words(500, "aaa"), y=110),
        _block("SecB", is_heading=True, y=400),
        _block(_words(80, "bbb"), y=440),
    )
    chunks = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))
    by_section = {chunk.section_title: chunk for chunk in chunks}
    assert set(by_section) == {"SecA", "SecB"}
    assert all(token.startswith("aaa") or token == "SecA" for token in ingest_tokens(by_section["SecA"].content))
    assert all(token.startswith("bbb") or token == "SecB" for token in ingest_tokens(by_section["SecB"].content))


def test_long_section_uses_max_window_and_overlap():
    page = _page(_block("Appendix", is_heading=True), _block(_words(700)))
    chunks = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))
    assert len(chunks) >= 2
    assert chunks[0].token_count <= CHUNK_MAX_TOKENS
    assert chunks[0].token_count >= CHUNK_MAX_TOKENS - 20
    first_tokens = ingest_tokens(chunks[0].content)
    second_tokens = ingest_tokens(chunks[1].content)
    assert first_tokens[-CHUNK_OVERLAP_TOKENS:] == second_tokens[:CHUNK_OVERLAP_TOKENS]
    assert all(chunk.page_number == 1 for chunk in chunks)
    assert all(chunk.section_title == "Appendix" for chunk in chunks)


def test_table_stays_markdown_and_is_table():
    markdown = table_to_gfm([["Benefit", "Days"], ["Vacation", "20"]])
    page = _page(_block("Leave Policy", is_heading=True), _block(markdown, y=200, is_table=True))
    chunks = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))
    tables = [chunk for chunk in chunks if chunk.is_table]
    assert len(tables) == 1
    assert tables[0].content.splitlines()[0].startswith("|")
    assert "Vacation" in tables[0].content
    assert tables[0].bbox is not None
    assert tables[0].highlight_rects


def test_long_table_splits_by_row_and_repeats_header():
    header = ["ColA", "ColB"]
    rows = [[f"r{i}", f"v{i}"] for i in range(400)]
    markdown = table_to_gfm([header, *rows])
    assert count_tokens(markdown) > CHUNK_MAX_TOKENS
    page = _page(_block(markdown, is_table=True))
    chunks = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))
    assert len(chunks) >= 2
    assert all(chunk.is_table for chunk in chunks)
    for chunk in chunks:
        lines = chunk.content.splitlines()
        assert lines[0] == "| ColA | ColB |"
        assert lines[1] == "| --- | --- |"
        assert chunk.token_count <= CHUNK_MAX_TOKENS or chunk.token_count == count_tokens(chunk.content)


def test_embed_text_has_meta_content_does_not():
    page = _page(_block("Expenses", is_heading=True), _block("Taxi receipts under forty dollars."))
    chunk = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))[0]
    embed = chunk.embed_text("HR_Policy.pdf")
    assert embed == format_embed_text(
        document_title="HR_Policy.pdf",
        section_title="Expenses",
        page_number=1,
        content=chunk.content,
    )
    assert embed.startswith("[Document: HR_Policy.pdf | Section: Expenses | Page: 1]\n")
    assert not chunk.content.startswith("[Document:")
    assert "Taxi receipts" in chunk.content
    snippet = citation_snippet(chunk.content)
    assert "[Document:" not in snippet
    assert "Taxi receipts" in snippet
    stripped = citation_snippet(embed)
    assert stripped == snippet
    assert not stripped.startswith("[Document:")


def test_missing_section_uses_untitled_in_embed_header():
    page = _page(_block("body only"))
    chunk = chunk_parsed_document(ParsedDocument(total_pages=1, pages=(page,)))[0]
    header = chunk.embed_text("Policy.pdf").split("\n", 1)[0]
    assert header == "[Document: Policy.pdf | Section: Untitled | Page: 1]"
