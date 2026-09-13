"""Remediere targetata pentru bug-ul documentat in
wiki/pages/failure-patterns/contextual-retrieval-wrong-company.md: propozitia
de context (contextual retrieval) numeste compania gresita sau contine
meta-comentariu ("Iata doua variante...") pe ~28% din corpus.

Nu re-ingereaza filing-uri intregi (ar re-contextualiza si chunk-uri deja
corecte, de ~3x mai scump/lent). In loc, pentru fiecare (doc_id, section) cu
chunk-uri afectate: re-parseaza HTML-ul brut din data/raw/, re-chunk-uieste
(determinist, acelasi text -> aceiasi chunk-uri la aceiasi indici), si repara
DOAR chunk-urile identificate ca afectate — restul sectiunii ramane neatinsa.

Necesita Postgres si Qdrant pornite. Ruleaza cu:
    python -c "from scripts.fix_contextual_sentences import main; main()"
"""

import os
import re
import time

import psycopg2
from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from src.ingestion.chunk import chunk_section
from src.ingestion.contextual import add_context
from src.ingestion.parse import parse_filing
from src.ingestion.pipeline import RAW_DIR, call_with_retry
from src.ingestion.tokenizer import count_tokens
from src.retrieval.embed import embed_document

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# Aceeasi logica de detectie folosita si la masurarea initiala a amplorii
# (wiki/pages/failure-patterns/contextual-retrieval-wrong-company.md) — trebuie
# sa ramana identica, altfel numerele raportate acolo si ce repara scriptul
# ar diverge silentios.
WRONG_COMPANY_NAMES = {
    "AAPL": ["Microsoft", "Alphabet"],
    "MSFT": ["Apple", "Alphabet"],
    "GOOGL": ["Apple", "Microsoft"],
    "NVDA": ["Apple", "Microsoft", "Alphabet"],
}
META_MARKERS = ["iată", "iata", "variantă", "varianta", "here are", "here's two"]


def situating_sentence(text: str) -> str:
    return text.split("\n\n", 1)[0]


def is_affected(text: str, ticker: str) -> bool:
    sentence = situating_sentence(text).lower()
    if any(marker in sentence for marker in META_MARKERS):
        return True
    return any(wrong.lower() in sentence for wrong in WRONG_COMPANY_NAMES.get(ticker, []))


def raw_html_path(doc_id: str) -> str:
    # make_doc_id() adauga sufixul de filing type (ex: "NVDA_2026_10K"), dar
    # download_filing() salveaza fisierul brut ca "{ticker}_{fiscal_year}.html",
    # fara sufix — corpusul de baza (run_ingestion.py) nu are sufix deloc.
    base = re.sub(r"_(10K|10Q)$", "", doc_id)
    return os.path.join(RAW_DIR, f"{base}.html")


def fetch_affected_chunks(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.chunk_id, c.doc_id, c.section, c.chunk_index, c.text,
                   f.ticker, f.filing_type, f.fiscal_year
            FROM chunks c JOIN filings f ON c.doc_id = f.doc_id
            """
        )
        rows = cur.fetchall()
    return [r for r in rows if is_affected(r[4], r[5])]


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    qdrant = QdrantClient(url=QDRANT_URL)

    affected = fetch_affected_chunks(conn)
    print(f"{len(affected)} chunk-uri afectate de reparat")

    # Grupate pe (doc_id, section) ca sa parsam/chunk-uim fiecare sectiune o
    # singura data, nu o data per chunk afectat din ea.
    by_doc_section: dict[tuple[str, str], list] = {}
    for row in affected:
        by_doc_section.setdefault((row[1], row[2]), []).append(row)

    parsed_cache: dict[str, dict[str, str]] = {}
    fixed = 0
    total_cost = 0.0
    start = time.time()

    for (doc_id, section), rows in by_doc_section.items():
        if doc_id not in parsed_cache:
            path = raw_html_path(doc_id)
            if not os.path.exists(path):
                print(f"  LIPSA fisier brut pentru {doc_id} ({path}) — sar peste {len(rows)} chunk-uri")
                continue
            with open(path, encoding="utf-8", errors="ignore") as f:
                html = f.read()
            filing_type = rows[0][6]
            parsed_cache[doc_id] = parse_filing(html, filing_type=filing_type)
        sections = parsed_cache[doc_id]
        if section not in sections:
            print(f"  Sectiunea {section} nu mai apare la re-parsare pentru {doc_id} — sar peste")
            continue

        raw_chunks = chunk_section(sections[section])
        ticker = rows[0][5]
        fiscal_year = rows[0][7]

        for chunk_id, _doc_id, _section, chunk_index, _old_text, _ticker, _ft, _fy in rows:
            if chunk_index >= len(raw_chunks):
                print(f"  {chunk_id}: index {chunk_index} nu mai exista dupa re-chunking — sar peste")
                continue
            raw_text = raw_chunks[chunk_index]
            contextualized, cost = call_with_retry(add_context, raw_text, doc_id, section)
            total_cost += cost
            token_count = count_tokens(contextualized)

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chunks SET text = %s, token_count = %s WHERE chunk_id = %s",
                    (contextualized, token_count, chunk_id),
                )
            conn.commit()

            vector = call_with_retry(embed_document, contextualized)
            qdrant.upsert(
                collection_name="financial_reports",
                points=[
                    PointStruct(
                        id=str(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL, chunk_id)),
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
            fixed += 1
            if fixed % 25 == 0:
                elapsed = time.time() - start
                print(f"  {fixed}/{len(affected)} reparate ({elapsed:.0f}s, ${total_cost:.4f})")

    elapsed = time.time() - start
    print(f"Gata: {fixed}/{len(affected)} chunk-uri reparate in {elapsed:.0f}s, cost total ${total_cost:.4f}")

    remaining = fetch_affected_chunks(conn)
    print(f"Chunk-uri inca afectate dupa remediere: {len(remaining)}")
    conn.close()


if __name__ == "__main__":
    main()
