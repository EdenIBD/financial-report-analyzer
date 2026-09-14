# Unit tests by module

93 total test cases (91 passed, 2 skipped) across 16 files under `tests/`. Source: `eval/results/unit-tests.xml`; full per-test list at [[unit-test-inventory]].

## test_chunk — 4 tests
`src/ingestion/chunk.py::chunk_section`. Text chunking: short text stays a single chunk, long text splits into multiple chunks, consecutive chunks overlap, empty text produces no chunks.

## test_citations — 7 tests
`src/agent/citations.py::inspect_citations` and `src/agent/nodes/generate.py::generate_answer`. Citation-format validation: full `[DOC_ID_section_N]` identifiers are required (6 parametrized cases covering valid, bare-number, and mixed valid/invalid citations), plus one case confirming an invalid citation makes the graph abstain while still preserving the generation cost already incurred.

## test_cost — 4 tests
`src/storage/cost.py`. Cost calculation: known-model pricing lookup, unknown models cost zero, input and output tokens are both counted, and the pricing dict's keys match the real `CLASSIFY_MODEL`/`GENERATE_MODEL`/`CONTEXT_MODEL` constants (so they can't silently drift apart).

## test_cost_trends — 7 tests
`scripts/cost_trends.py`. Aggregation helpers behind [[cost-trends]]: average of an empty list is zero, mean computation, grouping by persona and query_type, skipping rows with a null persona/query_type, the query-type cost-ratio insight (both with and without enough data), and Markdown pipe-table rendering.

## test_detect — 4 tests (1 skipped)
`src/ingestion/detect.py::detect_filing_metadata`. Filing-metadata detection: rejects HTML without DEI tags, rejects an unsupported document type, and detects metadata on real filings (AAPL 10-K passes; the AAPL 10-Q sample is skipped — missing local fixture file).

## test_documents — 10 tests
`src/api/documents.py::process_uploaded_document`. Upload pipeline: rejects a file without valid metadata, rejects one missing required sections, a full success path indexes into the global corpus and marks it ready, real-markup metadata/section extraction on MSFT and Winmark filings, nested single-quoted attributes with whitespace, decoding that preserves text across UTF-8-SIG/UTF-16/Windows-1252, and a clear error message for legacy filings missing inline XBRL.

## test_dynamic_ingestion — 14 tests
`src/agent/nodes/check_entity.py::check_entity_exists` and `src/ingestion/pipeline.py::resolve_company/resolve_ticker`. Resolving an unknown company at query time: ticker resolution (valid/nonexistent), company-name matching (exact match preferred over a longer prefix, minimum name length for prefix matching, suffix/punctuation tolerance, periods inside a name), blocking the corpus on a resolution failure, triggering ingestion for a missing year on an already-known company, checking known and unknown companies together, skipping ingestion when the filing is already complete, abstaining when a registrant can't be resolved and no other sources exist, counting a failed attempt against the per-query ingestion limit, keeping general questions in general scope, and distinguishing a year range from a comparison.

## test_edgar_year_selection — 4 tests
`src/ingestion/pipeline.py::download_filing`. EDGAR submission-year selection: finding a requested year in an older submissions shard, treating `reportDate` as distinct from the actual fiscal year, not silently substituting the latest filing when the requested year is unavailable, and propagating SEC API failures without substitution.

## test_fusion — 2 tests
`src/retrieval/fusion.py::reciprocal_rank_fusion`. Merges and ranks dense + keyword result sets, and respects the `top_k` cutoff.

## test_parse — 9 tests (1 skipped)
`src/ingestion/parse.py` (`ITEM_TITLE_RE`, `PART_TITLE_RE`, `parse_filing`). Section-title regex matching (Apple-style "number + title", Google-style "number only, no trailing space", letter suffixes like "1A", rejecting unrelated text containing the word "item", 10-Q Part-title matching) and full canonical-section extraction on real AAPL/GOOGL/MSFT 10-K filings; disambiguating Part I vs. Part II Item 1 on a 10-Q is skipped — missing local fixture file.

## test_query_log — 2 tests
`src/storage/query_log.py::log_query_to_postgres`. Logs the expected values to Postgres, and handles a missing classification without crashing.

## test_query_scope — 7 tests
`src/agent/nodes/retrieve.py`, `src/agent/nodes/generate.py`, `src/agent/graph.py`. The company/year/document scope fix from [[company-year-scope]]: filters survive both `retrieve_single`/`retrieve_multi` routes and a retry (4 parametrized cases), a blocked scope short-circuits the graph straight to abstention, empty context abstains without calling the LLM, and the scope survives a real compiled-graph stream through the verification retry.

## test_retrieve_sections — 6 tests
`src/agent/nodes/retrieve.py` (`PERSONA_SECTIONS`, `FALLBACK_SECTIONS`, `extract_entities`, `retrieve_multi`). Every persona has a non-empty section list, the fallback list is non-empty, entity extraction matches against the real corpus (including a brand name not present in the registrant's legal name), single-letter tickers aren't matched inside unrelated words, and `retrieve_multi` falls back to all known companies when no entity is named (see [[retrieve-multi-no-entity-fallback]]).

## test_sections — 3 tests
`src/ingestion/sections.py` (`CANONICAL_SECTIONS`, `validate_sections`). 10-K and 10-Q map to the same required canonical categories, validation passes when everything required is present, and raises when something is missing.

## test_tokenizer — 3 tests
`src/ingestion/tokenizer.py::count_tokens`. Empty string has zero tokens, longer text has more tokens, and a known short phrase has an exact expected token count.

## test_verify — 7 tests
`src/agent/nodes/verify.py` (`verify_context`, `route_after_verify`). The routing fix from [[verify-context-infinite-retry-loop]]: enough good chunks generates an answer, insufficient chunks retries and sets the fallback-sections flag, insufficient chunks on a comparison routes to `retrieve_multi`, hitting the max retry count forces `generate_answer` anyway, `verify_context` appends a reasoning-trace entry, retry_count actually reaches its limit and stops (proving the node-vs-routing-function mutation bug can't recur), and the trace doesn't promise a retry when the router is actually about to generate.
