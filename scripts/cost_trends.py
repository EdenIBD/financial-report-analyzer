"""Agregare simpla peste query_logs: cost_usd x classified_persona x classified_query_type.
Scrie observatiile in wiki/pages/cost-trends.md. Fara logica noua de tracking —
doar citeste ce e deja in query_logs.

Nota: sectiunea 7 din spec cere si corelatie pe retry_count, dar retry_count nu e
o coloana persistata in query_logs (schema.sql nu o are, si sectiunea 7 interzice
explicit adaugarea de coloane noi) — nu poate fi calculata din datele existente.
"""

import os
from collections import defaultdict

import psycopg2
from dotenv import load_dotenv

load_dotenv()

WIKI_PAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "wiki", "pages", "cost-trends.md")


def fetch_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT classified_persona, classified_query_type, cost_usd, status,
                   coalesce(array_length(ingested_entities, 1), 0) > 0
            FROM query_logs
            WHERE cost_usd IS NOT NULL
            """
        )
        return cur.fetchall()


def avg(values):
    return sum(values) / len(values) if values else 0.0


def aggregate(rows):
    by_query_type = defaultdict(list)
    by_persona = defaultdict(list)
    by_status = defaultdict(list)
    by_ingestion = defaultdict(list)
    for persona, query_type, cost, status, had_ingestion in rows:
        if query_type:
            by_query_type[query_type].append(cost)
        if persona:
            by_persona[persona].append(cost)
        if status:
            by_status[status].append(cost)
        by_ingestion["cu ingestie live" if had_ingestion else "fara ingestie"].append(cost)
    return by_query_type, by_persona, by_status, by_ingestion


def render_table(header: list[str], rows: list[list]) -> list[str]:
    lines = [f"| {' | '.join(header)} |", f"|{'---|' * len(header)}"]
    for row in rows:
        lines.append(f"| {' | '.join(str(c) for c in row)} |")
    return lines


def render_query_type_insight(by_query_type: dict) -> str:
    if "factual" in by_query_type and "comparison" in by_query_type:
        factual_avg = avg(by_query_type["factual"])
        comparison_avg = avg(by_query_type["comparison"])
        if factual_avg > 0:
            ratio = comparison_avg / factual_avg
            return (
                f"Query-urile de comparatie costa de ~{ratio:.1f}x fata de cele factuale "
                f"(${comparison_avg:.6f} vs ${factual_avg:.6f} in medie)."
            )
    return "Insuficiente date pentru comparatie factual vs. comparison (necesita ambele tipuri logate)."


def render_ingestion_insight(by_ingestion: dict) -> str:
    with_cost = by_ingestion.get("cu ingestie live", [])
    without_cost = by_ingestion.get("fara ingestie", [])
    if not with_cost:
        return (
            "Niciun query logat nu a declansat inca ingestie live, deci nu exista "
            "inca o comparatie reala cu/fara. Coloana `ingested_entities` exista si "
            "se populeaza, dar ramane goala pana ruleaza primul astfel de query."
        )
    if not without_cost or avg(without_cost) == 0:
        return f"Query-uri cu ingestie live: {len(with_cost)}, cost mediu ${avg(with_cost):.6f}."
    ratio = avg(with_cost) / avg(without_cost)
    return (
        f"Un query care declanseaza ingestie live costa de ~{ratio:.0f}x un query obisnuit "
        f"(${avg(with_cost):.6f} vs ${avg(without_cost):.6f} in medie) — ingestia face un "
        "apel LLM de contextual retrieval per chunk, sute per filing."
    )


def render_markdown(by_query_type, by_persona, by_status, by_ingestion, total_rows: int) -> str:
    lines = ["# Cost trends", "", f"Generat automat de `scripts/cost_trends.py` din `query_logs` ({total_rows} query-uri cu cost logat).", ""]

    lines.append("## Cost mediu per query_type")
    lines.append("")
    lines += render_table(
        ["query_type", "n", "cost mediu (USD)"],
        [[qt, len(costs), f"{avg(costs):.6f}"] for qt, costs in sorted(by_query_type.items())],
    )
    lines.append("")
    lines.append(f"**Observatie:** {render_query_type_insight(by_query_type)}")
    lines.append("")

    lines.append("## Cost mediu per persona")
    lines.append("")
    lines += render_table(
        ["persona", "n", "cost mediu (USD)"],
        [[p, len(costs), f"{avg(costs):.6f}"] for p, costs in sorted(by_persona.items())],
    )
    lines.append("")

    lines.append("## Cost mediu per status")
    lines.append("")
    lines += render_table(
        ["status", "n", "cost mediu (USD)"],
        [[s, len(costs), f"{avg(costs):.6f}"] for s, costs in sorted(by_status.items())],
    )
    lines.append("")

    lines.append("## Cost mediu cu vs. fara ingestie live")
    lines.append("")
    lines += render_table(
        ["tip query", "n", "cost mediu (USD)"],
        [[k, len(costs), f"{avg(costs):.6f}"] for k, costs in sorted(by_ingestion.items())],
    )
    lines.append("")
    lines.append(f"**Observatie:** {render_ingestion_insight(by_ingestion)}")
    lines.append("")

    lines.append("## Ce nu poate fi calculat din query_logs")
    lines.append("")
    lines.append(
        "Sectiunea 7 din spec cere si corelatie pe `retry_count`, dar acesta nu e o "
        "coloana persistata in `query_logs` (schema.sql nu o include, iar sectiunea 7 "
        "interzice explicit adaugarea de coloane noi). Nu poate fi calculat din datele "
        "existente fara o sursa suplimentara (ex: extras din trace-urile LangSmith, unde "
        "retry_count exista in starea fiecarui nod)."
    )
    lines.append("")

    return "\n".join(lines)


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    rows = fetch_rows(conn)
    by_query_type, by_persona, by_status, by_ingestion = aggregate(rows)
    markdown = render_markdown(by_query_type, by_persona, by_status, by_ingestion, len(rows))

    os.makedirs(os.path.dirname(WIKI_PAGE_PATH), exist_ok=True)
    with open(WIKI_PAGE_PATH, "w") as f:
        f.write(markdown)

    print(f"Scris {WIKI_PAGE_PATH} ({len(rows)} query-uri agregate)")
    conn.close()


if __name__ == "__main__":
    main()
