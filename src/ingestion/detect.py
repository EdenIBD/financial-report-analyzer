"""Metadata for supported inline-XBRL filings; legacy plain HTML is unsupported."""

from bs4 import BeautifulSoup, UnicodeDammit

_DEI_FIELDS = {
    "document_type": "dei:documenttype",
    "company": "dei:entityregistrantname",
    "ticker": "dei:tradingsymbol",
    "fiscal_year": "dei:documentfiscalyearfocus",
    "cik": "dei:entitycentralindexkey",
}


def decode_filing_html(raw: bytes) -> str:
    """Honor BOM/HTML encoding declarations without silently dropping bytes."""
    decoded = UnicodeDammit(raw, is_html=True)
    if decoded.unicode_markup is None or decoded.contains_replacement_characters:
        raise FilingMetadataError("Cannot decode this HTML file without data loss. Save it as UTF-8 and retry.")
    return decoded.unicode_markup


SUPPORTED_FILING_TYPES = {"10-K", "10-Q"}


class FilingMetadataError(ValueError):
    """Missing/unsupported filing metadata; this does not imply SEC invalidity."""


def detect_filing_metadata(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    values = {key: None for key in _DEI_FIELDS}
    for tag in soup.find_all(attrs={"name": True}):
        name = tag["name"].lower()
        for key, concept in _DEI_FIELDS.items():
            if name == concept and not values[key]:
                values[key] = tag.get_text().strip()

    if not values["document_type"] or not values["ticker"] or not values["fiscal_year"]:
        raise FilingMetadataError(
            "This upload requires a 10-K or 10-Q HTML filing with inline XBRL "
            "metadata (dei:DocumentType, dei:TradingSymbol and "
            "dei:DocumentFiscalYearFocus). One or more values are missing. "
            "Older filings without inline XBRL and files with stripped metadata "
            "are not supported. Download the original primary HTML document from SEC EDGAR."
        )
    if values["document_type"] not in SUPPORTED_FILING_TYPES:
        raise FilingMetadataError(
            f"Unsupported document type: {values['document_type']!r} "
            f"(supported: {sorted(SUPPORTED_FILING_TYPES)})"
        )
    if not values["fiscal_year"].isdigit():
        raise FilingMetadataError(f"Invalid fiscal year detected: {values['fiscal_year']!r}")

    return {
        "filing_type": values["document_type"],
        "company": values["company"] or values["ticker"].upper(),
        "ticker": values["ticker"].upper(),
        "fiscal_year": int(values["fiscal_year"]),
        "cik": values["cik"],
    }
