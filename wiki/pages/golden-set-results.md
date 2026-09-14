# Golden set results

Run via `eval/run_golden_set.py` on the 15 questions in `eval/golden_set.json`, through the real `handle_query()` (the full graph: classify -> retrieve -> rerank -> verify -> generate).

## What can honestly be calculated

| Metric | Result |
|---|---|
| persona_classification_accuracy | 15/15 = 100.00% |
| query_type_classification_accuracy | 14/15 = 93.33% |
| status = valid (answer generated) | 15/15 |
| total cost (15 queries) | $0.178093 |

## What was NOT calculated, and why

- **retrieval_recall_at_8** — needs `expected_chunk_ids` per question; `golden_set.json` has them as `null` (nobody has manually annotated the correct chunks for these 15 questions). Cannot be computed without that annotation.
- **faithfulness / judge_score** — needs an LLM judge to verify whether the answer is supported by the retrieved context; not implemented yet.

## Per-question detail

| Expected persona | Actual persona | Expected query type | Actual query type | Status | Cost |
|---|---|---|---|---|---|
| legal | legal ✓ | risk_analysis | risk_analysis ✓ | valid | $0.012969 |
| legal | legal ✓ | factual | factual ✓ | valid | $0.011791 |
| legal | legal ✓ | comparison | comparison ✓ | valid | $0.012163 |
| audit_firm | audit_firm ✓ | factual | factual ✓ | valid | $0.009430 |
| audit_firm | audit_firm ✓ | risk_analysis | factual ✗ | valid | $0.010535 |
| audit_firm | audit_firm ✓ | comparison | comparison ✓ | valid | $0.011113 |
| investment_firm | investment_firm ✓ | comparison | comparison ✓ | valid | $0.012197 |
| investment_firm | investment_firm ✓ | risk_analysis | risk_analysis ✓ | valid | $0.013455 |
| investment_firm | investment_firm ✓ | factual | factual ✓ | valid | $0.010396 |
| investment_bank | investment_bank ✓ | factual | factual ✓ | valid | $0.012904 |
| investment_bank | investment_bank ✓ | comparison | comparison ✓ | valid | $0.010822 |
| investment_bank | investment_bank ✓ | risk_analysis | risk_analysis ✓ | valid | $0.011214 |
| treasury | treasury ✓ | risk_analysis | risk_analysis ✓ | valid | $0.012164 |
| treasury | treasury ✓ | factual | factual ✓ | valid | $0.012623 |
| treasury | treasury ✓ | comparison | comparison ✓ | valid | $0.014314 |
