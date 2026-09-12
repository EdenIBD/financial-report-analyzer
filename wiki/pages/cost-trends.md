# Cost trends

Generat automat de `scripts/cost_trends.py` din `query_logs` (27 query-uri cu cost logat).

## Cost mediu per query_type

| query_type | n | cost mediu (USD) |
|---|---|---|
| comparison | 10 | 0.003444 |
| factual | 8 | 0.001492 |
| risk_analysis | 4 | 0.000504 |

**Observatie:** Query-urile de comparatie costa de ~2.3x fata de cele factuale ($0.003444 vs $0.001492 in medie).

## Cost mediu per persona

| persona | n | cost mediu (USD) |
|---|---|---|
| investment_bank | 1 | 0.000179 |
| investment_firm | 13 | 0.002795 |
| legal | 2 | 0.000395 |
| treasury | 6 | 0.001849 |

## Cost mediu per status

| status | n | cost mediu (USD) |
|---|---|---|
| error | 16 | 0.000128 |
| valid | 11 | 0.004213 |

## Ce nu poate fi calculat din query_logs

Sectiunea 7 din spec cere si corelatie pe `retry_count`, dar acesta nu e o coloana persistata in `query_logs` (schema.sql nu o include, iar sectiunea 7 interzice explicit adaugarea de coloane noi). Nu poate fi calculat din datele existente fara o sursa suplimentara (ex: extras din trace-urile LangSmith, unde retry_count exista in starea fiecarui nod).
