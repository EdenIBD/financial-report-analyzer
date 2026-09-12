"""Migrare unica: remapeaza chunks.section (Postgres) si payload.section (Qdrant)
de la numarul brut de Item (ex: "Item7") la categoria canonica (ex: "mdna"), pentru
corpusul deja ingerat (8250 chunks, toate 10-K). Vezi src/ingestion/sections.py.

Nu modifica chunk_id — chunk_id ramane forma istorica ("AAPL_2023_Item7_3"),
folosita deja in citari generate si in query_logs/eval_set; doar campul folosit
pentru filtrare la retrieval (section) e remapat. Idempotenta: dupa prima rulare,
nu mai gaseste randuri cu valorile vechi si nu face nimic.
"""

import os

import psycopg2
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

load_dotenv()

from src.ingestion.sections import CANONICAL_SECTIONS

OLD_TO_CANONICAL = CANONICAL_SECTIONS["10-K"]  # corpusul existent e 100% 10-K


def migrate_postgres(conn) -> None:
    with conn.cursor() as cur:
        for old, new in OLD_TO_CANONICAL.items():
            cur.execute("UPDATE chunks SET section = %s WHERE section = %s", (new, old))
            print(f"  Postgres: {old} -> {new} ({cur.rowcount} randuri)")
    conn.commit()


def migrate_qdrant(client: QdrantClient) -> None:
    for old, new in OLD_TO_CANONICAL.items():
        result = client.set_payload(
            collection_name="financial_reports",
            payload={"section": new},
            points=Filter(must=[FieldCondition(key="section", match=MatchValue(value=old))]),
        )
        print(f"  Qdrant: {old} -> {new} ({result.status})")


def verify(conn, client: QdrantClient) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT section FROM chunks ORDER BY section")
        pg_sections = {row[0] for row in cur.fetchall()}
    leftover = pg_sections & set(OLD_TO_CANONICAL)
    assert not leftover, f"Postgres inca are sectiuni vechi: {leftover}"
    print(f"  Postgres OK, sectiuni distincte ramase: {sorted(pg_sections)}")

    for old in OLD_TO_CANONICAL:
        count = client.count(
            collection_name="financial_reports",
            count_filter=Filter(must=[FieldCondition(key="section", match=MatchValue(value=old))]),
        ).count
        assert count == 0, f"Qdrant inca are {count} puncte cu section={old}"
    print("  Qdrant OK, nicio sectiune veche ramasa")


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    qdrant = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))

    print("Migrare Postgres...")
    migrate_postgres(conn)
    print("Migrare Qdrant...")
    migrate_qdrant(qdrant)
    print("Verificare...")
    verify(conn, qdrant)

    conn.close()
    print("Migrare completa.")


if __name__ == "__main__":
    main()
