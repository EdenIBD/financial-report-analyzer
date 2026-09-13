# Golden set results

Rulat prin `eval/run_golden_set.py` pe cele 15 intrebari din `eval/golden_set.json`, prin `handle_query()` real (graful complet: classify -> retrieve -> rerank -> verify -> generate).

## Ce se poate calcula onest

| Metrica | Rezultat |
|---|---|
| persona_classification_accuracy | 15/15 = 100.00% |
| query_type_classification_accuracy | 14/15 = 93.33% |
| status = valid (raspuns generat) | 15/15 |
| cost total (15 query-uri) | $0.178093 |

## Ce NU s-a calculat, si de ce

- **retrieval_recall_at_8** — necesita `expected_chunk_ids` per intrebare; `golden_set.json` le are `null` (nimeni nu a adnotat manual chunk-urile corecte pentru cele 15 intrebari). Nu poate fi calculat fara aceasta adnotare.
- **faithfulness / judge_score** — necesita un LLM judge care sa verifice daca raspunsul e sustinut de contextul recuperat; neimplementat inca.

## Detaliu per intrebare

| Persona asteptata | Persona actuala | Query type asteptat | Query type actual | Status | Cost |
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
