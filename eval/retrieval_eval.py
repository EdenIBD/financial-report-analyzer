"""Evaluare izolata de retrieval (fara agent/persona): genereaza intrebari sintetice
din chunk-uri deja indexate (o mostra, nu tot corpusul) si masoara Recall@8.

Foloseste sablonul din skill-ul evaluate-rag:
  Given a chunk of text, extract a specific, self-contained fact from it.
  Then write a question that is directly and unambiguously answered by that fact alone.
"""

import json
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient

from src.ingestion.contextual import llm_call
from src.retrieval.embed import embed_query

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
TOP_K = 8
SAMPLES_PER_SECTION = 2

QA_PROMPT_TEMPLATE = """Given a chunk of text, extract a specific, self-contained fact from it.
Then write a question that is directly and unambiguously answered
by that fact alone.

Return output in JSON format:
{{ "fact": "...", "question": "..." }}

Chunk: "{text_chunk}"
"""


def sample_chunks(conn, doc_id: str, per_section: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_id, section, text FROM (
                SELECT chunk_id, section, text,
                       row_number() OVER (PARTITION BY section ORDER BY chunk_index) AS rn
                FROM chunks WHERE doc_id = %s
            ) t
            WHERE rn <= %s
            """,
            (doc_id, per_section),
        )
        rows = cur.fetchall()
    return [{"chunk_id": r[0], "section": r[1], "text": r[2]} for r in rows]


def generate_question(chunk_text: str) -> dict | None:
    raw = llm_call(QA_PROMPT_TEMPLATE.format(text_chunk=chunk_text[:1500]))
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"  [WARN] raspuns neparsabil ca JSON: {raw[:200]!r}")
        return None


def recall_at_k(qdrant: QdrantClient, question: str, expected_chunk_id: str, k: int) -> bool:
    vector = embed_query(question)
    results = qdrant.query_points(collection_name="financial_reports", query=vector, limit=k)
    retrieved_ids = [p.payload["chunk_id"] for p in results.points]
    return expected_chunk_id in retrieved_ids


def main(doc_id: str = "AAPL_2023"):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    qdrant = QdrantClient(url=QDRANT_URL)

    chunks = sample_chunks(conn, doc_id, SAMPLES_PER_SECTION)
    print(f"Mostra: {len(chunks)} chunk-uri din {doc_id} (max {SAMPLES_PER_SECTION}/sectiune)")

    eval_rows = []
    for c in chunks:
        # c["text"] e chunk-ul contextualizat (add_context prepends "Acest fragment
        # provine din ..." inainte de continutul real, separat prin \n\n) — generam
        # intrebarea din continutul real, altfel LLM-ul extrage adesea un "fapt" din
        # propozitia de context (metadata despre document), nu din continutul financiar.
        real_content = c["text"].split("\n\n", 1)[-1]
        qa = generate_question(real_content)
        if qa is None or "question" not in qa:
            continue
        eval_rows.append({"chunk_id": c["chunk_id"], "section": c["section"], "question": qa["question"], "fact": qa.get("fact")})

    print(f"\n{len(eval_rows)} intrebari sintetice generate\n")

    hits = 0
    for row in eval_rows:
        found = recall_at_k(qdrant, row["question"], row["chunk_id"], TOP_K)
        hits += found
        status = "HIT " if found else "MISS"
        print(f"[{status}] ({row['section']}) {row['question']}")

    recall = hits / len(eval_rows) if eval_rows else 0.0
    print(f"\nRecall@{TOP_K}: {hits}/{len(eval_rows)} = {recall:.2%}")

    with open(os.path.join(os.path.dirname(__file__), f"retrieval_eval_{doc_id}.json"), "w") as f:
        json.dump(eval_rows, f, indent=2)

    conn.close()


if __name__ == "__main__":
    main()
