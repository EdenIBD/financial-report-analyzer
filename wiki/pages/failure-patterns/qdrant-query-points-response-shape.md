# qdrant_client.query_points() returns a QueryResponse, not a list

## What happened

The code given by the spec for `retrieve_single`/`retrieve_multi`
(`src/agent/nodes/retrieve.py`) passed the result of
`qdrant_client.query_points(...)` directly into `reciprocal_rank_fusion`,
which does `for rank, r in enumerate(dense_results): scores[r.id] = ...` —
assuming `dense_results` is a list of objects with `.id`/`.score`.

In reality, `query_points()` returns a `QueryResponse` (a pydantic model
with a single field, `points`). Iterating directly over a pydantic model
yields `(field_name, value)` tuples, not the actual points — hence:

```
AttributeError: 'tuple' object has no attribute 'id'
```

The error was completely invisible from `/query` (it only responded
`status: "error"`, with no detail, because `handle_query` catches any
exception generically) — found by running `graph.invoke()` directly,
outside the try/except.

## Fix applied

Added `.points` to each of the 4 `query_points()` calls (2 in
`retrieve_single`, 2 in `retrieve_multi`) before passing them into
`reciprocal_rank_fusion`.

## When to revisit

Any other place that calls `qdrant_client.query_points()` or `search()`
directly must be checked the same way — don't assume the response shape
without explicitly reading `.points`.
