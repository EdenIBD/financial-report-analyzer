# build-spec.md din 12 sept a cerut reintroducerea a 2 bug-uri critice deja reparate

## Ce s-a intamplat

O versiune noua a `build-spec.md` a dat cod "complet" pentru `retrieve_multi` si
`verify_context` care nu tinea cont de fix-urile aplicate deja azi (documentate
in `verify-context-infinite-retry-loop.md` si `retrieve-multi-no-entity-fallback.md`):

- **`verify.py`**: codul dat revenea la varianta originala — `verify_context`
  ca functie de rutare care muta `state["retry_count"]` direct. Aplicarea ei
  ar fi reintrodus bucla infinita retrieve<->rerank (deja confirmata: 300+
  iteratii, oprita doar de rate-limit extern Google).
- **`retrieve.py`**: `retrieve_multi` dat explicit nu avea fallback-ul pe
  `KNOWN_ENTITIES` cand `extract_entities` nu gaseste nicio companie —
  exact bug-ul confirmat live ("factorii de risc 2024 vs 2025" fara raspuns).

**NU s-au aplicat aceste doua bucati de cod.** Structura noua data pentru
`retrieve_multi` (pattern `base_filter`, `limit=10`, `top_k=5`) a fost adoptata,
dar cu fallback-ul pastrat peste ea.

## Alte discrepante gasite si verificate direct (nu presupuse)

- `gemini-embedding-2` (cerut din nou in `embed.py`/`qdrant_setup.py`/`cost.py`) —
  re-testat direct, tot 404. Ramas pe `gemini-embedding-001` (deja in productie,
  8250 vectori reali).
- `gemini-3-flash` (cerut nou pentru classify+generate) — testat direct, 404,
  nu exista. Inlocuit cu `gemini-3-flash-preview`, verificat functional.
- `gemini-3.1-flash-lite` (cerut pentru contextual retrieval) — testat direct,
  functioneaza. Aplicat ca atare (imbunatatire reala, nu conflict).

## Cand sa revii aici

Orice varianta viitoare a spec-ului care da cod "complet" pentru `verify.py`
sau `retrieve.py::retrieve_multi` trebuie comparata linie cu linie cu versiunea
curenta din repo inainte de a fi aplicata — nu presupune ca o versiune "mai
noua" a documentului reflecta neaparat fix-urile deja facute in cod. Verifica
mereu modelele Gemini/Vertex printr-un apel real inainte de a le adopta dintr-un
document, indiferent cat de sigur suna ("verificat", "confirmat") — lineup-ul
se schimba des si documentul poate fi el insusi gresit sau neactualizat.
