# Edgar10QParser does not correctly classify a 10-K's sections

## What happened

`sec-parser` (v0.58.1, PyPI) has no `Edgar10KParser` — only `Edgar10QParser`.
`Edgar10QParser`'s semantic section classification is specific to a 10-Q's
structure (Item 1-4 in Part I, Item 1-6 in Part II, with different meanings
than in a 10-K) and doesn't recognize 10-K-specific Items: 1A, 7, 7A, 8, 9A.
These titles show up in the tree as a plain `TitleElement` (not
`TopSectionTitle`) or get flagged `InvalidTopSectionIn10Q`, with a parsing
warning.

## Fix applied

`src/ingestion/parse.py` uses `Edgar10QParser` + `TreeBuilder` only for the
HTML element tree (structural parsing — title detection is correct
regardless of the wrong semantic classification). Sectioning is done via a
regex on the title text (`Item N[Letter]`), not the parser's `section_type`.

## Special case: Google

The initial regex required a mandatory space after the period (`Item 1A. `).
In the GOOGL 2023 filing, the titles sit in a separate element with no text
after the period (`"ITEM 1."`) — the strict regex failed completely, 0
sections found. Fix: regex relaxed to `\.?(\s|$)` (also accepts end of
string, not just a space).

## Known caveat, unfixed: Microsoft

For MSFT, the first 1-3 characters of some titles are lost from the
extracted content (e.g. "RISK FACTORS" → the content starts with "K
FACTORS"). Doesn't affect which section is identified, only the start of
the text. Flagged with a `# ponytail:` comment in the code. Still to check
whether this affects retrieval (unlikely on dense embeddings, possible on
keyword/full-text matching if someone searches for the exact truncated
term).

## When to revisit

If the corpus expands to other companies, the title format may differ (as
happened with Google) — repeat manual validation (inspect the output,
don't assume) on 2-3 new documents before running against the whole corpus.
