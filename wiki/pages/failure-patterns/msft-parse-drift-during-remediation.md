# MSFT parsing has drifted since original ingestion — discovered mid-remediation, may have introduced misalignment

Data: 2026-09-13
Context: in timp ce rulam `scripts/fix_contextual_sentences.py` (remedierea
pentru [contextual-retrieval-wrong-company.md](contextual-retrieval-wrong-company.md)),
scriptul a esuat cu "index N nu mai exista dupa re-chunking" pentru ~29 din
cele 225 de chunk-uri MSFT ramase in ultimul lot. Investigand de ce, am gasit
o problema mai larga si mai veche, independenta de bug-ul pe care il reparam.

## Ce s-a gasit

Re-parsand HTML-ul brut (`data/raw/MSFT_*.html`, nemodificat) cu `parse.py`
**din stadiul lui curent**, textul extras pentru sectiunile canonice ale MSFT
e mai scurt decat la ingestia originala — pe undeva, in una din editarile
succesive ale `parse.py` de-a lungul sesiunilor anterioare (proiectul nu are
istoric git de consultat), granitele de sectiune pentru MSFT s-au schimbat.

| Filing | Sectiune | Chunk-uri stocate | Chunk-uri la re-parsare azi | Diferenta |
|---|---|---|---|---|
| MSFT_2021 | financial_statements | 305 | 304 | -1 |
| MSFT_2021 | risk_factors | 149 | 143 | -6 |
| MSFT_2023 | financial_statements | 273 | 265 | -8 |
| MSFT_2023 | risk_factors | 145 | 138 | -7 |
| MSFT_2024 | controls_procedures | 23 | 21 | -2 |
| MSFT_2024 | financial_statements | 281 | 273 | -8 |
| MSFT_2024 | mdna | 136 | 127 | -9 |
| MSFT_2024 | risk_factors | 159 | 146 | -13 |
| MSFT_2025 | controls_procedures | 18 | 16 | -2 |
| MSFT_2025 | financial_statements | 252 | 238 | -14 |
| MSFT_2025 | mdna | 113 | 104 | -9 |
| MSFT_2025 | risk_factors | 141 | 128 | -13 |
| MSFT_2026 | controls_procedures | 18 | 16 | -2 |
| MSFT_2026 | financial_statements | 255 | 244 | -11 |
| MSFT_2026 | mdna | 126 | 117 | -9 |
| MSFT_2026 | risk_factors | 166 | 152 | -14 |

**GOOGL, AAPL si NVDA nu au aceasta problema** — re-parsarea lor azi produce
exact acelasi numar de chunk-uri ca la ingestie, pe toate sectiunile
canonice. Doar MSFT e afectat, pe toate cele 5 filing-uri.

Pentru MSFT_2023/financial_statements, primul index la care chunk-ul
re-generat difera de cel stocat e **indexul 26 din 273** — deci nu e doar o
problema la coada sectiunii, diferenta incepe devreme si se propaga.

## De ce conteaza pentru remedierea in curs

`fix_contextual_sentences.py` repara un chunk_id existent re-parsand sectiunea
lui si luand textul brut de la `chunk_index`-ul respectiv din rezultatul
proaspat. Presupunerea (valabila pentru GOOGL/AAPL/NVDA, verificata) era ca
re-parsarea azi reproduce identic segmentarea originala. **Pentru MSFT, asta
e falsa** — scriptul a rescris deja urmatoarele chunk-uri MSFT cu text
provenit dintr-o segmentare care nu se mai aliniaza garantat cu chunk-urile
vecine (ramase din segmentarea veche, mai lunga):

| Filing | Sectiuni afectate, chunk-uri deja rescrise |
|---|---|
| MSFT_2021 | financial_statements 135, mdna 43, risk_factors 46, controls_procedures 6 |
| MSFT_2023 | financial_statements 117, mdna 60, risk_factors 42, controls_procedures 10 |
| MSFT_2024 | financial_statements 118, mdna 42, risk_factors 57, controls_procedures 8 |
| MSFT_2025 | financial_statements 112, mdna 33, risk_factors 56, controls_procedures 8 |
| MSFT_2026 | financial_statements 122, mdna 40, risk_factors 55, controls_procedures 7 |

Nota: "rescris" nu inseamna neaparat "gresit" — inseamna ca granitele de
chunk s-au putut deplasa, deci setul complet de chunk-uri al unei sectiuni
(cele rescrise + cele ramase netouched la coada, cu segmentarea veche) ar
putea avea acum suprapuneri sau goluri fata de textul complet al sectiunii.
Nu a fost inca verificat daca exista goluri reale de continut sau daca
efectul e benign (doar granite usor deplasate, fara pierdere neta). Scriptul
de remediere a fost **oprit** in acest punct, fara sa continue peste MSFT,
tocmai ca sa nu adanceasca o eventuala problema inainte de o decizie.

## Ce nu s-a atins

`legal_proceedings` si `market_risk` pentru MSFT NU apar in tabelul de drift
— acelea au fost reparate normal, fara risc de dezaliniere. La fel, tot ce
s-a reparat pentru GOOGL/AAPL/NVDA e verificat corect si sigur.

## Optiuni de remediere (decizie in asteptare)

1. **Re-ingestie completa, curata, doar pentru (doc_id, sectiune) afectate**
   la MSFT: sterge chunk-urile existente din Postgres+Qdrant pentru acele
   perechi, re-parseaza + re-chunk-uieste + re-contextualizeaza + re-embedeaza
   totul de la zero, cu indici 0..N noi, consistenti. Cea mai sigura, dar
   inseamna re-facut ~600 chunk-uri MSFT deja atinse plus restul sectiunii
   (nu doar cele afectate initial) — comparabil ca timp/cost cu remedierea
   deja facuta (~3 ore).
2. Accepta starea curenta ca e, documentata ca risc cunoscut necuantificat
   (posibile goluri/suprapuneri minore in cateva sectiuni MSFT), fara alt
   cost — dar fara sa se stie exact daca vreun fragment de continut real a
   fost pierdut din corpus.
3. Investigheaza mai intai daca exista vreun gol real de continut (comparand
   text-ul complet al sectiunii vechi reconstituit din chunk-uri stocate,
   inainte de a fi rescrise, cu cel nou) — dar chunk-urile deja rescrise
   si-au pierdut deja continutul vechi (nu exista backup), deci comparatia
   se poate face doar pe chunk-urile inca netouched (legal_proceedings,
   market_risk, si coada nefixata din celelalte sectiuni).
