"""Pipeline de ingestie reutilizabil: chunking -> contextual retrieval -> embed
-> upsert Postgres + Qdrant. Functii importabile, apelate atat din
scripts/run_ingestion.py (corpus fix, descarcat de pe EDGAR, metadata din CIK
lookup) cat si din src/api/documents.py (upload direct din frontend, metadata
auto-detectata din continut) — o singura implementare de procesare, diferă doar
sursa fisierului si modul de obtinere a metadatei (vezi
feature-document-upload.md: "nu duplici pipeline-ul").
"""

import json
import os
import time
import uuid

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")

EDGAR_HEADERS = {
    "User-Agent": (
        f"{os.environ.get('EDGAR_USER_AGENT_NAME', 'Placeholder Name')} "
        f"{os.environ.get('EDGAR_USER_AGENT_EMAIL', 'placeholder@example.com')}"
    )
}
RATE_LIMIT_SECONDS = 0.2
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_TICKERS_CACHE = os.path.join(DATA_DIR, "cache", "company_tickers.json")


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
) -> tuple[int, float]:
    """Chunking + contextual retrieval + embedding + indexare pentru sectiunile
    (deja canonice, vezi src/ingestion/sections.py) ale unui filing. Presupune
    ca filings a fost deja upsertat pentru doc_id (upsert_filing mai sus).
    Returneaza (numar de chunk-uri indexate, cost real acumulat).

    Costul acoperă doar apelurile de contextual retrieval (usage_metadata real).
    Embedding-ul ramane necontabilizat — embed_document nu expune usage in
    raspuns, limitare deja documentata a proiectului, nu o omisiune noua."""
    from src.ingestion.chunk import chunk_section
    from src.ingestion.contextual import add_context
    from src.ingestion.tokenizer import count_tokens
    from src.retrieval.embed import embed_document

    chunk_count = 0
    cost_usd = 0.0
    for section, text in sections.items():
        for chunk_index, chunk_text in enumerate(chunk_section(text)):
            contextualized, chunk_cost = call_with_retry(add_context, chunk_text, doc_id, section)
            cost_usd += chunk_cost
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
    return chunk_count, cost_usd


def make_doc_id(ticker: str, fiscal_year: int | str, filing_type: str) -> str:
    """Sufix cu tipul de filing: evita coliziunea intre un 10-K si un 10-Q ale
    aceleiasi companii/an, si cu doc_id-urile fixe din corpusul initial."""
    return f"{ticker}_{fiscal_year}_{filing_type.replace('-', '')}"


def _company_index() -> list[dict]:
    """Maparea publica SEC ticker/nume -> CIK. Cache local dupa prima descarcare:
    e un fisier de ~1MB, nu are sens re-descarcat la fiecare query."""
    if os.path.exists(COMPANY_TICKERS_CACHE):
        with open(COMPANY_TICKERS_CACHE, encoding="utf-8") as f:
            return json.load(f)

    response = requests.get(COMPANY_TICKERS_URL, headers=EDGAR_HEADERS, timeout=30)
    time.sleep(RATE_LIMIT_SECONDS)
    response.raise_for_status()
    companies = list(response.json().values())

    os.makedirs(os.path.dirname(COMPANY_TICKERS_CACHE), exist_ok=True)
    with open(COMPANY_TICKERS_CACHE, "w", encoding="utf-8") as f:
        json.dump(companies, f)
    return companies


def resolve_company(name_or_ticker: str) -> dict | None:
    """{ticker, cik, title} de pe EDGAR, sau None daca nu exista acolo."""
    needle = name_or_ticker.strip().lower()
    if not needle:
        return None

    exact_title = None
    for entry in _company_index():
        ticker = entry["ticker"]
        title = entry["title"]
        if ticker.lower() == needle:
            return {"ticker": ticker, "cik": f"{entry['cik_str']:010d}", "title": title}
        if exact_title is None and title.lower() == needle:
            exact_title = {"ticker": ticker, "cik": f"{entry['cik_str']:010d}", "title": title}
    if exact_title:
        return exact_title

    # "Nvidia" pentru "NVIDIA CORP": prefix pe titlu, dupa ce match-urile exacte
    # au esuat, ca sa nu returnam o companie gresita cand exista una exacta.
    # Sub 3 caractere nu facem prefix match: numele vine dintr-un LLM, iar un
    # "A" ar rezolva la prima companie care incepe cu A si ar declansa o
    # ingestie de minute pe compania gresita.
    if len(needle) < 3:
        return None
    prefixed = [
        entry
        for entry in _company_index()
        if entry["title"].lower().startswith(needle)
        and not entry["title"][len(needle) : len(needle) + 1].isalpha()
    ]
    if not prefixed:
        return None
    # cel mai scurt titlu = cel mai aproape de numele simplu cautat
    # ("Apple Inc." inaintea lui "Apple Hospitality REIT" pentru "apple").
    best = min(prefixed, key=lambda e: len(e["title"]))
    return {"ticker": best["ticker"], "cik": f"{best['cik_str']:010d}", "title": best["title"]}


