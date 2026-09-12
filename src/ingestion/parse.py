"""Extrage sectiunile unui 10-K sau 10-Q, mapate la categorii canonice comune
(src/ingestion/sections.py) — nu la numarul brut de Item, care difera intre
tipurile de filing.

sec-parser nu are Edgar10KParser (doar Edgar10QParser exista in pachetul
instalat, v0.58.1). Edgar10QParser clasifica gresit sectiunile specifice
10-K (Item 1A, 7, 7A, 8, 9A...) ca "Invalid section type" pentru ca schema
lui interna e cea a 10-Q. Insa detectia titlurilor (TopSectionTitle /
TitleElement) e corecta indiferent de asta — validat manual mai jos.
Asa ca folosim Edgar10QParser doar pentru tree-ul de elemente si facem
sectionarea noi, dupa textul titlului (regex "Item N[Litera]."), nu dupa
section_type-ul (gresit) al parserului. Acelasi parser de elemente merge
si pe un 10-Q real (verificat), doar maparea Item -> categorie difera.
"""

import os
import re

import sec_parser as sp

from src.ingestion.sections import CANONICAL_SECTIONS

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw")

# "\.?(\s|$)" pentru ca unii filer-i (ex: Google) pun titlul intr-un element
# separat de numarul item-ului ("ITEM 1." fara text dupa), altii (Apple) pun
# numarul si titlul in acelasi element ("Item 1.    Business").
ITEM_TITLE_RE = re.compile(r"^item\s+(\d+[a-z]?)\.?(\s|$)", re.IGNORECASE)
# 10-Q are titluri "PART I — FINANCIAL INFORMATION" / "PART II — OTHER INFORMATION"
# (verificat pe filing real AAPL) — necesar doar pentru disambiguarea Item1-4
# intre Part I si Part II, 10-K nu are nevoie de Part pentru mapare.
PART_TITLE_RE = re.compile(r"^part\s+(i|ii)\b", re.IGNORECASE)
# ponytail: la unii filer-i (vazut la Microsoft), primele 1-3 caractere ale
# titlului de sectiune ajung intr-un element separat de restul titlului si
# se pierd (ex: "RISK FACTORS" -> continutul incepe cu "K FACTORS"). Nu
# afecteaza sectiunea gasita, doar cateva caractere de la inceputul ei —
# de reparat doar daca eval-ul arata ca afecteaza retrieval-ul.


def parse_filing(html: str, filing_type: str = "10-K") -> dict[str, str]:
    canonical_map = CANONICAL_SECTIONS[filing_type]
    elements = sp.Edgar10QParser().parse(html)
    tree = sp.TreeBuilder().build(elements)

    sections: dict[str, str] = {}
    current_category = None
    current_part = None
    for node in tree.nodes:
        element = node.semantic_element
        text = getattr(element, "text", "") or ""
        stripped = text.strip()

        part_match = PART_TITLE_RE.match(stripped)
        if part_match:
            current_part = "PartI" if part_match.group(1).lower() == "i" else "PartII"
            continue

        item_match = ITEM_TITLE_RE.match(stripped)
        if item_match:
            item = item_match.group(1).upper()
            if filing_type == "10-Q" and current_part:
                raw_key = f"{current_part}_Item{item}"
            else:
                raw_key = f"Item{item}"
            current_category = canonical_map.get(raw_key)
            continue

        if current_category:
            sections.setdefault(current_category, "")
            sections[current_category] += text + "\n"

    return sections


if __name__ == "__main__":
    # Validare manuala obligatorie (build-spec.md sectiunea 3): ruleaza pe 2-3
    # fisiere din data/raw/ si arata output-ul, nu presupune ca e corect.
    from src.ingestion.sections import REQUIRED_CANONICAL_SECTIONS

    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".html"))[:3]
    for filename in files:
        with open(os.path.join(RAW_DIR, filename), encoding="utf-8") as f:
            html = f.read()
        sections = parse_filing(html)
        print(f"--- {filename} ---")
        for category in sorted(sections):
            preview = sections[category].strip().replace("\n", " ")[:100]
            print(f"  {category}: {len(sections[category])} caractere | {preview}...")
        missing = REQUIRED_CANONICAL_SECTIONS - set(sections)
        if missing:
            print(f"  LIPSA: {sorted(missing)}")
