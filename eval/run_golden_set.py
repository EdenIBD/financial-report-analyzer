"""Ruleaza eval/golden_set.json prin handle_query() real si scrie rezultatele
in tabela eval_set. Calculeaza doar ce poate fi calculat onest din datele
disponibile:

- persona_classification_accuracy si query_type_classification_accuracy —
  golden_set.json are expected_persona/expected_query_type, deci acestea
  sunt comparabile direct cu ce clasifica agentul.

NU calculeaza recall_at_8/mrr (necesita expected_chunk_ids, care sunt null
in golden_set.json — nimeni nu a adnotat manual chunk-urile corecte) si nu
calculeaza faithfulness/judge_score (necesita un LLM judge, neimplementat
inca). Aceste coloane raman NULL in eval_set — nu se inventeaza valori.
"""

import json
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

from src.api.main import handle_query

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "golden_set.json")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "wiki", "pages", "golden-set-results.md")


def insert_eval_row(conn, question, actual_answer):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO eval_set (question, actual_answer)
            VALUES (%s, %s)
            """,
            (question, actual_answer),
        )
    conn.commit()


def main():
    with open(GOLDEN_SET_PATH) as f:
        golden_set = json.load(f)

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    results = []

    for item in golden_set:
        question = item["question"]
        result = handle_query(question)

        row = {
            "question": question,
            "expected_persona": item["expected_persona"],
            "actual_persona": result.get("persona"),
            "expected_query_type": item["expected_query_type"],
            "actual_query_type": result.get("query_type"),
            "status": result.get("status"),
            "cost_usd": result.get("cost_usd"),
            "latency_ms": result.get("latency_ms"),
            "num_chunks": len(result.get("retrieved_chunks", [])),
            "answer": result.get("answer"),
        }
        results.append(row)
        insert_eval_row(conn, question, result.get("answer"))

        print(
            f"[{row['status']:>7}] persona={row['actual_persona']!s:<18} "
            f"({'OK ' if row['actual_persona'] == row['expected_persona'] else 'MISS'}) "
            f"query_type={row['actual_query_type']!s:<12} "
            f"({'OK ' if row['actual_query_type'] == row['expected_query_type'] else 'MISS'}) "
            f"| {question[:60]}"
        )

    conn.close()

    n = len(results)
    persona_correct = sum(1 for r in results if r["actual_persona"] == r["expected_persona"])
    query_type_correct = sum(1 for r in results if r["actual_query_type"] == r["expected_query_type"])
    valid_count = sum(1 for r in results if r["status"] == "valid")
    total_cost = sum(r["cost_usd"] or 0.0 for r in results)

    persona_accuracy = persona_correct / n
    query_type_accuracy = query_type_correct / n

    print(f"\npersona_classification_accuracy: {persona_correct}/{n} = {persona_accuracy:.2%}")
    print(f"query_type_classification_accuracy: {query_type_correct}/{n} = {query_type_accuracy:.2%}")
    print(f"status=valid: {valid_count}/{n}")
    print(f"total cost: ${total_cost:.6f}")

    write_report(results, n, persona_correct, persona_accuracy, query_type_correct, query_type_accuracy, valid_count, total_cost)


def write_report(results, n, persona_correct, persona_accuracy, query_type_correct, query_type_accuracy, valid_count, total_cost):
    lines = [
        "# Golden set results",
        "",
        f"Rulat prin `eval/run_golden_set.py` pe cele {n} intrebari din `eval/golden_set.json`, "
        "prin `handle_query()` real (graful complet: classify -> retrieve -> rerank -> verify -> generate).",
        "",
        "## Ce se poate calcula onest",
        "",
        "| Metrica | Rezultat |",
        "|---|---|",
        f"| persona_classification_accuracy | {persona_correct}/{n} = {persona_accuracy:.2%} |",
        f"| query_type_classification_accuracy | {query_type_correct}/{n} = {query_type_accuracy:.2%} |",
        f"| status = valid (raspuns generat) | {valid_count}/{n} |",
        f"| cost total (15 query-uri) | ${total_cost:.6f} |",
        "",
        "## Ce NU s-a calculat, si de ce",
        "",
        "- **retrieval_recall_at_8** — necesita `expected_chunk_ids` per intrebare; "
        "`golden_set.json` le are `null` (nimeni nu a adnotat manual chunk-urile corecte "
        "pentru cele 15 intrebari). Nu poate fi calculat fara aceasta adnotare.",
        "- **faithfulness / judge_score** — necesita un LLM judge care sa verifice daca "
        "raspunsul e sustinut de contextul recuperat; neimplementat inca.",
        "",
        "## Detaliu per intrebare",
        "",
        "| Persona asteptata | Persona actuala | Query type asteptat | Query type actual | Status | Cost |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        persona_mark = "✓" if r["actual_persona"] == r["expected_persona"] else "✗"
        qt_mark = "✓" if r["actual_query_type"] == r["expected_query_type"] else "✗"
        lines.append(
            f"| {r['expected_persona']} | {r['actual_persona']} {persona_mark} | "
            f"{r['expected_query_type']} | {r['actual_query_type']} {qt_mark} | "
            f"{r['status']} | ${r['cost_usd'] or 0:.6f} |"
        )
    lines.append("")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"\nScris {REPORT_PATH}")


if __name__ == "__main__":
    main()
