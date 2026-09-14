# The Sept 12 build-spec.md asked to reintroduce 2 already-fixed critical bugs

## What happened

A new version of `build-spec.md` gave "complete" code for `retrieve_multi`
and `verify_context` that didn't account for the fixes already applied that
day (documented in `verify-context-infinite-retry-loop.md` and
`retrieve-multi-no-entity-fallback.md`):

- **`verify.py`**: the given code reverted to the original version —
  `verify_context` as a routing function that mutates `state["retry_count"]`
  directly. Applying it would have reintroduced the infinite
  retrieve<->rerank loop (already confirmed: 300+ iterations, stopped only
  by an external Google rate limit).
- **`retrieve.py`**: the `retrieve_multi` given explicitly had no fallback
  onto `KNOWN_ENTITIES` when `extract_entities` finds no company — exactly
  the bug confirmed live ("risk factors 2024 vs 2025" with no answer).

**These two pieces of code were NOT applied.** The new structure given for
`retrieve_multi` (the `base_filter` pattern, `limit=10`, `top_k=5`) was
adopted, but with the fallback kept on top of it.

## Other discrepancies found and verified directly (not assumed)

- `gemini-embedding-2` (requested again in `embed.py`/`qdrant_setup.py`/`cost.py`) —
  retested directly, still 404. Stayed on `gemini-embedding-001` (already in
  production, 8250 real vectors).
- `gemini-3-flash` (newly requested for classify+generate) — tested directly,
  404, doesn't exist. Replaced with `gemini-3-flash-preview`, verified
  working.
- `gemini-3.1-flash-lite` (requested for contextual retrieval) — tested
  directly, works. Applied as given (a real improvement, not a conflict).

## When to revisit

Any future version of the spec that gives "complete" code for `verify.py`
or `retrieve.py::retrieve_multi` must be compared line by line against the
current version in the repo before being applied — don't assume a "newer"
version of the document necessarily reflects fixes already made in the
code. Always verify Gemini/Vertex models with a real call before adopting
them from a document, no matter how confident it sounds ("verified",
"confirmed") — the lineup changes often and the document itself can be
wrong or stale.
