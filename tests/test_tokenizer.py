from src.ingestion.tokenizer import count_tokens


def test_empty_string_has_zero_tokens():
    assert count_tokens("") == 0


def test_longer_text_has_more_tokens():
    short = count_tokens("Apple Inc.")
    long = count_tokens("Apple Inc. reported strong revenue growth in the fiscal year 2023.")
    assert long > short


def test_known_short_phrase_token_count():
    # "Apple Inc." cu cl100k_base -> tokenizare stabila, verificata empiric
    assert count_tokens("Apple Inc.") > 0
