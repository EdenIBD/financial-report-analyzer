# Cost trends

Generat automat de `scripts/cost_trends.py` din `query_logs` (129 query-uri cu cost logat).

## Cost mediu per query_type

| query_type | n | cost mediu (USD) |
|---|---|---|
| comparison | 29 | 0.009187 |
| factual | 46 | 0.009455 |
| risk_analysis | 46 | 0.012678 |

**Observatie:** Query-urile de comparatie costa de ~1.0x fata de cele factuale ($0.009187 vs $0.009455 in medie).

## Cost mediu per persona

| persona | n | cost mediu (USD) |
|---|---|---|
| audit_firm | 9 | 0.011311 |
| investment_bank | 10 | 0.011255 |
| investment_firm | 63 | 0.011313 |
| legal | 16 | 0.009500 |
| treasury | 23 | 0.008933 |

## Cost mediu per status

| status | n | cost mediu (USD) |
|---|---|---|
| abstained | 8 | 0.004104 |
| error | 20 | 0.000325 |
| valid | 101 | 0.012329 |

## Cost mediu cu vs. fara ingestie live

| tip query | n | cost mediu (USD) |
|---|---|---|
| cu ingestie live | 5 | 0.050353 |
| fara ingestie | 124 | 0.008329 |

**Observatie:** Un query care declanseaza ingestie live costa de ~6x un query obisnuit ($0.050353 vs $0.008329 in medie) — ingestia face un apel LLM de contextual retrieval per chunk, sute per filing.

## Ce nu poate fi calculat din query_logs

Sectiunea 7 din spec cere si corelatie pe `retry_count`, dar acesta nu e o coloana persistata in `query_logs` (schema.sql nu o include, iar sectiunea 7 interzice explicit adaugarea de coloane noi). Nu poate fi calculat din datele existente fara o sursa suplimentara (ex: extras din trace-urile LangSmith, unde retry_count exista in starea fiecarui nod).
