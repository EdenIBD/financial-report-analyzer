import os

import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/financial_report_analyzer"
)  # TODO: confirma connection string

def log_query_to_postgres(
    raw_query: str,
    classification,
    retrieved_chunk_ids: list[str],
    latency_ms: int,
    final_answer: str | None,
    status: str,
    langsmith_trace_id: str | None,
    cost_usd: float | None = None,
) -> None:
    persona = classification.persona.value if classification else None
    query_type = classification.query_type.value if classification else None

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_logs (
                    raw_query, classified_persona, classified_query_type,
                    retrieved_chunk_ids, langsmith_trace_id, latency_ms,
                    final_answer, status, cost_usd
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    raw_query,
                    persona,
                    query_type,
                    retrieved_chunk_ids,
                    langsmith_trace_id,
                    latency_ms,
                    final_answer,
                    status,
                    cost_usd,
                ),
            )
        conn.commit()
    finally:
        conn.close()
