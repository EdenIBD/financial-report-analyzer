"""Ruleaza pipeline-ul de ingestie pe fisierele din data/raw/:
parse (sectiuni) -> chunk -> contextual retrieval -> embed -> Postgres + Qdrant.

Necesita Postgres si Qdrant pornite si schema.sql/qdrant_setup.py deja rulate.
"""

import os
import time
import uuid

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from src.ingestion.parse import parse_filing
from src.ingestion.chunk import chunk_section
from src.ingestion.contextual import add_context
from src.ingestion.tokenizer import count_tokens
from src.retrieval.embed import embed_document

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

COMPANIES = {
    "AAPL": ("0000320193", "Apple Inc."),
    "MSFT": ("0000789019", "Microsoft Corporation"),
    "GOOGL": ("0001652044", "Alphabet Inc."),
}

EDGAR_HEADERS = {
    "User-Agent": (
        f"{os.environ.get('EDGAR_USER_AGENT_NAME', 'Placeholder Name')} "
        f"{os.environ.get('EDGAR_USER_AGENT_EMAIL', 'placeholder@example.com')}"
    )
}
RATE_LIMIT_SECONDS = 0.2


def call_with_retry(fn, *args, max_attempts=4, base_delay=2, **kwargs):
    """La 16.500 apeluri API pe tot corpusul, erori tranzitorii (503, network)
    sunt inevitabile — fara retry, un singur blip pierde ora de lucru de dinainte."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == max_attempts:
                raise
            wait = base_delay * (2 ** (attempt - 1))
            print(f"  [retry {attempt}/{max_attempts}] {fn.__name__} a esuat ({e}); reincerc in {wait}s")
            time.sleep(wait)


def fetch_filing_metadata(cik: str, fiscal_year: str) -> dict | None:
    """Regaseste accession_number/filing_date/source_url pentru un 10-K dupa fiscal_year
    (aceleasi date pe care scripts/download_filings.py le-a vazut la descarcare,
    dar nu le-a persistat separat)."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(url, headers=EDGAR_HEADERS)
    time.sleep(RATE_LIMIT_SECONDS)
    if response.status_code != 200:
        print(f"Eroare: nu s-a putut accesa {url} (status {response.status_code})")
        return None

    recent = response.json()["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form != "10-K":
            continue
        report_date = recent.get("reportDate", [""])[i] if i < len(recent.get("reportDate", [])) else ""
        if report_date[:4] != str(fiscal_year):
            continue
        accession = recent["accessionNumber"][i]
        primary_doc = recent["primaryDocument"][i]
        accession_no_dashes = accession.replace("-", "")
        return {
            "accession_number": accession,
            "filing_date": recent["filingDate"][i],
            "source_url": (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession_no_dashes}/{primary_doc}"
            ),
        }
    return None


def upsert_filing(conn, doc_id, company, ticker, cik, fiscal_year, meta) -> None:
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
                "10-K",
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


def main(files: list[str] | None = None):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    qdrant = QdrantClient(url=QDRANT_URL)

    if files is None:
        files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".html"))
    for filename in files:
        ticker, fiscal_year = filename.replace(".html", "").split("_")
        if ticker not in COMPANIES:
            print(f"Sar peste {filename}: ticker necunoscut {ticker}")
            continue
        cik, company = COMPANIES[ticker]
        doc_id = f"{ticker}_{fiscal_year}"

        print(f"--- {doc_id} ---")
        meta = fetch_filing_metadata(cik, fiscal_year)
        upsert_filing(conn, doc_id, company, ticker, cik, fiscal_year, meta)

        with open(os.path.join(RAW_DIR, filename), encoding="utf-8") as f:
            html = f.read()
        sections = parse_filing(html)

        chunk_count = 0
        for section, text in sections.items():
            for chunk_index, chunk_text in enumerate(chunk_section(text)):
                contextualized = call_with_retry(add_context, chunk_text, doc_id, section)
                chunk_id = f"{doc_id}_{section}_{chunk_index}"
                token_count = count_tokens(contextualized)

                upsert_chunk(conn, chunk_id, doc_id, section, chunk_index, contextualized, token_count)

                vector = call_with_retry(embed_document, contextualized)
                # upsert per-chunk, nu batch la finalul fisierului: daca pica la jumatatea
                # unui fisier mare (Item8 are 100+ chunk-uri), vectorii deja calculati raman
                # salvati, nu se pierd odata cu crash-ul (la fel cum Postgres deja e per-chunk).
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

        print(f"  {chunk_count} chunk-uri indexate din {len(sections)} sectiuni")

    conn.close()


if __name__ == "__main__":
    main()
