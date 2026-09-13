# Real filing upload evaluation — 2026-09-13

Ten distinct SEC filings; additionally one existing user browser save, one new Chrome save and one explicitly derived BOM variant. Parsing checks do not measure financial-answer faithfulness.

| Filing / variant | Form | Result | Canonical categories |
|---|---|---|---|
| aapl_2023_10k | 10-K | PASS | 6/6 |
| msft_2024_10k | 10-K | PASS | 6/6 |
| googl_2023_10k | 10-K | PASS | 6/6 |
| nvda_2023_10k | 10-K | PASS | 6/6 |
| yum_2015_10k | 10-K | Unsupported: no inline XBRL | 0/6 |
| lway_2023-12-31_10k | 10-K | PASS | 6/6 |
| wina_2024-09-28_10q | 10-Q | PASS | 6/6 |
| boom_2018-09-30_10q | 10-Q | Unsupported: no inline XBRL | 0/6 |
| aapl_2026-06-27_10q | 10-Q | PASS | 6/6 |
| tsla_2025-12-31_10k | 10-K | PASS | 6/6 |
| yum_2015_user_browser_save | 10-K | Unsupported: no inline XBRL | 0/6 |
| aapl_2023_browser_save | 10-K | PASS | 6/6 |
| aapl_2023_utf8_bom | 10-K | PASS | 6/6 |

Microsoft nested spans and Winmark nested bold tags failed metadata detection before the fix. Winmark then exposed colon-delimited Item headings. All eight modern original filings now pass all six categories. The two legacy originals and the user-saved legacy copy remain explicitly unsupported.

Apple FY2023 saved with Chrome’s native Save Page As retains DEI metadata and passes. A UTF-8 BOM variant also passes. The declared Windows-1252 YUM save is retained as an independent legacy sample; metadata rejection is caused by absent DEI, not assumed encoding corruption.

Detailed stage results and provenance: `eval/results/upload-matrix-before.json`, `eval/results/upload-matrix-after.json`, `eval/upload-fixture-manifest.json`. Full HTML stays in ignored local data; committed excerpts preserve real metadata/heading structures.

Reproduce from project root: `python -m eval.run_upload_matrix`. Live upload tests (paid): `cd frontend && RUN_LIVE_UPLOAD=1 npx playwright test e2e/upload-live.spec.ts`.

Live browser upload: Winmark FY2024 10-Q reached ready with 122 chunks; the legacy YUM upload returned the explicit unsupported-inline-XBRL message. Both used the real API, parser and database.
