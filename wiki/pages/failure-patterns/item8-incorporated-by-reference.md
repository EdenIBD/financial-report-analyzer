# Item 8 incorporat prin referinta: sectiune "gasita", dar practic goala

Data: 2026-09-12
Descoperit la: primul filing ingerat dinamic din afara corpusului fix (NVDA 10-K FY2026).

## Ce s-a intamplat

`parse_filing` + `validate_sections` au trecut curat pe NVDA_2026: toate cele 6
categorii canonice gasite, validare OK. Dar dimensiunile spun altceva:

| categorie | NVDA_2026 |
|---|---|
| risk_factors | 114.252 caractere |
| mdna | 33.685 |
| market_risk | 4.160 |
| controls_procedures | 3.372 |
| legal_proceedings | 171 |
| **financial_statements** | **155** |

Continutul lui `financial_statements` e integral:

> "The information required by this Item is set forth in our Consolidated
> Financial Statements..."

Adica un pointer, nu situatiile financiare. La fel `legal_proceedings` (171
caractere, trimite la Nota 12). NVIDIA incorporeaza Item 8 si Item 3 prin
referinta la alte parti ale documentului, in loc sa puna continutul sub titlul
Item-ului — perfect legal si obisnuit la SEC, dar invizibil pentru un parser
care sectioneaza dupa titluri de Item.

## De ce conteaza

`financial_statements` e in `PERSONA_SECTIONS` pentru 4 din 5 persona-uri
(audit_firm, investment_firm, investment_bank, treasury). Pentru un filing
ingerat asa, acele query-uri filtreaza pe o sectiune care are un singur chunk
inutil. Nu e o eroare — e un raspuns slab, fara niciun semnal ca ceva lipseste.

Corpusul fix (Apple/Microsoft/Google) nu arata problema: acolo
`financial_statements` are ~3.100 chunk-uri in total, deci continutul chiar e
sub titlul Item-ului. E o diferenta intre filer-i, exact clasa de bug de la
Google (titluri fara spatiu dupa punct), doar ca de data asta esecul e tacut.

## Ce NU s-a facut

`validate_sections` verifica prezenta, nu dimensiunea. Un prag de lungime
minima per sectiune ar prinde cazul asta, dar ar respinge si filing-uri
legitime — pragul corect nu poate fi ghicit dintr-un singur exemplu. De decis
dupa ce mai sunt ingerate cateva companii din afara corpusului, nu acum.

Urmarirea corecta a referintelor incrucisate ("see Note 12") ar insemna un
parser de alt nivel decat sectionarea dupa titluri — nu intra in scopul curent.
