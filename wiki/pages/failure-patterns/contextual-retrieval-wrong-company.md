# Contextual retrieval: situating sentence names the wrong company on ~28% of the corpus

Data: 2026-09-12
Descoperit: citind efectiv textul chunk-urilor retrieved in noul panou "Show
retrieved chunks" din UI, nu presupunand ca contextual retrieval a iesit bine.
Un chunk MSFT_2026 arata cu propozitia de context "Acest fragment provine din
Raportul Anual al companiei **Apple Inc.**" — clar gresit, companie diferita.

## Amploare reala (masurata, nu estimata)

Numarand doar propozitia de context (prima linie, inainte de separatorul
`\n\n` care desparte contextul de fragmentul real), nu tot textul chunk-ului
(care poate mentiona legitim un competitor in Item 1A):

| Ticker | Chunk-uri cu compania gresita in context | Total chunk-uri | % |
|---|---|---|---|
| GOOGL | 927 (675 "Apple", 252 "Microsoft") | 2060 | **45.0%** |
| MSFT | 1204 (1089 "Apple", 115 "Alphabet") | 3697 | **32.6%** |
| NVDA | 74 | 347 | 21.3% |
| AAPL | 235 (213 "Microsoft", 22 "Alphabet") | 2493 | 9.4% |
| **Total** | **2440** | **8597** | **28.4%** |

Pe langa asta, 146 chunk-uri (concentrate mai ales in NVDA) au propozitia de
context inlocuita integral cu meta-comentariu — modelul raspundea cu "Iată
două variante de situare a fragmentului: **Varianta 1 (Specifică):** ..." in
loc de o propozitie directa, si tot acel text a fost stocat si embedat ca
parte din chunk.

## Cauza radacina — doua bug-uri separate in `src/ingestion/contextual.py`

1. **`add_context(chunk_text, doc_id, section)` primea `doc_id` ca parametru,
   dar prompt-ul nu-l folosea niciodata.** Modelul trebuia sa ghiceasca firma
   si anul doar din primele 300 caractere ale fragmentului. Pe fragmente care
   incep cu text generic (boilerplate legal, definitii, tabele fara nume de
   companie in primele randuri), modelul ghicea, si ghicea des gresit —
   probabil catre Apple ca exemplu "implicit" de 10-K din datele lui de
   antrenament.
2. **Chiar dupa ce doc_id a fost dat explicit in prompt, `gemini-3.1-flash-lite`
   tot nu respecta o instructiune formulata conversational** — raspundea cu
   "Iată două variante..." si explicatii in loc de o singura propozitie
   directa. Prompt-ul original ("Genereaza 1-2 propozitii...") lasa loc de
   interpretare; modelul a interpretat asta ca o cerere de brainstorming.

## De ce a trecut neobservat pana acum

Filtrarea de retrieval (`retrieve.py`) foloseste campul real `company` din
payload-ul Qdrant (ticker-ul, populat corect din pipeline, independent de
propozitia de context), nu textul generat. Deci **rezultatele de retrieval nu
au fost afectate** — un query despre Microsoft tot gasea chunk-uri MSFT
corecte, filtrate corect pe companie. Defectul era vizibil doar daca citeai
efectiv continutul complet al unui chunk retrieved, ceea ce UI-ul dinainte de
azi nu expunea intr-un mod usor de observat.

Impact real, totusi:
- **Calitatea embeddingului**: propozitia de context e prepended INAINTE de
  embedding (`embed_document(contextualized)`), deci vectorul unui chunk MSFT
  contine un semnal fals catre "Apple Inc." — poate dilua sau deplasa usor
  similaritatea semantica a cautarii dense (nu a fost masurat cat de mult).
- **Increderea utilizatorului**: panoul "Show retrieved chunks" arata acum
  text corect al filing-ului, dar cu o propozitie de deschidere care contrazice
  eticheta companie/an de langa ea — confuz, chiar daca continutul de dedesubt
  e corect.

## Fix aplicat (previne aparitia pe viitor, nu repara istoricul)

`add_context` primeste acum `doc_id` explicit in prompt si o instructiune
stricta de output (o singura propozitie, foloseste exact identificatorul dat,
fara alternative). Verificat direct, live, pe 4 companii diferite — toate
corecte, fara variante, fara ghicit:

```
MSFT_2026 -> 'This fragment is from filing "MSFT_2026", section "mdna".'
GOOGL_2024 -> 'This fragment is from filing "GOOGL_2024", section "risk_factors".'
AAPL_2023 -> 'This fragment is from filing "AAPL_2023", section "financial_statements".'
NVDA_2026_10K -> 'This fragment is from filing "NVDA_2026_10K", section "controls_procedures".'
```

Rezultatul e literal (ecou al identificatorului, nu proza naturala cu numele
companiei scrise) — corectitudine garantata in locul unei formulari mai
naturale. Orice ingestie noua (upload, ingestie dinamica) foloseste deja
fix-ul; cele 2440 + 146 chunk-uri deja ingerate raman neschimbate pana la o
decizie explicita de remediere (cost estimat: ~$0.37 in apeluri LLM, dar
~3 ore de rulare secventiala la ritmul observat de ~14 chunk-uri/minut — timpul,
nu costul, e constrangerea reala).

## Update — 2026-09-13

Canonical-section remediation has been checked, including fresh parsing of all 16 drifted Microsoft sections and full PostgreSQL/Qdrant text equality. The detector's remaining 159 flags are not 159 verified errors: 158 are legacy Item-category chunks, while the canonical NVIDIA flag correctly mentions a Microsoft agreement found in its source body. See [[msft-parse-drift-during-remediation]] and [[evaluation-2026-09-13]]. Historical percentages on this page describe the pre-repair heuristic sample, not current retrieval accuracy.
