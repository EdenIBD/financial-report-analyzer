# gemini-2.5-flash / gemini-2.5-pro return 404 for a new account

## What happened

`src/agent/nodes/classify.py` (`CLASSIFY_MODEL = "gemini-2.5-flash"`) and
`src/agent/nodes/generate.py` (`GENERATE_MODEL = "gemini-2.5-pro"`) — initially
chosen with a `# TODO: confirm the model` comment — failed on the first real
call through `ChatGoogleGenerativeAI`, with:

```
404 NOT_FOUND: This model models/gemini-2.5-flash is no longer available to new
users. Please update your code to use models/gemini-3.6-flash...
```

Same as with `gemini-embedding-2` (see the separate failure pattern), the
model **appears in the `client.models.list()` catalog**, but isn't actually
callable — this time the error itself states the reason: retired for new
accounts.

The error surfaced in the graph as `status: "error"` with no detail, because
`handle_query` catches any exception from `graph.invoke()` in a generic
`except Exception:`, without logging the message (code given exactly as
specified). Diagnosed by running `graph.invoke()` directly, outside the
try/except, to see the real traceback.

## Fix applied

Tested directly (`generate_content`, not just `models.list()`) several
models available through the same API key:

| Model | Result |
|---|---|
| gemini-2.5-flash | 404 (retired) |
| gemini-2.5-pro | 404 (retired) |
| gemini-3.6-flash | OK |
| gemini-flash-latest | OK |
| gemini-pro-latest | OK |
| gemini-3.1-pro-preview | OK |

Chose `gemini-flash-latest` (classify) and `gemini-pro-latest` (generate) —
"latest" aliases instead of pinned versions, so the same problem doesn't
recur on the next model retirement.

## When to revisit

`handle_query` silently swallows any exception from the graph — if "error"
responses with no answer show up again, run `graph.invoke()` directly
(without try/except) to see the real traceback, don't assume the cause.
