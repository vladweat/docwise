from __future__ import annotations

from app.services.ingestion.chunker import chunk_parsed_document, format_embed_text
from app.services.ingestion.pdf_parser import parse_pdf, table_to_gfm

from pdf_fixtures import blank_pdf_bytes, policy_pdf_bytes


def test_parse_pdf_uses_1based_physical_pages():
    parsed = parse_pdf(policy_pdf_bytes())
    assert parsed.total_pages == 2
    assert [page.page_number for page in parsed.pages] == [1, 2]


def test_parse_pdf_extracts_headings_and_table_markdown():
    parsed = parse_pdf(policy_pdf_bytes())
    page1, page2 = parsed.pages
    headings = [block.text for block in page1.blocks if block.is_heading]
    assert any("Leave Policy" in text for text in headings)
    assert any(block.is_heading and "Expenses" in block.text for block in page2.blocks)

    tables = [block for block in page1.blocks if block.is_table]
    assert len(tables) == 1
    markdown = tables[0].text
    assert markdown.startswith("|")
    assert "Benefit" in markdown
    assert "Vacation" in markdown
    assert "---" in markdown
    assert tables[0].highlight_rects


def test_parse_pdf_keeps_block_coordinates():
    parsed = parse_pdf(policy_pdf_bytes())
    for page in parsed.pages:
        assert page.width > 0 and page.height > 0
        for block in page.blocks:
            x0, y0, x1, y1 = block.bbox
            assert x1 > x0 and y1 > y0
            assert 0 <= x0 <= page.width
            assert 0 <= y0 <= page.height


def test_table_to_gfm_escapes_pipes_and_fills_header():
    markdown = table_to_gfm([["A|B", "C"], [None, "1"]])
    assert markdown.splitlines()[0] == "| A\\|B | C |"
    assert markdown.splitlines()[1] == "| --- | --- |"
    assert markdown.splitlines()[2] == "|  | 1 |"


def test_blank_pdf_has_pages_but_no_blocks():
    parsed = parse_pdf(blank_pdf_bytes())
    assert parsed.total_pages == 1
    assert parsed.pages[0].blocks == ()


def test_chunks_from_fixture_stay_on_one_page():
    chunks = chunk_parsed_document(parse_pdf(policy_pdf_bytes()))
    assert chunks
    pages = {chunk.page_number for chunk in chunks}
    assert pages <= {1, 2}
    assert any(chunk.is_table and "| Benefit |" in chunk.content for chunk in chunks)
    for chunk in chunks:
        assert chunk.page_number in (1, 2)
        assert "[Document:" not in chunk.content
        embed = format_embed_text(
            document_title="HR_Policy.pdf",
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            content=chunk.content,
        )
        assert embed.startswith("[Document: HR_Policy.pdf | Section:")
        assert f"| Page: {chunk.page_number}]" in embed.split("\n", 1)[0]
        assert embed.endswith(chunk.content)
