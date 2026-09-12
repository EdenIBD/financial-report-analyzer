"""Pipeline de ingestie reutilizabil: chunking -> contextual retrieval -> embed
-> upsert Postgres + Qdrant. Functii importabile, apelate atat din
scripts/run_ingestion.py (corpus fix, descarcat de pe EDGAR, metadata din CIK
lookup) cat si din src/api/documents.py (upload direct din frontend, metadata
auto-detectata din continut) — o singura implementare de procesare, diferă doar
sursa fisierului si modul de obtinere a metadatei (vezi
feature-document-upload.md: "nu duplici pipeline-ul").
"""

import time
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct


def call_with_retry(fn, *args, max_attempts=4, base_delay=2, **kwargs):
    """La un volum mare de apeluri API, erori tranzitorii (503, network) sunt
    inevitabile — fara retry, un singur blip pierde munca de dinainte."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == max_attempts:
                raise
            wait = base_delay * (2 ** (attempt - 1))
            print(f"  [retry {attempt}/{max_attempts}] {fn.__name__} a esuat ({e}); reincerc in {wait}s")
            time.sleep(wait)


def upsert_filing(conn, doc_id, company, ticker, cik, filing_type, fiscal_year, meta=None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO filings (doc_id, company, ticker, cik, filing_type, fiscal_year,
                                  filing_date, accession_number, source_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO UPDATE SET
                filing_date = EXCLUDED.filing_date,
                accession_number = EXCLUDED.accession_number,
                source_url = EXCLUDED.source_url
            """,
            (
                doc_id,
                company,
                ticker,
                cik,
                filing_type,
                int(fiscal_year),
                meta["filing_date"] if meta else None,
                meta["accession_number"] if meta else None,
                meta["source_url"] if meta else None,
            ),
        )
    conn.commit()


def upsert_chunk(conn, chunk_id, doc_id, section, chunk_index, text, token_count) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, section, chunk_index, text, token_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE SET text = EXCLUDED.text, token_count = EXCLUDED.token_count
            """,
            (chunk_id, doc_id, section, chunk_index, text, token_count),
        )
    conn.commit()


def ingest_sections(
    conn,
    qdrant: QdrantClient,
    doc_id: str,
    ticker: str,
    fiscal_year: int,
    sections: dict[str, str],
) -> int:
    """Chunking + contextual retrieval + embedding + indexare pentru sectiunile
    (deja canonice, vezi src/ingestion/sections.py) ale unui filing. Presupune
    ca filings a fost deja upsertat pentru doc_id (upsert_filing mai sus).
    Returneaza numarul de chunk-uri indexate."""
    from src.ingestion.chunk import chunk_section
    from src.ingestion.contextual import add_context
    from src.ingestion.tokenizer import count_tokens
    from src.retrieval.embed import embed_document

    chunk_count = 0
    for section, text in sections.items():
        for chunk_index, chunk_text in enumerate(chunk_section(text)):
            contextualized = call_with_retry(add_context, chunk_text, doc_id, section)
            chunk_id = f"{doc_id}_{section}_{chunk_index}"
            token_count = count_tokens(contextualized)

            upsert_chunk(conn, chunk_id, doc_id, section, chunk_index, contextualized, token_count)

            vector = call_with_retry(embed_document, contextualized)
            # upsert per-chunk, nu batch la finalul fisierului: daca pica la jumatatea
            # unui fisier mare, vectorii deja calculati raman salvati, nu se pierd.
            qdrant.upsert(
                collection_name="financial_reports",
                points=[
                    PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)),
                        vector=vector,
                        payload={
                            "chunk_id": chunk_id,
                            "doc_id": doc_id,
                            "text": contextualized,
                            "company": ticker,
                            "fiscal_year": int(fiscal_year),
                            "section": section,
                        },
                    )
                ],
            )
            chunk_count += 1
    return chunk_count
