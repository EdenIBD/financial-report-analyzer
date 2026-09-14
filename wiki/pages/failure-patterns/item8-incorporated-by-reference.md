# Item 8 incorporated by reference: section "found", but practically empty

Date: 2026-09-12
Discovered during: the first filing dynamically ingested from outside the fixed corpus (NVDA 10-K FY2026).

## What happened

`parse_filing` + `validate_sections` passed cleanly on NVDA_2026: all 6
canonical categories found, validation OK. But the sizes tell a different
story:

| category | NVDA_2026 |
|---|---|
| risk_factors | 114,252 characters |
| mdna | 33,685 |
| market_risk | 4,160 |
| controls_procedures | 3,372 |
| legal_proceedings | 171 |
| **financial_statements** | **155** |

The entire content of `financial_statements` is:

> "The information required by this Item is set forth in our Consolidated
> Financial Statements..."

In other words, a pointer, not the financial statements. Same for
`legal_proceedings` (171 characters, points to Note 12). NVIDIA
incorporates Item 8 and Item 3 by reference to other parts of the document,
instead of putting the content under the Item's own heading — perfectly
legal and common at the SEC, but invisible to a parser that sections by
Item headings.

## Why it matters

`financial_statements` is in `PERSONA_SECTIONS` for 4 of the 5 personas
(audit_firm, investment_firm, investment_bank, treasury). For a filing
ingested this way, those queries filter on a section with a single, useless
chunk. It isn't an error — it's a poor answer with no signal that anything
is missing.

The fixed corpus (Apple/Microsoft/Google) doesn't show the problem: there,
`financial_statements` has ~3,100 chunks in total, so the content really is
under the Item heading. It's a difference between filers — the same class
of bug as Google's (titles without a space after the period), just this
time the failure is silent.

## What was NOT done

`validate_sections` checks presence, not size. A minimum-length threshold
per section would catch this case, but would also reject legitimate
filings — the right threshold can't be guessed from a single example. To be
decided once a few more companies outside the fixed corpus have been
ingested, not now.

Properly following cross-references ("see Note 12") would mean a different
tier of parser than heading-based sectioning — out of scope for now.
