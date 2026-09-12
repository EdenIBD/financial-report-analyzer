"""POST /documents/upload + GET /documents/{id}/status — upload de 10-K/10-Q
direct din frontend, procesat asincron in fundal (vezi feature-document-upload.md).

Fluxul de validare, in ordinea ceruta explicit: intai formatul (tag-uri inline
XBRL SEC EDGAR valide, detect_filing_metadata), apoi structura reala (toate
categoriile canonice de sectiuni gasite dupa parsing, validate_sections) —
daca oricare esueaza, documentul NU e indexat deloc, doar status="error" cu
motivul. Daca ambele trec, documentul intra in corpusul global unic (aceeasi
colectie Qdrant/tabel Postgres ca cele 3 companii fixe), reutilizand exact
acelasi pipeline de procesare (src/ingestion/pipeline.py).
"""

import os
import uuid

import psycopg2
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from pydantic import BaseModel
from qdrant_client import QdrantClient

from src.ingestion.detect import FilingMetadataError, detect_filing_metadata
from src.ingestion.parse import parse_filing
from src.ingestion.pipeline import ingest_sections, upsert_filing
from src.ingestion.sections import FilingValidationError, validate_sections

router = APIRouter()

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "uploads"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")


class UploadResponse(BaseModel):
    document_id: str
    status: str


class UploadStatusResponse(BaseModel):
    document_id: str
    status: str
    original_filename: str
    company: str | None
    ticker: str | None
    fiscal_year: int | None
    filing_type: str | None
    sections_found: int | None
    chunks_indexed: int | None
    error_message: str | None


def _db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _insert_upload_row(conn, document_id: str, filename: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_uploads (document_id, original_filename, status)
            VALUES (%s, %s, 'processing')
            """,
            (document_id, filename),
        )
    conn.commit()


def _update_upload_row(conn, document_id: str, **fields) -> None:
    set_parts = [f"{key} = %s" for key in fields] + ["updated_at = now()"]
    values = list(fields.values())
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE document_uploads SET {', '.join(set_parts)} WHERE document_id = %s",
            (*values, document_id),
        )
    conn.commit()


def process_uploaded_document(document_id: str, file_path: str) -> None:
    """Ruleaza in fundal (BackgroundTasks): detectie -> validare -> ingestie.
    Orice esec (format nerecunoscut, sectiuni lipsa, eroare API) se reflecta
    in status='error' + error_message, nu propaga o exceptie necontrolata."""
    conn = _db_conn()
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            html = f.read()

        try:
            meta = detect_filing_metadata(html)
        except FilingMetadataError as e:
            _update_upload_row(conn, document_id, status="error", error_message=str(e))
            return

        sections = parse_filing(html, filing_type=meta["filing_type"])
        try:
            validate_sections(sections)
        except FilingValidationError as e:
            _update_upload_row(
                conn,
                document_id,
                status="error",
                error_message=str(e),
                company=meta["company"],
                ticker=meta["ticker"],
                fiscal_year=meta["fiscal_year"],
                filing_type=meta["filing_type"],
                sections_found=len(sections),
            )
            return

        # sufix cu tipul de filing: evita coliziunea cu doc_id-urile fixe
        # (ex: "AAPL_2023" din corpusul EDGAR) si intre un 10-K si un 10-Q
        # ale aceleiasi companii/an ("AAPL_2026_10K" vs "AAPL_2026_10Q").
        doc_id = f"{meta['ticker']}_{meta['fiscal_year']}_{meta['filing_type'].replace('-', '')}"

        upsert_filing(
            conn,
            doc_id,
            meta["company"],
            meta["ticker"],
            meta["cik"],
            meta["filing_type"],
            meta["fiscal_year"],
            meta=None,
        )
        qdrant = QdrantClient(url=QDRANT_URL)
        chunk_count = ingest_sections(conn, qdrant, doc_id, meta["ticker"], meta["fiscal_year"], sections)

        _update_upload_row(
            conn,
            document_id,
            status="ready",
            doc_id=doc_id,
            company=meta["company"],
            ticker=meta["ticker"],
            fiscal_year=meta["fiscal_year"],
            filing_type=meta["filing_type"],
            sections_found=len(sections),
            chunks_indexed=chunk_count,
        )
    except Exception as e:
        _update_upload_row(conn, document_id, status="error", error_message=f"Eroare interna: {e}")
    finally:
        conn.close()


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile, background_tasks: BackgroundTasks):
    document_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{document_id}.html")
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    conn = _db_conn()
    try:
        _insert_upload_row(conn, document_id, file.filename or "unknown.html")
    finally:
        conn.close()

    background_tasks.add_task(process_uploaded_document, document_id, file_path)
    return {"document_id": document_id, "status": "processing"}


@router.get("/documents/{document_id}/status", response_model=UploadStatusResponse)
def get_upload_status(document_id: str):
    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT document_id, status, original_filename, company, ticker,
                       fiscal_year, filing_type, sections_found, chunks_indexed, error_message
                FROM document_uploads WHERE document_id = %s
                """,
                (document_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="document_id necunoscut")

    keys = [
        "document_id", "status", "original_filename", "company", "ticker",
        "fiscal_year", "filing_type", "sections_found", "chunks_indexed", "error_message",
    ]
    result = dict(zip(keys, row))
    result["document_id"] = str(result["document_id"])
    return result
