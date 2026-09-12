from src.ingestion.chunk import chunk_section


def test_short_text_stays_one_chunk():
    text = "This is a short piece of text."
    chunks = chunk_section(text)
    assert chunks == [text]


def test_long_text_splits_into_multiple_chunks():
    text = ". ".join(f"Sentence number {i} in a long section" for i in range(200))
    chunks = chunk_section(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 700 + 50  # marja mica pt separatori


def test_consecutive_chunks_overlap():
    text = ". ".join(f"Sentence number {i} in a long section" for i in range(200))
    chunks = chunk_section(text)
    # cu chunk_overlap=100, sfarsitul unui chunk ar trebui sa apara in urmatorul
    assert chunks[0][-30:] in chunks[1] or chunks[1].startswith(chunks[0][-30:])


def test_empty_text_returns_no_chunks():
    assert chunk_section("") == []