def resolve_ticker(company_name_or_ticker: str) -> str | None:
    """Nume companie sau ticker -> CIK. None daca nu exista pe EDGAR."""
    company = resolve_company(company_name_or_ticker)
    return company["cik"] if company else None


def download_filing(cik: str, filing_type: str = "10-K", count: int = 1, ticker: str | None = None) -> list[str]:
    """Descarca filing-uri, returneaza lista de path-uri HTML din data/raw/."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(url, headers=EDGAR_HEADERS, timeout=30)
    time.sleep(RATE_LIMIT_SECONDS)
    response.raise_for_status()

    recent = response.json()["filings"]["recent"]
    report_dates = recent.get("reportDate", [])
    indices = [i for i, form in enumerate(recent["form"]) if form == filing_type][:count]
    if not indices:
        # mesajele de eroare de aici ajung in interfata, deci sunt in engleza
        raise ValueError(f"no {filing_type} filings found on SEC EDGAR for CIK {cik}")

    os.makedirs(RAW_DIR, exist_ok=True)
    paths = []
    for i in indices:
        accession = recent["accessionNumber"][i].replace("-", "")
        report_date = report_dates[i] if i < len(report_dates) else ""
        fiscal_year = (report_date or recent["filingDate"][i])[:4]
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession}/{recent['primaryDocument'][i]}"
        )
        doc_response = requests.get(doc_url, headers=EDGAR_HEADERS, timeout=60)
        time.sleep(RATE_LIMIT_SECONDS)
        doc_response.raise_for_status()

        path = os.path.join(RAW_DIR, f"{ticker or cik}_{fiscal_year}.html")
        with open(path, "wb") as f:
            f.write(doc_response.content)
        paths.append(path)
    return paths


def ingest_filing(html_path: str, ticker: str, fiscal_year: int, filing_type: str) -> tuple[int, float]:
    """Pipeline complet pentru UN filing: parse -> chunk -> contextual -> embed
    -> Qdrant + Postgres. Returneaza (chunk-uri indexate, cost real).

    Spec-ul cere `-> int`, dar sectiunea 5 cere si costul acumulat inapoi; un
    tuplu evita un al doilea drum prin acelasi pipeline doar ca sa-l afli.
    """
    import psycopg2

    from src.ingestion.detect import detect_filing_metadata
    from src.ingestion.parse import parse_filing
    from src.ingestion.sections import validate_sections

    with open(html_path, encoding="utf-8", errors="ignore") as f:
        html = f.read()

    meta = detect_filing_metadata(html)  # doar pentru company/cik; restul vine de la apelant
    sections = parse_filing(html, filing_type=filing_type)
    validate_sections(sections)  # acelasi prag ca la upload — o singura definitie de "filing valid"

    doc_id = make_doc_id(ticker, fiscal_year, filing_type)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        upsert_filing(
            conn, doc_id, meta["company"], ticker, meta["cik"], filing_type, fiscal_year, meta=None
        )
        qdrant = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))
        return ingest_sections(conn, qdrant, doc_id, ticker, fiscal_year, sections)
    finally:
        conn.close()


def ingest_company(ticker: str, filing_type: str = "10-K", count: int = 1) -> dict:
    """resolve -> download -> ingest. Rezumat cu ce a reusit si ce nu."""
    from src.ingestion.detect import detect_filing_metadata

    summary = {
        "ticker": ticker,
        "filings_ingested": 0,
        "chunks_indexed": 0,
        "cost_usd": 0.0,
        "errors": [],
    }

    company = resolve_company(ticker)
    if company is None:
        summary["errors"].append(f"{ticker}: not found on SEC EDGAR")
        return summary

    paths = download_filing(company["cik"], filing_type, count, ticker=company["ticker"])
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                meta = detect_filing_metadata(f.read())
            chunks, cost = ingest_filing(
                path, company["ticker"], int(meta["fiscal_year"]), meta["filing_type"]
            )
            summary["filings_ingested"] += 1
            summary["chunks_indexed"] += chunks
            summary["cost_usd"] += cost
        except Exception as e:
            summary["errors"].append(f"{os.path.basename(path)}: {e}")
    return summary
