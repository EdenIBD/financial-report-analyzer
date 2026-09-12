"""Extrage sectiunile (Item 1, 1A, 2, 3, 5, 7, 7A, 8, 9A...) dintr-un 10-K.

sec-parser nu are Edgar10KParser (doar Edgar10QParser exista in pachetul
instalat, v0.58.1). Edgar10QParser clasifica gresit sectiunile specifice
10-K (Item 1A, 7, 7A, 8, 9A...) ca "Invalid section type" pentru ca schema
lui interna e cea a 10-Q. Insa detectia titlurilor (TopSectionTitle /
TitleElement) e corecta indiferent de asta — validat manual mai jos.
Asa ca folosim Edgar10QParser doar pentru tree-ul de elemente si facem
sectionarea noi, dupa textul titlului (regex "Item N[Litera]."), nu dupa
section_type-ul (gresit) al parserului.
"""

import os
import re

import sec_parser as sp

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw")

TARGET_ITEMS = {"1", "1A", "2", "3", "5", "7", "7A", "8", "9A"}
# "\.?(\s|$)" pentru ca unii filer-i (ex: Google) pun titlul intr-un element
# separat de numarul item-ului ("ITEM 1." fara text dupa), altii (Apple) pun
# numarul si titlul in acelasi element ("Item 1.    Business").
ITEM_TITLE_RE = re.compile(r"^item\s+(\d+[a-z]?)\.?(\s|$)", re.IGNORECASE)
# ponytail: la unii filer-i (vazut la Microsoft), primele 1-3 caractere ale
# titlului de sectiune ajung intr-un element separat de restul titlului si
# se pierd (ex: "RISK FACTORS" -> continutul incepe cu "K FACTORS"). Nu
# afecteaza sectiunea gasita, doar cateva caractere de la inceputul ei —
# de reparat doar daca eval-ul arata ca afecteaza retrieval-ul.


def parse_filing(html: str) -> dict[str, str]:
    elements = sp.Edgar10QParser().parse(html)
    tree = sp.TreeBuilder().build(elements)

    sections: dict[str, str] = {}
    current_item = None
    for node in tree.nodes:
        element = node.semantic_element
        text = getattr(element, "text", "") or ""
        match = ITEM_TITLE_RE.match(text.strip())
        if match:
            item = match.group(1).upper()
            current_item = f"Item{item}" if item in TARGET_ITEMS else None
            continue
        if current_item:
            sections.setdefault(current_item, "")
            sections[current_item] += text + "\n"

    return sections


if __name__ == "__main__":
    # Validare manuala obligatorie (build-spec.md sectiunea 3): ruleaza pe 2-3
    # fisiere din data/raw/ si arata output-ul, nu presupune ca e corect.
    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".html"))[:3]
    for filename in files:
        with open(os.path.join(RAW_DIR, filename), encoding="utf-8") as f:
            html = f.read()
        sections = parse_filing(html)
        print(f"--- {filename} ---")
        for item in sorted(sections):
            preview = sections[item].strip().replace("\n", " ")[:100]
            print(f"  {item}: {len(sections[item])} caractere | {preview}...")
        missing = TARGET_ITEMS - {i.replace("Item", "") for i in sections}
        if missing:
            print(f"  LIPSA: {sorted(missing)}")
