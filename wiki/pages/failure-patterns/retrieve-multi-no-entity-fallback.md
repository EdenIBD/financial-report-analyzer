# retrieve_multi produced no answer at all without an explicitly named company

## What happened

Confirmed live during a demo: the query "what's the difference between the
risk factors in 2024 vs 2025" was classified correctly (`investment_firm`,
`comparison`), but `extract_entities()` found no known company named
explicitly (the query refers to years, not companies) — it returned `[]`.
The `for ticker in entities` loop in `retrieve_multi` never ran,
`retrieved_chunks` stayed empty, and `generate_answer` produced no answer
(`status: "error"`, `answer: null`).

Already flagged as a theoretical risk in an earlier code review (angle B,
finding "retrieve_multi returns empty retrieved_chunks, with no error, when
extract_entities finds no known ticker") — confirmed empirically on first
real use after the reranker became functional.

## Fix applied

`src/agent/nodes/retrieve.py::retrieve_multi`: if `extract_entities`
returns `[]`, fall back to all 3 known companies
(`list(KNOWN_ENTITIES.keys())`) instead of silently stopping — the corpus
only has 3 companies anyway, so searching all 3 is a safe, cheap fallback,
not a risky assumption.

## When to revisit

If the corpus grows to more companies, the "search everything" fallback
becomes expensive/noisy — at that point, `extract_entities` (or an
LLM-based replacement, already mentioned as the next step in build-spec.md
section 4) needs to explicitly handle "over time" comparisons too (same
company, different years), not just cross-company comparisons —
`retrieve_multi`'s current design doesn't differentiate by `fiscal_year` at
all.
