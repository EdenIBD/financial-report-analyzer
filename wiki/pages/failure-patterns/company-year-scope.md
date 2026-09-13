# Company and fiscal-year scope was lost before retrieval

Observed on 2026-09-13: a request for NVIDIA's 2023 report attributed Google 2025 figures to NVIDIA and cited NVIDIA 2026. A separate Taco Bell Funding, LLC query searched unrelated companies after resolution returned no match.

## Causes

1. `retrieve_single` applied section filters only. `retrieve_multi` applied company filters but no year filter.
2. Dynamic ingestion checked whether a ticker existed, not whether the requested fiscal-year filing existed.
3. Company extraction ran only when no existing company matched. Mixed known/unknown comparisons could omit the unknown company.
4. An unresolved registrant was silently dropped, making a company-specific query indistinguishable from a general corpus query.
5. Downloads selected the latest recent 10-K. They did not search historical submissions or verify a requested fiscal year.

## Repair

Resolve all named companies and explicit years before retrieval. Store the resolved tickers, years and allowed document IDs in LangGraph state; apply these filters to dense and keyword calls on both routes and retries. Request the exact fiscal year when missing, search SEC submissions shards, and validate XBRL CIK/form/fiscal-year metadata. A calendar `reportDate` year is only a candidate filter.

If resolution or required ingestion fails, route to abstention with zero source chunks. One failed ingestion attempt also counts against the per-query limit. Dynamic filings are `processing` until all chunk writes return successfully. Existing installations need `scripts/migrate_ingestion_status.sql`.

The SEC ticker catalog is not a fixed three-company allowlist, but it does not cover every registrant. Taco Bell Funding, LLC was unresolved in the current catalog. The application must not replace it with Yum!, or treat a parent's consolidated 10-K as a standalone subsidiary report. SEC's [Yum! FY2023 filing](https://www.sec.gov/Archives/edgar/data/1041061/000104106124000011/yum-20231231.htm) describes the entity under securitization notes; this is not proof of an independently filed Taco Bell Funding 10-K.

## Verification

- `tests/test_dynamic_ingestion.py`: existing ticker/missing year, mixed companies, unresolved registrant, bounded failed attempts and FY-prefixed years.
- `tests/test_query_scope.py`: dense/keyword filters on both retrieval routes and fallback, actual compiled-graph retry, empty-context abstention.
- `tests/test_edgar_year_selection.py`: historical shard, XBRL year vs calendar report date, unavailable year and SEC errors.
- `frontend/e2e/query-scope.spec.ts`: historical evidence, explicit unresolved-registrant message, no unrelated citations, reference eagle layout.
- Live results: [[evaluation-2026-09-13]]. Five scope cases pass after a temporary external DNS failure in the first attempt. Both attempts are retained.

## Limits

Relative-date resolution, company-specific year pairings, registrants without tickers and quarter-level 10-Q identity remain incomplete. Correct source scope alone does not guarantee correct financial interpretation. Low rerank scores can still lead to generation from limited, correctly scoped context.
