# Cost trends

Generat automat de `scripts/cost_trends.py` din `query_logs` (97 query-uri cu cost logat).

## Cost mediu per query_type

| query_type | n | cost mediu (USD) |
|---|---|---|
| comparison | 22 | 0.008261 |
| factual | 34 | 0.008182 |
| risk_analysis | 33 | 0.012891 |

**Observatie:** Query-urile de comparatie costa de ~1.0x fata de cele factuale ($0.008261 vs $0.008182 in medie).

## Cost mediu per persona

| persona | n | cost mediu (USD) |
|---|---|---|
| audit_firm | 6 | 0.010642 |
| investment_bank | 7 | 0.011028 |
| investment_firm | 46 | 0.010675 |
| legal | 11 | 0.009015 |
| treasury | 19 | 0.008110 |

## Cost mediu per status

| status | n | cost mediu (USD) |
|---|---|---|
| abstained | 2 | 0.005855 |
| error | 20 | 0.000325 |
| valid | 75 | 0.011562 |

## Cost mediu cu vs. fara ingestie live

| tip query | n | cost mediu (USD) |
|---|---|---|
| cu ingestie live | 3 | 0.053135 |
| fara ingestie | 94 | 0.007723 |

**Observatie:** Un query care declanseaza ingestie live costa de ~7x un query obisnuit ($0.053135 vs $0.007723 in medie) — ingestia face un apel LLM de contextual retrieval per chunk, sute per filing.

## Ce nu poate fi calculat din query_logs

Sectiunea 7 din spec cere si corelatie pe `retry_count`, dar acesta nu e o coloana persistata in `query_logs` (schema.sql nu o include, iar sectiunea 7 interzice explicit adaugarea de coloane noi). Nu poate fi calculat din datele existente fara o sursa suplimentara (ex: extras din trace-urile LangSmith, unde retry_count exista in starea fiecarui nod).
