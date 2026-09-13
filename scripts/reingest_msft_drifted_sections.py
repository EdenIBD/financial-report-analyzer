"""Re-ingestie curata pentru sectiunile MSFT afectate de drift-ul de parsare
documentat in wiki/pages/failure-patterns/msft-parse-drift-during-remediation.md.

Pentru fiecare (doc_id, sectiune) din DRIFTED_SECTIONS: sterge complet
chunk-urile existente (Postgres + Qdrant) pentru acea pereche, apoi re-parseaza
-> re-chunk-uieste -> re-contextualizeaza (cu prompt-ul deja reparat) ->
re-embedeaza -> insereaza de la zero, cu indici 0..N-1 consistenti intre ei.
Nu amesteca segmentari diferite ca fix_contextual_sentences.py (care doar
inlocuia chunk-uri individuale pe indici posibil nealiniati).

Necesita Postgres si Qdrant pornite. Ruleaza cu:
    python -c "from scripts.reingest_msft_drifted_sections import main; main()"
"""

import os
import time

import psycopg2
from dotenv import load_dotenv

load_dotenv()

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList

from src.ingestion.chunk import chunk_section
from src.ingestion.parse import parse_filing
from src.ingestion.pipeline import RAW_DIR, ingest_sections

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# Exact perechile (doc_id, sectiune) identificate cu COUNT_DRIFT in
# msft-parse-drift-during-remediation.md — nu toate sectiunile MSFT, doar
# cele unde re-parsarea de azi difera de ce e stocat.
DRIFTED_SECTIONS = {
    "MSFT_2021": ["financial_statements", "risk_factors"],
    "MSFT_2023": ["financial_statements", "risk_factors"],
    "MSFT_2024": ["controls_procedures", "financial_statements", "mdna", "risk_factors"],
    "MSFT_2025": ["controls_procedures", "financial_statements", "mdna", "risk_factors"],
    "MSFT_2026": ["controls_procedures", "financial_statements", "mdna", "risk_factors"],
}


def delete_stale_old_style_chunks(conn, qdrant: QdrantClient, doc_id: str, section: str) -> int:
    """Sterge DOAR chunk-urile ramase din segmentarea veche (chunk_id nu se
    potriveste formatului nou "{doc_id}_{section}_{index}") pentru aceasta
    pereche — apelat DUPA ce noile chunk-uri sunt deja inserate complet, nu
    inainte. In ordinea asta, o intrerupere la mijloc lasa cel mult chunk-uri
    vechi redundante (retrieval-ul filtreaza pe coloana 'section', nu pe
    chunk_id, deci coexistenta temporara nu strica nimic), niciodata un gol
    real de continut — spre deosebire de sterge-apoi-insereaza, care poate
    lasa sectiunea fara acele chunk-uri daca insertul e intrerupt la mijloc
    (exact ce a patit MSFT_2021/risk_factors data trecuta)."""
    pattern = f"^{doc_id}_{section}_[0-9]+$"
    with conn.cursor() as cur:
        cur.execute(
            "SELECT chunk_id FROM chunks WHERE doc_id = %s AND section = %s AND chunk_id !~ %s",
            (doc_id, section, pattern),
        )
        stale_ids = [row[0] for row in cur.fetchall()]
        if not stale_ids:
            return 0
        cur.execute("DELETE FROM chunks WHERE chunk_id = ANY(%s)", (stale_ids,))
    conn.commit()
    # Sterge DOAR punctele Qdrant ale chunk_id-urilor vechi identificate mai sus
    # (id-uri calculate determinist din chunk_id) — un filtru pe doc_id+section
    # ar sterge si punctele proaspat inserate, care au acelasi payload.section.
    stale_point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, cid)) for cid in stale_ids]
    qdrant.delete(collection_name="financial_reports", points_selector=PointIdsList(points=stale_point_ids))
    return len(stale_ids)


def already_done(conn, doc_id: str, section: str, target_count: int) -> bool:
    """True daca sectiunea are deja exact target_count chunk-uri in noul
    format — evita re-rularea (costisitoare, un apel LLM+embed per chunk) a
    unei sectiuni deja terminate cu succes intr-o rulare anterioara, oprita
    de o intrerupere ulterioara pe alta sectiune. Fara asta, fiecare repornire
    reface de la zero tot ce era deja corect, in ordine, inainte sa ajunga la
    treaba noua — exact ce s-a intamplat la a patra repornire a acestui job."""
    pattern = f"^{doc_id}_{section}_[0-9]+$"
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM chunks WHERE doc_id = %s AND section = %s AND chunk_id ~ %s",
            (doc_id, section, pattern),
        )
        return cur.fetchone()[0] == target_count


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    qdrant = QdrantClient(url=QDRANT_URL)

    with conn.cursor() as cur:
        cur.execute("SELECT doc_id, ticker, filing_type, fiscal_year FROM filings WHERE ticker = 'MSFT'")
        filings_by_doc = {row[0]: row[1:] for row in cur.fetchall()}

    total_deleted = 0
    total_reindexed = 0
    total_cost = 0.0
    start = time.time()

    for doc_id, sections_to_fix in DRIFTED_SECTIONS.items():
        ticker, filing_type, fiscal_year = filings_by_doc[doc_id]
        path = os.path.join(RAW_DIR, f"{doc_id}.html")
        with open(path, encoding="utf-8", errors="ignore") as f:
            html = f.read()
        fresh_sections = parse_filing(html, filing_type=filing_type)

        for section in sections_to_fix:
            target_count = len(chunk_section(fresh_sections[section]))
            if already_done(conn, doc_id, section, target_count):
                print(f"--- {doc_id}/{section}: deja complet ({target_count} chunk-uri) — sar peste ---")
                continue

            print(f"--- {doc_id}/{section}: re-ingerez (insert-first, safe la intrerupere) ---")
            count, cost = ingest_sections(
                conn, qdrant, doc_id, ticker, fiscal_year, {section: fresh_sections[section]}
            )
            total_reindexed += count

            # Abia dupa ce noile chunk-uri sunt complet inserate, sterge orice
            # chunk_id vechi ramas pentru aceasta pereche (segmentarea veche,
            # posibil dezaliniata) — nu inainte.
            deleted = delete_stale_old_style_chunks(conn, qdrant, doc_id, section)
            total_deleted += deleted
            total_cost += cost
            elapsed = time.time() - start
            print(f"    {count} chunk-uri noi indexate (${cost:.4f}), total {elapsed:.0f}s")

    print(
        f"Gata: {total_deleted} chunk-uri vechi sterse, {total_reindexed} noi indexate, "
        f"cost total ${total_cost:.4f}, {time.time() - start:.0f}s"
    )
    conn.close()


if __name__ == "__main__":
    main()
