# retrieve_multi nu producea niciun raspuns fara o companie numita explicit

## Ce s-a intamplat

Confirmat live in timpul unei demonstratii: query-ul "care este diferenta
dintre factorii de risk din 2024 vs 2025" a fost clasificat corect
(`investment_firm`, `comparison`), dar `extract_entities()` nu a gasit nicio
companie cunoscuta numita explicit (query-ul se refera la ani, nu la
companii) — a intors `[]`. Bucla `for ticker in entities` din `retrieve_multi`
nu a rulat deloc, `retrieved_chunks` a ramas gol, si `generate_answer` nu a
produs niciun raspuns (`status: "error"`, `answer: null`).

Deja identificat ca risc teoretic la review-ul de cod anterior (angle B,
finding "retrieve_multi returneaza retrieved_chunks gol, fara nicio eroare,
cand extract_entities nu gaseste niciun ticker cunoscut") — confirmat empiric
la prima utilizare reala dupa ce reranker-ul a devenit functional.

## Fix aplicat

`src/agent/nodes/retrieve.py::retrieve_multi`: daca `extract_entities`
intoarce `[]`, se foloseste fallback pe toate cele 3 companii cunoscute
(`list(KNOWN_ENTITIES.keys())`) in loc sa se opreasca silentios — corpusul
are oricum doar 3 companii, deci cautarea in toate 3 e un fallback sigur si
ieftin, nu o presupunere riscanta.

## Cand sa revii aici

Daca corpusul se extinde la mai multe companii, fallback-ul "cauta in toate"
devine scump/zgomotos — la punctul acela, `extract_entities` (sau un
inlocuitor bazat pe LLM, mentionat deja ca urmatorul pas in build-spec.md
sectiunea 4) trebuie sa gestioneze explicit si comparatii "in timp" (acelasi
companie, ani diferiti), nu doar comparatii intre companii — design-ul
actual al lui `retrieve_multi` nu diferentiaza deloc dupa `fiscal_year`.
