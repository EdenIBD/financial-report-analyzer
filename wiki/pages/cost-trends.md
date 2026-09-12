# Cost trends

Generat automat de `scripts/cost_trends.py` din `query_logs` (9 query-uri cu cost logat).

## Cost mediu per query_type

| query_type | n | cost mediu (USD) |
|---|---|---|
| comparison | 1 | 0.000108 |
| factual | 2 | 0.000168 |
| risk_analysis | 1 | 0.000122 |

**Observatie:** Query-urile de comparatie costa de ~0.6x fata de cele factuale ($0.000108 vs $0.000168 in medie).

## Cost mediu per persona

| persona | n | cost mediu (USD) |
|---|---|---|
| investment_bank | 1 | 0.000179 |
| investment_firm | 1 | 0.000108 |
| legal | 1 | 0.000122 |
| treasury | 1 | 0.000156 |

## Cost mediu per status

| status | n | cost mediu (USD) |
|---|---|---|
| error | 9 | 0.000063 |

## Ce nu poate fi calculat din query_logs

Sectiunea 7 din spec cere si corelatie pe `retry_count`, dar acesta nu e o coloana persistata in `query_logs` (schema.sql nu o include, iar sectiunea 7 interzice explicit adaugarea de coloane noi). Nu poate fi calculat din datele existente fara o sursa suplimentara (ex: extras din trace-urile LangSmith, unde retry_count exista in starea fiecarui nod).
