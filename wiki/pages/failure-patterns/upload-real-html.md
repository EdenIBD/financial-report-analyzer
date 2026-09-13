# Upload failures hidden by synthetic fixtures

2026-09-13. Reproduction corpus and exact source URLs: `eval/upload-fixture-manifest.json`; before/after stage results: `eval/results/upload-matrix-{before,after}.json`.

- Microsoft FY2024 10-K: metadata regex expected text immediately after the DEI opening tag. Actual DocumentType, TradingSymbol and FiscalYear values are wrapped in `span` elements. Winmark FY2024 Q3 uses a nested `b` for DocumentType. Both were rejected before section parsing. Replaced regex extraction with BeautifulSoup text extraction (already a sec-parser dependency, now declared explicitly). Attribute ordering, quoting and nested formatting are handled by the HTML parser.
- Winmark's real headings use `ITEM 1:` rather than `ITEM 1.`. Once metadata was fixed, all six categories still failed. The Item boundary regex now accepts either punctuation; Part I/II disambiguation and all six required categories are unchanged.
- YUM FY2015 (filed 2016), directly downloaded and user-saved, has no DEI facts. BOOM 2018 Q3 also has none. These remain unsupported; the error now explains the inline-XBRL requirement instead of calling a genuine older filing invalid. Legacy cover-page inference is not implemented.
- Upload decoding previously used UTF-8 with `errors=ignore`, silently discarding bytes. The decoder now honors BOM/HTML encoding and rejects replacement-character decoding. Real-derived metadata fixtures exercise UTF-8 BOM, UTF-16 and Windows-1252.
- A failed polling request left the UI's one-shot timer unscheduled: status could remain processing forever after transient network failure. Repeating polling now recovers and clears the stale error; ready uploads refresh the sidebar. Playwright aborts the first status request to reproduce this deterministically.
- Live Winmark upload appeared in `/corpus` while its upload row was still `processing`. Upload used `upsert_filing` (default ready) and omitted the dynamic pipeline's publication lifecycle. Upload now takes the same document lock and marks the filing processing until indexing completes. Interrupted jobs still require retry; there is no durable queue.

A real Chrome **Save Page As / complete HTML** of Apple FY2023 retained metadata and passed all six categories. Its bytes differ from the direct download, as expected. A BOM variant is explicitly labelled derived, not an original SEC download. Trimming parser fixtures does not establish coverage or faithfulness of the full filing; full documents were also evaluated separately.

Known limitation retained: incorporated-by-reference financial statements may pass presence validation while containing little substantive text. Do not relax the six-category requirement to hide parser failures.
