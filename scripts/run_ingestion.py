"""Ruleaza pipeline-ul de ingestie pe fisierele din data/raw/:
parse (sectiuni) -> chunk -> contextual retrieval -> embed -> Postgres + Qdrant.

Necesita Postgres si Qdrant pornite si schema.sql/qdrant_setup.py deja rulate.
"""

import os
import time

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient

from src.ingestion.parse import parse_filing
from src.ingestion.pipeline import ingest_sections, upsert_filing

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
        upsert_filing(conn, doc_id, company, ticker, cik, "10-K", fiscal_year, meta)

        with open(os.path.join(RAW_DIR, filename), encoding="utf-8") as f:
            html = f.read()
        sections = parse_filing(html, filing_type="10-K")

        chunk_count = ingest_sections(conn, qdrant, doc_id, ticker, fiscal_year, sections)
        print(f"  {chunk_count} chunk-uri indexate din {len(sections)} sectiuni")

    conn.close()


if __name__ == "__main__":
    main()
