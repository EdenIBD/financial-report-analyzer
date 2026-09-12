# qdrant_client.query_points() intoarce QueryResponse, nu o lista

## Ce s-a intamplat

Codul dat de spec pentru `retrieve_single`/`retrieve_multi` (`src/agent/nodes/retrieve.py`)
paseaza rezultatul `qdrant_client.query_points(...)` direct in `reciprocal_rank_fusion`,
care face `for rank, r in enumerate(dense_results): scores[r.id] = ...` — presupunand ca
`dense_results` e o lista de obiecte cu `.id`/`.score`.

De fapt `query_points()` intoarce un `QueryResponse` (model pydantic cu un singur camp,
`points`). Iterand direct peste un model pydantic se obtin tupluri `(nume_camp, valoare)`,
nu punctele efective — de unde:

```
AttributeError: 'tuple' object has no attribute 'id'
```

Eroarea era complet invizibila din `/query` (raspundea doar `status: "error"`, fara detaliu,
pentru ca `handle_query` prinde orice exceptie generic) — gasita rulind `graph.invoke()`
direct, in afara try/except.

## Fix aplicat

Adaugat `.points` la fiecare din cele 4 apeluri `query_points()` (2 in `retrieve_single`,
2 in `retrieve_multi`) inainte de a le pasa in `reciprocal_rank_fusion`.

## Cand sa revii aici

Orice alt loc care apeleaza `qdrant_client.query_points()` sau `search()` direct trebuie
verificat la fel — nu presupune forma raspunsului fara sa citesti `.points` explicit.
