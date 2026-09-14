# response.content is not always a string — gemini-pro-latest returns structured blocks

## What happened

`generate_answer` did `state["answer"] = response.content`, assuming
LangChain's response is always a plain string. With `gemini-pro-latest`,
`response.content` can be a list of structured blocks
(`[{"type": "text", "text": "...", "extras": {"signature": "..."}}]`), not a
string — likely related to a "thinking"/signature mechanism of the model.

FastAPI validated the `/query` response against `QueryResponse` (which
declares `answer: str | None`), so any answer the LLM successfully
generated raised a `ResponseValidationError` and `/query` returned a
**500 Internal Server Error** — a good, correctly generated answer was
being thrown away at the last step.

## Fix applied

Replaced `response.content` with `response.text` — the LangChain property
that robustly extracts the text regardless of whether `content` is a
string or a list of blocks (verified directly: works for both forms).

## When to revisit

Any other place that reads `.content` directly off a LangChain response
(not just `generate.py`) should use `.text` instead, so it doesn't depend
on the exact shape a given model returns.
