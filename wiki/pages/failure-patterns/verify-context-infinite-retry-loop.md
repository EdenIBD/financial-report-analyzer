# verify_context as a routing function loses its state mutations -> infinite loop

## What happened

`verify_context` (code given by the spec) mutates `state["retry_count"] += 1`
and `state["use_fallback_sections"] = True` directly, then returns a string
naming the next node. It was wired into the graph via
`add_conditional_edges` (a routing function), not via `add_node`.

LangGraph does not persist state mutations made inside a routing function —
only the returned value (the node name) matters. So `retry_count` always
stayed at the value read from state (often 0), the `retry_count >= 2`
condition never became true, and the graph looped forever:
`retrieve -> rerank -> verify_context -> retrieve -> ...`.

**Didn't manifest until now** because `rerank()` always failed first (GCP
Discovery Engine not enabled / `{project}` not substituted) — the exception
stopped everything before ever reaching `verify_context`. Once the
reranker was fixed, the bug became immediately visible: a real query ran
for over 120 seconds, 300+ iterations, stopped only by Google's external
rate limit (`ResourceExhausted` on the Rank Service).

## Fix applied

Split into two functions (`src/agent/nodes/verify.py`):
- `verify_context(state) -> state`: now a real NODE (`add_node`), mutates
  the state and returns it — mutations are persisted correctly.
- `route_after_verify(state) -> str`: a pure routing function (only reads
  the state already updated by the node), used with
  `add_conditional_edges`.

`src/agent/graph.py`: `rerank -> verify_context` (plain edge) ->
`add_conditional_edges("verify_context", route_after_verify, ...)`.

## When to revisit

Any function used directly as an argument to `add_conditional_edges` must
NOT mutate state — it should only read it and return a node name.
Mutations happen exclusively in nodes added with `add_node`.
