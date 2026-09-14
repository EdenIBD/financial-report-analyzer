# gemini-embedding-2 returns 404 on Vertex AI, despite appearing in the catalog

## What happened

`src/retrieval/embed.py` used `model="gemini-embedding-2"` (marked
"confirmed" in build-spec.md). On the first real call,
`embed_content(model="gemini-embedding-2", ...)` in Vertex AI mode
(`genai.Client(vertexai=True, project=..., location="us-central1")`), the
API responded:

```
404 NOT_FOUND: Publisher model
`projects/<project>/locations/us-central1/publishers/google/models/gemini-embedding-2`
was not found or your project does not have access to it.
```

`client.models.list()` does in fact list
`publishers/google/models/gemini-embedding-2` as an existing model — but
listing doesn't guarantee the model is actually callable for the current
project/region (possibly preview/allowlisted, unclear from the API
response).

## Fix applied

Tested `gemini-embedding-001` directly (same project, same `us-central1`
region) — it works, and returns exactly **3072 dimensions**, identical to
what was already configured in `qdrant_setup.py`
(`VectorParams(size=3072)`). Changed `embed_document`/`embed_query` in
`src/retrieval/embed.py` to use `gemini-embedding-001`. No other code
change needed — the `embed_content(..., config={"task_type": ...})`
interface is identical.

## When to revisit

If the model becomes unavailable again, or pricing/versioning changes
again, verify empirically first with a real call (`embed_content`) before
assuming a model name listed in the catalog is actually callable —
`client.models.list()` is not a guarantee of real access.
