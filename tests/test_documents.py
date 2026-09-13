import os
import tempfile
from unittest.mock import patch

from src.api.documents import process_uploaded_document
from src.ingestion.sections import FilingValidationError

VALID_DEI_HTML = (
    '<span name="dei:DocumentType">10-Q</span>'
    '<span name="dei:EntityRegistrantName">Test Co</span>'
    '<span name="dei:TradingSymbol">TEST</span>'
    '<span name="dei:DocumentFiscalYearFocus">2025</span>'
    '<span name="dei:EntityCentralIndexKey">1234</span>'
)


def _write_temp_html(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


@patch("src.api.documents.psycopg2.connect")
@patch("src.api.documents._update_upload_row")
def test_rejects_file_without_valid_metadata(mock_update, mock_connect):
    # cazul limita explicit din feature-document-upload.md: fisierul uploadat
    # nu e deloc un 10-K/10-Q -> respins inainte de orice indexare.
    path = _write_temp_html("<html><body>not a filing at all</body></html>")
    try:
        process_uploaded_document("doc-1", path)
    finally:
        os.remove(path)

    mock_update.assert_called_once()
    _, kwargs = mock_update.call_args
    assert kwargs["status"] == "error"


@patch("src.api.documents.QdrantClient")
@patch("src.api.documents.ingest_sections")
@patch("src.api.documents.validate_sections")
@patch("src.api.documents.parse_filing")
@patch("src.api.documents.upsert_filing")
@patch("src.api.documents.psycopg2.connect")
@patch("src.api.documents._update_upload_row")
def test_rejects_when_required_sections_missing(
    mock_update, mock_connect, mock_upsert_filing, mock_parse, mock_validate, mock_ingest, mock_qdrant_cls
):
    # metadata (dei:*) e valida, dar parsing-ul nu gaseste toate categoriile
    # canonice obligatorii -> respins fara indexare, nu doar un warning silentios.
    mock_parse.return_value = {"mdna": "text"}
    mock_validate.side_effect = FilingValidationError("categorii lipsa")

    path = _write_temp_html(VALID_DEI_HTML)
    try:
        process_uploaded_document("doc-2", path)
    finally:
        os.remove(path)

    mock_upsert_filing.assert_not_called()
    mock_ingest.assert_not_called()
    _, kwargs = mock_update.call_args
    assert kwargs["status"] == "error"


@patch("src.api.documents.QdrantClient")
@patch("src.api.documents.ingest_sections", return_value=(12, 0.03))
@patch("src.api.documents.validate_sections")
@patch("src.api.documents.parse_filing")
@patch("src.api.documents.upsert_filing")
@patch("src.api.documents.psycopg2.connect")
@patch("src.api.documents._update_upload_row")
def test_success_path_indexes_into_global_corpus_and_marks_ready(
    mock_update, mock_connect, mock_upsert_filing, mock_parse, mock_validate, mock_ingest, mock_qdrant_cls
):
    mock_parse.return_value = {
        "risk_factors": "a",
        "legal_proceedings": "b",
        "mdna": "c",
        "market_risk": "d",
        "financial_statements": "e",
        "controls_procedures": "f",
    }

    path = _write_temp_html(VALID_DEI_HTML)
    try:
        process_uploaded_document("doc-3", path)
    finally:
        os.remove(path)

    mock_upsert_filing.assert_called_once()
    # doc_id include tipul de filing, ca sa nu se coliziona cu corpusul fix
    # ("TEST_2025") sau intre un 10-K si un 10-Q ale aceleiasi companii/an.
    doc_id_arg = mock_upsert_filing.call_args[0][1]
    assert doc_id_arg == "TEST_2025_10Q"

    mock_ingest.assert_called_once()
    _, kwargs = mock_update.call_args
    assert kwargs["status"] == "ready"
    assert kwargs["chunks_indexed"] == 12
