# langsmith_trace_id was always null in the /query response

## What happened

`src/api/tracing.py::get_current_run_id()` uses `get_current_run_tree()`
from `langsmith.run_helpers`, called inside `handle_query` (`main.py`)
**after** `graph.invoke()` had already finished. LangSmith's run context
(populated via Python contextvars) only exists while code is running
*inside* a traced call — once that call finishes and unwinds the stack, the
context is gone, so `get_current_run_tree()` always returns `None` when
called "after the fact", even though `graph.invoke()` itself was correctly
traced.

Verified empirically: LangGraph automatically traces EVERY node in the
graph (classify, retrieve_single, rerank...) in LangSmith when
`LANGCHAIN_TRACING_V2=true` — so the underlying infrastructure exists and
works (confirmed with a direct call to the LangSmith API,
`GET /api/v1/runs/query`, which shows real runs with classification,
retrieved chunks, cost). The problem was only at the `handle_query` level,
which had no active trace context of its own in which to "catch" the id.

## Fix applied

Added `@traceable(name="handle_query")` from the `langsmith` package on the
`handle_query` function — this creates an active run-tree for the whole
execution of the function, inside which `get_current_run_tree()` (called
after `graph.invoke()`, still inside the decorated function) finds the real
id. Tested directly: without the decorator, `run_tree` is `None`; with the
decorator, it's a real UUID.

## When to revisit

If other functions are added that call `graph.invoke()` from outside
`handle_query` (e.g. a separate CLI script) and need the trace_id, they
must be decorated the same way with `@traceable`, otherwise
`get_current_run_id()` will return `None` there too.
