"""Detectie automata a metadatelor unui filing (tip, companie, ticker, an fiscal)
direct din tag-urile inline XBRL standard SEC EDGAR (dei:*), prezente pe orice
10-K/10-Q modern depus pe EDGAR — verificat pe filing-uri reale AAPL (10-K si
10-Q) si GOOGL. Mult mai robust decat un regex pe textul liber de coperta, care
difera intre filer-i: astea sunt tag-uri structurate, standardizate de SEC.

Daca tag-urile lipsesc complet, fisierul nu e un filing EDGAR real cu inline
XBRL — primul semnal de validare ceruta explicit inainte de indexare (vezi
feature-document-upload.md: "ar trebui in primul rand sa se verifice formatul").
"""

import re

_DEI_TAG_PATTERNS = {
    "document_type": re.compile(r'name="dei:DocumentType"[^>]*>([^<]*)<', re.IGNORECASE),
    "company": re.compile(r'name="dei:EntityRegistrantName"[^>]*>([^<]*)<', re.IGNORECASE),
    "ticker": re.compile(r'name="dei:TradingSymbol"[^>]*>([^<]*)<', re.IGNORECASE),
    "fiscal_year": re.compile(r'name="dei:DocumentFiscalYearFocus"[^>]*>([^<]*)<', re.IGNORECASE),
    "cik": re.compile(r'name="dei:EntityCentralIndexKey"[^>]*>([^<]*)<', re.IGNORECASE),
}

SUPPORTED_FILING_TYPES = {"10-K", "10-Q"}


class FilingMetadataError(ValueError):
    """Fisierul nu contine tag-urile inline XBRL standard SEC EDGAR, deci nu
    pare sa fie un 10-K/10-Q real, sau tipul detectat nu e suportat."""


def detect_filing_metadata(html: str) -> dict:
    values = {key: None for key in _DEI_TAG_PATTERNS}
    for key, pattern in _DEI_TAG_PATTERNS.items():
        match = pattern.search(html)
        if match:
            values[key] = match.group(1).strip()

    if not values["document_type"] or not values["ticker"] or not values["fiscal_year"]:
        raise FilingMetadataError(
            "Standard inline XBRL tags not found (dei:DocumentType / "
            "dei:TradingSymbol / dei:DocumentFiscalYearFocus) — this file does not "
            "look like a real 10-K/10-Q from SEC EDGAR."
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
