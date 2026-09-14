# Contextual retrieval: the situating sentence names the wrong company on ~28% of the corpus

Date: 2026-09-12
Discovered: by actually reading the text of retrieved chunks in the new
"Show retrieved chunks" UI panel, not by assuming contextual retrieval had
gone well. One MSFT_2026 chunk showed the context sentence "This fragment
is from the Annual Report of **Apple Inc.**" — clearly wrong, a different
company.

## Real scope (measured, not estimated)

Counting only the context sentence (the first line, before the `\n\n`
separator that splits the context from the actual fragment), not the whole
chunk text (which can legitimately mention a competitor in Item 1A):

| Ticker | Chunks with the wrong company in context | Total chunks | % |
|---|---|---|---|
| GOOGL | 927 (675 "Apple", 252 "Microsoft") | 2060 | **45.0%** |
| MSFT | 1204 (1089 "Apple", 115 "Alphabet") | 3697 | **32.6%** |
| NVDA | 74 | 347 | 21.3% |
| AAPL | 235 (213 "Microsoft", 22 "Alphabet") | 2493 | 9.4% |
| **Total** | **2440** | **8597** | **28.4%** |

On top of that, 146 chunks (concentrated mostly in NVDA) had the context
sentence entirely replaced with meta-commentary — the model answered with
"Here are two options for situating the fragment: **Option 1 (Specific):**
..." instead of a single direct sentence, and all of that text was stored
and embedded as part of the chunk.

## Root cause — two separate bugs in `src/ingestion/contextual.py`

1. **`add_context(chunk_text, doc_id, section)` received `doc_id` as a
   parameter, but the prompt never used it.** The model had to guess the
   company and year purely from the first 300 characters of the fragment.
   On fragments that start with generic text (legal boilerplate,
   definitions, tables with no company name in the first lines), the model
   guessed, and often guessed wrong — probably defaulting to Apple as an
   "implicit" 10-K example from its training data.
2. **Even after doc_id was passed explicitly into the prompt,
   `gemini-3.1-flash-lite` still didn't follow a conversationally phrased
   instruction** — it answered with "Here are two options..." and
   explanations instead of a single direct sentence. The original prompt
   ("Generate 1-2 sentences...") left room for interpretation; the model
   interpreted it as a brainstorming request.

## Why it went unnoticed until now

Retrieval filtering (`retrieve.py`) uses the real `company` field from the
Qdrant payload (the ticker, populated correctly by the pipeline,
independent of the generated context sentence), not the generated text. So
**retrieval results were not affected** — a Microsoft query still found the
correct MSFT chunks, correctly filtered by company. The defect was only
visible if you actually read a retrieved chunk's full content, which the
UI didn't expose in an easily noticeable way before today.

Real impact, nonetheless:
- **Embedding quality**: the context sentence is prepended BEFORE embedding
  (`embed_document(contextualized)`), so an MSFT chunk's vector carries a
  false signal toward "Apple Inc." — this may dilute or slightly shift
  dense-search semantic similarity (not measured how much).
- **User trust**: the "Show retrieved chunks" panel now shows the correct
  filing text, but with an opening sentence that contradicts the
  company/year label next to it — confusing, even though the content below
  is correct.

## Fix applied (prevents future occurrences, doesn't repair history)

`add_context` now receives `doc_id` explicitly in the prompt and a strict
output instruction (a single sentence, use exactly the given identifier, no
alternatives). Verified directly, live, on 4 different companies — all
correct, no variants, no guessing:

```
MSFT_2026 -> 'This fragment is from filing "MSFT_2026", section "mdna".'
GOOGL_2024 -> 'This fragment is from filing "GOOGL_2024", section "risk_factors".'
AAPL_2023 -> 'This fragment is from filing "AAPL_2023", section "financial_statements".'
NVDA_2026_10K -> 'This fragment is from filing "NVDA_2026_10K", section "controls_procedures".'
```

The result is literal (an echo of the identifier, not natural prose with
the company name spelled out) — correctness guaranteed in exchange for a
less natural phrasing. Any new ingestion (upload, dynamic ingestion)
already uses the fix; the 2440 + 146 chunks already ingested remain
unchanged pending an explicit remediation decision (estimated cost: ~$0.37
in LLM calls, but ~3 hours of sequential runtime at the observed pace of
~14 chunks/minute — time, not cost, is the real constraint).

## Update — 2026-09-13

Canonical-section remediation has been checked, including fresh parsing of all 16 drifted Microsoft sections and full PostgreSQL/Qdrant text equality. The detector's remaining 159 flags are not 159 verified errors: 158 are legacy Item-category chunks, while the canonical NVIDIA flag correctly mentions a Microsoft agreement found in its source body. See [[msft-parse-drift-during-remediation]] and [[evaluation-2026-09-13]]. Historical percentages on this page describe the pre-repair heuristic sample, not current retrieval accuracy.
