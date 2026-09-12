"""Taxonomie canonica de sectiuni, comuna intre 10-K si 10-Q.

10-K si 10-Q numeroteaza aceleasi continuturi semantice cu Item-uri diferite
(ex: MD&A e Item7 la 10-K, Item2 la 10-Q). Fara aceasta mapare, retrieval-ul
filtrat pe Item brut (PERSONA_SECTIONS) nu ar gasi nimic intr-un 10-Q — vezi
feature-document-upload.md. Toate sectiunile extrase (indiferent de tipul de
filing) sunt mapate la aceeasi categorie canonica inainte de a ajunge in
Postgres/Qdrant, ca retrieval-ul sa filtreze pe categorie, nu pe Item brut.

La 10-Q, "Item 1"/"Item 2"/"Item 3"/"Item 4" apar de doua ori cu sens diferit
in Part I vs Part II (verificat pe un 10-Q real AAPL, 2026-06-27: Part I Item1
= Financial Statements, Part II Item1 = Legal Proceedings; Part II mai are si
Item2/3/4 proprii — Unregistered Sales/Defaults/Mine Safety — care nu sunt
categorii tinta, deci raman nemapate intentionat).
"""

CANONICAL_SECTIONS: dict[str, dict[str, str]] = {
    "10-K": {
        "Item1A": "risk_factors",
        "Item3": "legal_proceedings",
        "Item7": "mdna",
        "Item7A": "market_risk",
        "Item8": "financial_statements",
        "Item9A": "controls_procedures",
    },
    "10-Q": {
        "PartI_Item1": "financial_statements",
        "PartI_Item2": "mdna",
        "PartI_Item3": "market_risk",
        "PartI_Item4": "controls_procedures",
        "PartII_Item1": "legal_proceedings",
        "PartII_Item1A": "risk_factors",
    },
}

REQUIRED_CANONICAL_SECTIONS = {
    "risk_factors",
    "legal_proceedings",
    "mdna",
    "market_risk",
    "financial_statements",
    "controls_procedures",
}


class FilingValidationError(ValueError):
    """Documentul a trecut de detectia de metadata (dei:DocumentType etc.) dar
    parsing-ul de sectiuni nu a gasit toate categoriile canonice obligatorii —
    structura reala a documentului nu corespunde unui 10-K/10-Q complet."""


def validate_sections(sections: dict[str, str]) -> None:
    missing = REQUIRED_CANONICAL_SECTIONS - set(sections)
    if missing:
        raise FilingValidationError(
            f"Sectiuni obligatorii lipsa dupa parsing: {sorted(missing)} — "
            "documentul nu respecta structura asteptata a unui 10-K/10-Q."
        )
