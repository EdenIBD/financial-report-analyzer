import os

import pytest

from src.ingestion.parse import ITEM_TITLE_RE, PART_TITLE_RE, parse_filing
from src.ingestion.sections import REQUIRED_CANONICAL_SECTIONS

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


def test_part_regex_matches_10q_style_part_titles():
    # verificat pe un 10-Q real AAPL: "PART I  —  FINANCIAL INFORMATION"
    assert PART_TITLE_RE.match("PART I  —  FINANCIAL INFORMATION")
    assert PART_TITLE_RE.match("PART II  —  OTHER INFORMATION")


@pytest.mark.parametrize("filename", ["AAPL_2023.html", "GOOGL_2023.html", "MSFT_2024.html"])
def test_parse_filing_10k_finds_all_canonical_sections(filename):
    path = os.path.join(RAW_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f"{filename} nu e descarcat local (data/raw/ e gitignored)")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    sections = parse_filing(html, filing_type="10-K")
    missing = REQUIRED_CANONICAL_SECTIONS - set(sections)
    assert not missing, f"categorii lipsa in {filename}: {missing}"
    for category, text in sections.items():
        assert len(text.strip()) > 0, f"categoria {category} din {filename} e goala"


def test_parse_filing_10q_disambiguates_part1_vs_part2_item1():
    path = os.path.join(RAW_DIR, "AAPL_2025_Q_sample.html")
    if not os.path.exists(path):
        pytest.skip("AAPL_2025_Q_sample.html nu e descarcat local (data/raw/ e gitignored)")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    sections = parse_filing(html, filing_type="10-Q")

    missing = REQUIRED_CANONICAL_SECTIONS - set(sections)
    assert not missing, f"categorii lipsa: {missing}"
    # Part I Item1 (Financial Statements) si Part II Item1 (Legal Proceedings)
    # trebuie sa ajunga in categorii diferite, nu amestecate intr-una singura.
    assert "condensed consolidated statements" in sections["financial_statements"].lower()
    assert "legal proceedings" not in sections["financial_statements"].lower()[:200]
    assert "digital markets act" in sections["legal_proceedings"].lower()
