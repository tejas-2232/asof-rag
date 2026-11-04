from app.parser import filing_content_hash, parse_filing


def test_parser_preserves_sections_and_stable_hashes(filing_html, filing):
    first = parse_filing(filing_html, filing, max_chars=500)
    second = parse_filing(filing_html, filing, max_chars=500)

    assert first
    assert [chunk.content_hash for chunk in first] == [
        chunk.content_hash for chunk in second
    ]
    assert filing.content_hash == filing_content_hash(filing_html)
    assert any("Item 1." in chunk.section for chunk in first)
    assert any("Item 2." in chunk.section for chunk in first)
    assert all("must not be indexed" not in chunk.text for chunk in first)
    assert all(chunk.filing_content_hash == filing.content_hash for chunk in first)
