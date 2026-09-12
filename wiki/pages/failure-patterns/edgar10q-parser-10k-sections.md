# Edgar10QParser nu clasifica corect sectiunile unui 10-K

## Ce s-a intamplat

`sec-parser` (v0.58.1, PyPI) nu are `Edgar10KParser` — doar `Edgar10QParser`.
Clasificarea semantica de sectiuni a lui `Edgar10QParser` e specifica structurii
unui 10-Q (Item 1-4 in Part I, Item 1-6 in Part II, cu alte sensuri decat in 10-K)
si nu recunoaste Item-urile specifice 10-K: 1A, 7, 7A, 8, 9A. Aceste titluri
apar in arbore ca `TitleElement` simplu (nu `TopSectionTitle`) sau sunt marcate
`InvalidTopSectionIn10Q`, cu warning la parsing.

## Fix aplicat

`src/ingestion/parse.py` foloseste `Edgar10QParser` + `TreeBuilder` doar pentru
arborele de elemente HTML (parsing structural — detectia titlurilor e corecta
indiferent de clasificarea semantica gresita). Sectionarea se face pe regex al
textului titlului (`Item N[Litera]`), nu pe `section_type`-ul parserului.

## Caz particular: Google

Regexul initial cerea spatiu obligatoriu dupa punct (`Item 1A. `). Pe filing-ul
GOOGL 2023, titlurile sunt intr-un element separat, fara text dupa punct
(`"ITEM 1."`) — regexul strict a picat complet, 0 sectiuni gasite. Fix: regex
relaxat la `\.?(\s|$)` (accepta si finalul stringului, nu doar spatiu).

## Caveat cunoscut, neremediat: Microsoft

Pe MSFT, primele 1-3 caractere ale unor titluri se pierd in continutul extras
(ex: "RISK FACTORS" → continutul incepe cu "K FACTORS"). Nu afecteaza care
sectiune e identificata, doar inceputul textului. Marcat cu comentariu
`# ponytail:` in cod. De verificat daca afecteaza retrieval-ul (improbabil pe
dense embeddings, posibil pe keyword/full-text matching daca cineva cauta
exact termenul trunchiat).

## Cand sa revii aici

Daca extinzi corpusul la alte companii, formatul de titlu poate diferi (cum a
fost cazul Google) — repeta validarea manuala (afisare output, nu presupunere)
pe 2-3 documente noi inainte de a rula pe tot corpusul.
