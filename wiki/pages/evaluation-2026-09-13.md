# Evaluation — 2026-09-13

Run after the company/fiscal-year scoping fix ([[company-year-scope]]) and the
MSFT parse-drift remediation ([[msft-parse-drift-during-remediation]]). All
numbers below are read directly from `eval/results/*.json`, not retyped from
memory — see each file for the full per-question detail.

## Golden set (classification)

[`eval/results/golden-set-latest.json`](../../eval/results/golden-set-latest.json), run at 2026-09-13T15:26:43Z, 15 questions, real pipeline:

| Metric | Result |
|---|---|
| Persona classification | **15/15 = 100%** |
| Query-type classification | **14/15 = 93.3%** |
| Answers generated (`status: valid`) | 15/15 |
| Total cost | $0.181626 |

The one query-type miss is the same one from the previous run: an
internal-controls-weakness question classified as `factual` instead of
`risk_analysis`. Stable across runs — not new noise from the scoping change.

Citation-ID integrity on this run: **15/15**. This verifies that cited IDs exist in retrieved context, not whether every claim is supported. The prior 14/15 result is preserved in the earlier evidence.

## Scope regressions (the actual bug report)

[`eval/results/scope-regressions.json`](../../eval/results/scope-regressions.json), 5 cases targeting the reported failure mode directly — a request for one company/year returning evidence from a different company or year:

| Case | Result |
|---|---|
| NVIDIA FY2023, English | pass |
| NVIDIA FY2023, Romanian | pass |
| Apple vs. NVIDIA comparison | pass |
| Taco Bell Funding, LLC (unresolvable registrant) | pass — abstains, no substitution |
| Unavailable fiscal year | pass — abstains, no substitution |

All 5 pass on the current code. [`scope-regressions-first-run.json`](../../eval/results/scope-regressions-first-run.json) is kept alongside: the first attempt hit a transient external DNS failure partway through (not a code defect) and was rerun rather than overwritten, per this project's practice of not quietly discarding an inconvenient first result.

"Pass" here means: the answer's sources are limited to the requested company/year (or the query abstains with zero sources) — it is a scope-correctness check, not a check that the financial content itself is accurate.

## Citation-identifier integrity

[`eval/results/citation-checks.json`](../../eval/results/citation-checks.json) — re-ran the golden set's 15 answers through `inspect_citations()`, checking every `[chunk_id]` in the generated text actually exists in the retrieved context (catches both a hallucinated source and a truncated one like `[61]`):

**14/15 pass.** The one failure: *"Ce impact ar putea avea nivelul actual de indatorare al Google asupra unei eventuale achizitii majore?"* — the model answered with no bracketed citation at all (`has_citations: False`), not a malformed one. Under the citation gate now wired into `generate_answer`, this specific answer would abstain in production rather than ship uncited. This is a real, known limitation on interpretive/forward-looking questions, not a bug in the checker.

**Scope note:** this validates that a cited identifier resolves to a real retrieved chunk. It does not validate that the cited chunk actually supports the claim next to it — that would require faithfulness scoring, still unimplemented (see below).

## Retrieval replay (single-filing probe, unchanged scope)

[`eval/results/retrieval-replay.json`](../../eval/results/retrieval-replay.json): the same frozen 17 synthetic AAPL FY2023 questions from the original retrieval probe, replayed against dense retrieval only (no reranking, no persona filtering):

```
Hit@8: 13/17 = 76.5%, MRR: 0.348
```

Unchanged from the original probe's finding — this measures the embedding step in isolation on one filing; it is not a corpus-wide recall number and was never expected to move from the scoping fix (which changes retrieval *filters*, not the embeddings or the underlying dense-search ranking).

## Corpus integrity audit

[`eval/results/corpus-audit-final.json`](../../eval/results/corpus-audit-final.json) — independent verification of the MSFT remediation ([[msft-parse-drift-during-remediation]]), run separately from the remediation script itself:

- Postgres and Qdrant both report **9,496 chunks**, zero missing on either side, zero orphans, zero text mismatches between the two stores.
- All 16 remediated (doc_id, section) pairs for MSFT show `expected == actual` chunk counts with no body mismatches.

This corroborates — via a separate script, not just the remediation job's own self-report — that the MSFT fix left the corpus internally consistent.

## Unit and browser tests

- Backend: **91 passed, 2 skipped** (`python -m pytest tests/`; skips are a missing local 10-Q fixture file, not a real failure). See [`unit-test-inventory.md`](unit-test-inventory.md) for the full per-test list, regenerated alongside this report.
- Frontend E2E: **14 passed** (`npx playwright test`), including the three new `query-scope.spec.ts` cases (historical-year evidence, unresolved-registrant abstention, eagle watermark placement against the reference layout) and the existing dynamic-ingestion/reasoning-trace/comparison suites.

## Still unmeasured

- **End-to-end Recall@8 and faithfulness against the golden set** — blocked on manually annotating `expected_chunk_ids` and building an LLM-judge, same gap as before; the scoping fix changes *what can be retrieved*, not this.
- **Citation-identifier integrity ≠ claim faithfulness.** A citation that resolves to a real chunk can still misrepresent what that chunk says; nothing here checks that.
- **Relative-date resolution** ("this year," "last quarter") beyond the explicit-year and simple-range regex in `requested_years()`.
- **Registrants without tickers** (like Taco Bell Funding, LLC) remain correctly *unresolved and reported*, not correctly *answerable* — extending coverage there needs a different resolution path than the SEC ticker catalog.

## Real upload and manual UI validation

See [[upload-evaluation-2026-09-13]] for all 13 file/variant results. Real browser upload WINA FY2024 Q3: ready, 122 chunks. Dynamic ingestion via UI for previously absent LWAY FY2023: 243 chunks, 269.706 seconds, $0.030287 estimated query cost; cited passages match LWAY/2023. Manual Apple–Microsoft FY2023 comparison: both companies present, all retrieved years 2023, clickable citations opened the matching passages. Raw Markdown delimiters remain visible in answer text; financial table interpretation and overbroad absence-of-risk statements remain qualitative review concerns.
