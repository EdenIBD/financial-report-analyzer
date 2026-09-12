import os

import pytest

from src.ingestion.parse import ITEM_TITLE_RE, TARGET_ITEMS, parse_filing

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def test_regex_matches_apple_style_number_and_title_together():
    assert ITEM_TITLE_RE.match("Item 1A.\xa0\xa0\xa0\xa0Risk Factors")


def test_regex_matches_google_style_number_only_no_trailing_space():
    # bug real: Google pune doar "ITEM 1." intr-un element separat, fara text
    # dupa punct — regexul initial (care cerea spatiu obligatoriu) pica aici.
    assert ITEM_TITLE_RE.match("ITEM 1.")


def test_regex_extracts_letter_suffix():
    match = ITEM_TITLE_RE.match("Item 9C.\xa0\xa0\xa0\xa0Disclosure Regarding Foreign Jurisdictions")
    assert match.group(1).upper() == "9C"


def test_regex_does_not_match_unrelated_text_containing_item_word():
    assert not ITEM_TITLE_RE.match("Items discussed below are important to investors.")


@pytest.mark.parametrize("filename", ["AAPL_2023.html", "GOOGL_2023.html", "MSFT_2024.html"])
def test_parse_filing_finds_all_target_sections(filename):
    path = os.path.join(RAW_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f"{filename} nu e descarcat local (data/raw/ e gitignored)")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    sections = parse_filing(html)
    found_items = {item.replace("Item", "") for item in sections}
    missing = TARGET_ITEMS - found_items
    assert not missing, f"sectiuni lipsa in {filename}: {missing}"
    for item, text in sections.items():
        assert len(text.strip()) > 0, f"sectiunea {item} din {filename} e goala"
