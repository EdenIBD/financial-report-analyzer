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
import re
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


_CORP_SUFFIXES = {
    "inc", "corp", "corporation", "co", "company",
    "ltd", "holding", "holdings", "group", "plc", "llc",
}


def _normalize_company(name: str) -> str:
    """Companie liber-scrisa -> forma comparabila: fara punctuatie, fara
    sufixul corporativ. BUG REAL gasit testand ingestia dinamica (2026-09-13):
    un LLM extrage adesea "Tesla Inc" dintr-o intrebare, dar EDGAR listeaza
    "Tesla, Inc." — nici match exact, nici prefix (virgula rupe startswith),
    deci resolve_company intorcea None si intreaga companie era ignorata
    silentios, fara eroare vizibila. Normalizarea ambelor parti la "tesla"
    elimina asta, nu doar pentru Tesla."""
    # Spatiu, nu sterge: "Amazon.com Inc" fara asta ar deveni "amazoncom",
    # care nu mai matcheaza "AMAZON COM INC" de pe EDGAR ("amazon com").
    name = re.sub(r"[.,]", " ", name.lower())
    words = name.split()
    while words and words[-1] in _CORP_SUFFIXES:
        words.pop()
    return " ".join(words)


def resolve_company(name_or_ticker: str) -> dict | None:
    """{ticker, cik, title} de pe EDGAR, sau None daca nu exista acolo."""
    raw_needle = name_or_ticker.strip().lower()
    needle = _normalize_company(name_or_ticker)
    if not needle:
        return None

    exact_title = None
    for entry in _company_index():
        ticker = entry["ticker"]
        title = entry["title"]
        if ticker.lower() == raw_needle:
            return {"ticker": ticker, "cik": f"{entry['cik_str']:010d}", "title": title}
        if exact_title is None and _normalize_company(title) == needle:
            exact_title = {"ticker": ticker, "cik": f"{entry['cik_str']:010d}", "title": title}
    if exact_title:
        return exact_title

    # "Nvidia" pentru "NVIDIA CORP": prefix pe titlu (normalizat), dupa ce
    # match-urile exacte au esuat, ca sa nu returnam o companie gresita cand
    # exista una exacta. Sub 3 caractere nu facem prefix match: numele vine
    # dintr-un LLM, iar un "A" ar rezolva la prima companie care incepe cu A
    # si ar declansa o ingestie de minute pe compania gresita.
    if len(needle) < 3:
        return None
    prefixed = [
        entry
        for entry in _company_index()
        if _normalize_company(entry["title"]).startswith(needle)
        and not _normalize_company(entry["title"])[len(needle) : len(needle) + 1].isalpha()
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


def download_filing(cik: str, filing_type: str = "10-K", count: int = 1,
                    ticker: str | None = None, fiscal_year: int | None = None) -> list[str]:
    """Select the requested FY using XBRL, including older submissions shards.

    reportDate is a candidate filter only: NVIDIA's fiscal year need not equal
    the calendar year in reportDate. Never silently substitute the latest filing.
    """
    from src.ingestion.detect import detect_filing_metadata

    def fetch(url):
        response = requests.get(url, headers=EDGAR_HEADERS, timeout=60)
        time.sleep(RATE_LIMIT_SECONDS)
        response.raise_for_status()
        return response

    submissions = fetch(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    batches = [submissions["filings"]["recent"]]
    archives = iter(submissions["filings"].get("files", []))
    paths, seen = [], set()
    os.makedirs(RAW_DIR, exist_ok=True)
    while batches:
        batch = batches.pop()
        for i, form in enumerate(batch["form"]):
            if form != filing_type:
                continue
            accession = batch["accessionNumber"][i]
            if accession in seen:
                continue
            seen.add(accession)
            report_date = batch.get("reportDate", [""] * len(batch["form"]))[i]
            if fiscal_year is not None and report_date and abs(int(report_date[:4]) - fiscal_year) > 1:
                continue
            document = batch["primaryDocument"][i]
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"
            print(f"Downloading {ticker or cik}: {batch['filingDate'][i]} {url}")
            response = fetch(url)
            meta = detect_filing_metadata(response.text)
            if meta["filing_type"] != filing_type or int(meta["cik"] or 0) != int(cik):
                raise ValueError("SEC document metadata does not match the requested registrant/form")
            if fiscal_year is not None and meta["fiscal_year"] != fiscal_year:
                continue
            path = os.path.join(RAW_DIR, f"{ticker or cik}_{meta['fiscal_year']}_{accession}.html")
            with open(path, "wb") as f:
                f.write(response.content)
            metadata_dir = os.path.join(DATA_DIR, "cache", "filing_metadata")
            os.makedirs(metadata_dir, exist_ok=True)
            with open(os.path.join(metadata_dir, os.path.basename(path) + ".json"), "w") as f:
                json.dump({"filing_date": batch["filingDate"][i], "accession_number": accession,
                           "source_url": url}, f)
            paths.append(path)
            if len(paths) >= count:
                return paths
        if fiscal_year is None and paths:
            break
        archive = next(archives, None)
        if archive is not None:
            # SEC supplies these shard filenames; do not accept arbitrary URLs.
            name = archive["name"]
            if not re.fullmatch(r"CIK[0-9]+-submissions-[0-9]+\.json", name):
                raise ValueError("Unexpected SEC submissions shard name")
            batches.append(fetch(f"https://data.sec.gov/submissions/{name}").json())
    if not paths:
        year_label = f" for fiscal year {fiscal_year}" if fiscal_year is not None else ""
        raise ValueError(f"no verified {filing_type}{year_label} found on SEC EDGAR for CIK {cik}")
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

    meta = detect_filing_metadata(html)
    if int(meta["fiscal_year"]) != int(fiscal_year) or meta["filing_type"] != filing_type:
        raise ValueError("Filing fiscal year/form does not match the requested scope")
    sections = parse_filing(html, filing_type=filing_type)
    validate_sections(sections)  # acelasi prag ca la upload — o singura definitie de "filing valid"

    doc_id = make_doc_id(ticker, fiscal_year, filing_type)
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    metadata_path = os.path.join(DATA_DIR, "cache", "filing_metadata", os.path.basename(html_path) + ".json")
    source_meta = None
    if os.path.exists(metadata_path):
        with open(metadata_path) as f:
            source_meta = json.load(f)
    try:
        # Serialize ingestion of the same filing across API requests.
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(hashtext(%s))", (doc_id,))
        upsert_filing(
            conn, doc_id, meta["company"], ticker, meta["cik"], filing_type, fiscal_year, meta=source_meta
        )
        qdrant = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))
        with conn.cursor() as cur:
            cur.execute("UPDATE filings SET ingestion_status = 'processing' WHERE doc_id = %s", (doc_id,))
        conn.commit()
        result = ingest_sections(conn, qdrant, doc_id, ticker, fiscal_year, sections)
        with conn.cursor() as cur:
            cur.execute("UPDATE filings SET ingestion_status = 'ready' WHERE doc_id = %s", (doc_id,))
        conn.commit()
        return result
    finally:
        conn.close()


def ingest_company(ticker: str, filing_type: str = "10-K", count: int = 1, fiscal_year: int | None = None) -> dict:
    """resolve -> download -> ingest. Rezumat cu ce a reusit si ce nu."""
    from src.ingestion.detect import detect_filing_metadata

    summary = {
        "ticker": ticker,
        "filings_ingested": 0,
        "chunks_indexed": 0,
        "cost_usd": 0.0,
        "errors": [],
        "filings": [],  # {company, fiscal_year, filing_type, chunks} - pentru cardul de "found via dynamic ingestion"
    }

    company = resolve_company(ticker)
    if company is None:
        summary["errors"].append(f"{ticker}: not found on SEC EDGAR")
        return summary

    paths = download_filing(company["cik"], filing_type, count, ticker=company["ticker"], fiscal_year=fiscal_year)
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
            summary["filings"].append(
                {
                    "company": meta["company"],
                    "fiscal_year": int(meta["fiscal_year"]),
                    "filing_type": meta["filing_type"],
                    "chunks": chunks,
                }
            )
        except Exception as e:
            summary["errors"].append(f"{os.path.basename(path)}: {e}")
    return summary
