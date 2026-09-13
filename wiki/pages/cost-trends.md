# Cost trends

Generat automat de `scripts/cost_trends.py` din `query_logs` (51 query-uri cu cost logat).

## Cost mediu per query_type

| query_type | n | cost mediu (USD) |
|---|---|---|
| comparison | 15 | 0.006633 |
| factual | 20 | 0.007252 |
| risk_analysis | 11 | 0.012418 |

**Observatie:** Query-urile de comparatie costa de ~0.9x fata de cele factuale ($0.006633 vs $0.007252 in medie).

## Cost mediu per persona

| persona | n | cost mediu (USD) |
|---|---|---|
| audit_firm | 3 | 0.010925 |
| investment_bank | 4 | 0.010564 |
| investment_firm | 18 | 0.008498 |
| legal | 6 | 0.007460 |
| treasury | 15 | 0.007226 |

## Cost mediu per status

| status | n | cost mediu (USD) |
|---|---|---|
| error | 16 | 0.000128 |
| valid | 35 | 0.010831 |

## Cost mediu cu vs. fara ingestie live

| tip query | n | cost mediu (USD) |
|---|---|---|
| cu ingestie live | 1 | 0.067291 |
| fara ingestie | 50 | 0.006277 |

**Observatie:** Un query care declanseaza ingestie live costa de ~11x un query obisnuit ($0.067291 vs $0.006277 in medie) — ingestia face un apel LLM de contextual retrieval per chunk, sute per filing.

## Ce nu poate fi calculat din query_logs

Sectiunea 7 din spec cere si corelatie pe `retry_count`, dar acesta nu e o coloana persistata in `query_logs` (schema.sql nu o include, iar sectiunea 7 interzice explicit adaugarea de coloane noi). Nu poate fi calculat din datele existente fara o sursa suplimentara (ex: extras din trace-urile LangSmith, unde retry_count exista in starea fiecarui nod).
