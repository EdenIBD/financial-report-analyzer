import os

import pytest

from src.ingestion.detect import FilingMetadataError, detect_filing_metadata

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def test_detect_rejects_html_without_dei_tags():
    with pytest.raises(FilingMetadataError):
        detect_filing_metadata("<html><body>not a filing at all</body></html>")


def test_detect_rejects_unsupported_document_type():
    html = (
        '<span name="dei:DocumentType">8-K</span>'
        '<span name="dei:TradingSymbol">AAPL</span>'
        '<span name="dei:DocumentFiscalYearFocus">2024</span>'
    )
    with pytest.raises(FilingMetadataError):
        detect_filing_metadata(html)


@pytest.mark.parametrize(
    "filename,expected_type",
    [("AAPL_2023.html", "10-K"), ("AAPL_2025_Q_sample.html", "10-Q")],
)
def test_detect_on_real_filings(filename, expected_type):
    path = os.path.join(RAW_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f"{filename} nu e descarcat local (data/raw/ e gitignored)")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    meta = detect_filing_metadata(html)
    assert meta["filing_type"] == expected_type
    assert meta["ticker"] == "AAPL"
    assert isinstance(meta["fiscal_year"], int)
    assert meta["cik"] == "0000320193"
