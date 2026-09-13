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

**Decizie luata (2026-09-13): optiunea 1** — re-ingestie completa, curata,
doar pentru perechile (doc_id, sectiune) din tabelul de mai sus.

## Incident operational: doua intreruperi, una a produs un gol real de continut

`scripts/reingest_msft_drifted_sections.py`, versiunea initiala, facea
**sterge intai, insereaza dupa** per sectiune (simetric cu cum arata orice
migratie "curata" pe hartie). Pe masina asta insa, Docker Desktop s-a oprit
de doua ori in timpul rularii (motiv probabil: repaus/sleep al laptopului,
nu o eroare de cod) — de fiecare data, `docker compose exec` a raportat
"completed, exit code 0" prin sistemul de notificari, un fals pozitiv (
procesul a fost omorat odata cu daemon-ul Docker, nu s-a terminat normal).

Consecinta reala a ordinii sterge-apoi-insereaza: la a doua intrerupere,
job-ul murise la mijlocul insertului pentru `MSFT_2021/risk_factors` —
sectiunea veche (149 chunk-uri) fusese deja stearsa complet, iar insertul
nou ajunsese doar la 108 din 143 tinta. Timp de cateva ore (pana la
verificarea urmatoare), acea sectiune a avut **un gol real de continut**:
35 de chunk-uri de text financiar real, indisponibile pentru retrieval, nu
doar etichetate gresit — o regresie mai grava decat bug-ul pe care remedierea
incerca sa-l repare.

**Lectie si fix aplicat**: ordinea a fost inversata — **insereaza intai
(complet), sterge dupa** (`delete_stale_old_style_chunks`, apelat abia dupa
ce noul set de chunk-uri e complet inserat). Chunk-urile vechi si cele noi
au formate de `chunk_id` diferite (`{doc_id}_Item8_{n}` vechi vs
`{doc_id}_financial_statements_{n}` nou), deci nu se suprascriu — pot
coexista temporar fara sa produca goluri. Retrieval-ul filtreaza pe coloana
`section`, nu pe `chunk_id`, deci coexistenta temporara a doua segmentari nu
afecteaza corectitudinea query-urilor, doar adauga cateva chunk-uri
redundante pana la pasul de curatare. O intrerupere la mijloc, cu aceasta
ordine, lasa cel mult continut vechi redundant — niciodata un gol.

## Rezolvare finala (2026-09-13)

Re-ingestia curata pentru toate cele 16 perechi (doc_id, sectiune) din
tabelul de mai sus s-a terminat cu succes: 819 chunk-uri vechi sterse, 761
noi indexate, cost total $0.05. Verificat direct: toate cele 16 sectiuni au
acum exact numarul de chunk-uri asteptat de la re-parsarea curenta, toate cu
`chunk_id` in formatul nou consistent — nici o dezaliniere ramasa.

**A patra optimizare**: scriptul repeta necondiționat toate sectiunile la
fiecare repornire, chiar si pe cele deja terminate cu succes — la a patra
repornire, asta insemna sa refaca ore de munca deja corecta inainte sa
ajunga la treaba noua. Adaugat `already_done()`: verifica local (fara apel
LLM) daca sectiunea are deja exact numarul tinta de chunk-uri in formatul
nou, si sare peste daca da. Rezultat: repornirea finala a durat 13 minute
(doar cele 6 sectiuni ramase, nu toate cele 16), nu ore.

**Recontrol pe tot corpusul** dupa remediere: cele 2440+146 chunk-uri
initial afectate au scazut la 159 ramase — dar aproape toate (158/159) sunt
in sectiuni orfane (`Item1`, `Item2`, `Item5`), ramasite dinainte de
migrarea la taxonomia canonica, pe care `retrieve.py` nu le mai filtreaza
niciodata (`PERSONA_SECTIONS`/`FALLBACK_SECTIONS` folosesc doar cele 6
categorii canonice). Aceste chunk-uri sunt **inaccesibile la retrieval,
indiferent de continutul lor** — repararea propozitiei lor de context nu ar
schimba niciun comportament real al sistemului, deci nu a fost facuta.
Bug-ul e rezolvat complet pentru tot ce conteaza functional; cele 158
chunk-uri orfane raman ca o curatenie separata, de facut (sters, nu reparat)
daca se decide vreodata.

**A treia intrerupere, auto-provocata**: in timp ce job-ul de re-ingestie rula
(cu ordinea deja corectata insert-first), am rulat `docker compose up -d
--build frontend` pentru un update de design — si `api` a fost repornit
odata cu el (compose reconciliaza intreg proiectul, nu doar serviciul cerut),
omorand din nou exec-ul cu SIGKILL (exit 137). Verificare directa dupa aceea
a confirmat ca design-ul insert-first si-a facut treaba: nici un gol de
continut, doar sectiuni ramase partial completate (ex: MSFT_2025/mdna avea
151 chunk-uri — 113 vechi + 38 noi, coexistand, nu suprascrise). Lectie
suplimentara: **niciun `docker compose up`/`--build`, pe orice serviciu, cat
timp un exec de migratie de date ruleaza in fundal** — nu doar "nu rebuild pe
serviciul care ruleaza exec-ul", ci pe intregul proiect compose.

**Lectie generala pentru munca de migratie de date pe aceasta masina**:
notificarile de "job completed" de la procese `docker compose exec` de lunga
durata nu sunt de incredere daca Docker Desktop se poate opri singur (sleep)
— verificarea trebuie facuta mereu direct in baza de date/Qdrant dupa
finalizare, nu doar pe baza codului de iesire raportat. A doua lectie:
orice script de migratie care modifica date in productie ar trebui sa fie
implicit rezistent la intrerupere (insert-first, delete-after, sau
tranzactii atomice), nu doar "de obicei ruleaza pana la capat".

## Independent verification — 2026-09-13

The completed repair was checked against actual stored data, not the background-task notification. All 16 targeted document/section pairs have exactly the fresh parser's chunk counts and identical raw bodies (after removing the contextual prefix). The initial full-corpus audit found 9,189 identical IDs/texts in PostgreSQL and Qdrant; the final audit after NVIDIA FY2023 found 9,496 in each, without missing, orphaned or mismatched entries.

Evidence: `eval/results/corpus-audit.json` and `eval/results/corpus-audit-final.json`. No additional Microsoft reingestion is required for these pairs. The last batch's 761 chunks / $0.0503 / 760 seconds are **not** totals for all remediation batches.

The old contextual-prefix heuristic still flags 159 chunks: 158 in legacy Item categories excluded from canonical retrieval, and one NVIDIA risk-factor chunk. Inspection of that NVIDIA source shows an actual agreement with Microsoft; this is a detector false positive. Counts of name matches must not be described as counts of proven wrong-company attributions.
