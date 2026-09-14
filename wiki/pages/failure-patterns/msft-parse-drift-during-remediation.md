# MSFT parsing has drifted since original ingestion — discovered mid-remediation, may have introduced misalignment

Date: 2026-09-13
Context: while running `scripts/fix_contextual_sentences.py` (the remediation
for [contextual-retrieval-wrong-company.md](contextual-retrieval-wrong-company.md)),
the script failed with "index N no longer exists after re-chunking" for ~29
of the remaining 225 MSFT chunks in the last batch. Investigating why
uncovered a broader, older issue, independent of the bug being fixed.

## What was found

Re-parsing the raw HTML (`data/raw/MSFT_*.html`, unmodified) with `parse.py`
**in its current state**, the extracted text for MSFT's canonical sections
is shorter than at original ingestion — somewhere, in one of the successive
edits to `parse.py` across earlier sessions (the project has no git history
to consult), MSFT's section boundaries shifted.

| Filing | Section | Stored chunks | Chunks on re-parse today | Diff |
|---|---|---|---|---|
| MSFT_2021 | financial_statements | 305 | 304 | -1 |
| MSFT_2021 | risk_factors | 149 | 143 | -6 |
| MSFT_2023 | financial_statements | 273 | 265 | -8 |
| MSFT_2023 | risk_factors | 145 | 138 | -7 |
| MSFT_2024 | controls_procedures | 23 | 21 | -2 |
| MSFT_2024 | financial_statements | 281 | 273 | -8 |
| MSFT_2024 | mdna | 136 | 127 | -9 |
| MSFT_2024 | risk_factors | 159 | 146 | -13 |
| MSFT_2025 | controls_procedures | 18 | 16 | -2 |
| MSFT_2025 | financial_statements | 252 | 238 | -14 |
| MSFT_2025 | mdna | 113 | 104 | -9 |
| MSFT_2025 | risk_factors | 141 | 128 | -13 |
| MSFT_2026 | controls_procedures | 18 | 16 | -2 |
| MSFT_2026 | financial_statements | 255 | 244 | -11 |
| MSFT_2026 | mdna | 126 | 117 | -9 |
| MSFT_2026 | risk_factors | 166 | 152 | -14 |

**GOOGL, AAPL and NVDA do not have this problem** — re-parsing them today
produces exactly the same chunk count as at ingestion, across all canonical
sections. Only MSFT is affected, across all 5 filings.

For MSFT_2023/financial_statements, the first index where the newly
regenerated chunk differs from the stored one is **index 26 of 273** — so
it's not just a problem at the tail of the section, the difference starts
early and propagates.

## Why it matters for the ongoing remediation

`fix_contextual_sentences.py` repairs an existing chunk_id by re-parsing its
section and taking the raw text at that same `chunk_index` from the fresh
result. The assumption (valid for GOOGL/AAPL/NVDA, verified) was that
re-parsing today reproduces the original segmentation identically. **For
MSFT, that's false** — the script had already rewritten the following MSFT
chunks with text coming from a segmentation that is no longer guaranteed to
line up with their neighboring chunks (left over from the old, longer
segmentation):

| Filing | Affected sections, chunks already rewritten |
|---|---|
| MSFT_2021 | financial_statements 135, mdna 43, risk_factors 46, controls_procedures 6 |
| MSFT_2023 | financial_statements 117, mdna 60, risk_factors 42, controls_procedures 10 |
| MSFT_2024 | financial_statements 118, mdna 42, risk_factors 57, controls_procedures 8 |
| MSFT_2025 | financial_statements 112, mdna 33, risk_factors 56, controls_procedures 8 |
| MSFT_2026 | financial_statements 122, mdna 40, risk_factors 55, controls_procedures 7 |

Note: "rewritten" doesn't necessarily mean "wrong" — it means the chunk
boundaries may have shifted, so a section's full chunk set (the rewritten
ones + the ones left untouched at the tail, with the old segmentation)
could now have overlaps or gaps relative to the section's full text. It
hasn't been verified yet whether there's a real content gap or whether the
effect is benign (just slightly shifted boundaries, no net loss). The
remediation script was **stopped** at this point, without continuing over
MSFT, specifically to avoid deepening a potential problem before a
decision was made.

## What was not touched

`legal_proceedings` and `market_risk` for MSFT do NOT appear in the drift
table — those were repaired normally, with no risk of misalignment.
Likewise, everything repaired for GOOGL/AAPL/NVDA is verified correct and
safe.

## Remediation options (decision pending)

1. **A full, clean re-ingestion, only for the affected (doc_id, section)
   pairs** in MSFT: delete the existing chunks from Postgres+Qdrant for
   those pairs, re-parse + re-chunk + re-contextualize + re-embed
   everything from scratch, with new, consistent 0..N indices. Safest, but
   means redoing the ~600 MSFT chunks already touched plus the rest of the
   section (not just the initially affected ones) — comparable in
   time/cost to the remediation already done (~3 hours).
2. Accept the current state as is, documented as a known, unquantified risk
   (possible minor gaps/overlaps in a few MSFT sections), at no further
   cost — but without knowing for sure whether any real content fragment
   was lost from the corpus.
3. First investigate whether there's an actual content gap (comparing the
   old section's full text, reconstructed from the stored chunks before
   they were rewritten, against the new one) — but the chunks already
   rewritten have already lost their old content (no backup exists), so the
   comparison can only be done on chunks still untouched
   (legal_proceedings, market_risk, and the unfixed tail of the other
   sections).

**Decision made (2026-09-13): option 1** — a full, clean re-ingestion, only
for the (doc_id, section) pairs listed in the table above.

## Operational incident: two interruptions, one produced a real content gap

`scripts/reingest_msft_drifted_sections.py`, the initial version, did
**delete first, insert after** per section (symmetric to how any "clean"
migration looks on paper). On this machine, however, Docker Desktop stopped
twice during the run (likely cause: the laptop sleeping, not a code error)
— each time, `docker compose exec` reported "completed, exit code 0"
through the notification system, a false positive (the process was killed
along with the Docker daemon, it did not finish normally).

The real consequence of the delete-then-insert ordering: on the second
interruption, the job had died midway through the insert for
`MSFT_2021/risk_factors` — the old section (149 chunks) had already been
fully deleted, and the new insert had only reached 108 of a 143 target. For
a few hours (until the next check), that section had a **real content
gap**: 35 chunks of real financial text, unavailable to retrieval, not
just mislabeled — a worse regression than the bug the remediation was
trying to fix.

**Lesson and fix applied**: the order was reversed — **insert first
(fully), delete after** (`delete_stale_old_style_chunks`, called only after
the new chunk set is fully inserted). The old and new chunks have different
`chunk_id` formats (`{doc_id}_Item8_{n}` old vs.
`{doc_id}_financial_statements_{n}` new), so they don't overwrite each
other — they can coexist temporarily without creating gaps. Retrieval
filters on the `section` column, not on `chunk_id`, so temporarily
coexisting segmentations don't affect query correctness, only add a few
redundant chunks until the cleanup step. An interruption partway through,
with this ordering, leaves at most redundant old content — never a gap.

## Final resolution (2026-09-13)

The clean re-ingestion for all 16 (doc_id, section) pairs in the table
above finished successfully: 819 old chunks deleted, 761 new ones indexed,
total cost $0.05. Verified directly: all 16 sections now have exactly the
chunk count expected from the current parser, all with `chunk_id` in the
new, consistent format — no remaining misalignment.

**A fourth optimization**: the script unconditionally repeated every
section on each restart, even ones already finished successfully — by the
fourth restart, that meant redoing hours of already-correct work before
reaching new work. Added `already_done()`: checks locally (no LLM call)
whether a section already has exactly the target chunk count in the new
format, and skips it if so. Result: the final restart took 13 minutes (only
the 6 remaining sections, not all 16), not hours.

**Full-corpus recheck** after remediation: the 2440+146 chunks initially
affected dropped to 159 remaining — but almost all (158/159) are in
orphaned sections (`Item1`, `Item2`, `Item5`), leftovers from before the
migration to the canonical taxonomy, which `retrieve.py` no longer ever
filters on (`PERSONA_SECTIONS`/`FALLBACK_SECTIONS` use only the 6 canonical
categories). Those chunks are **unreachable at retrieval, regardless of
their content** — fixing their context sentence wouldn't change any real
system behavior, so it wasn't done. The bug is fully resolved for
everything that matters functionally; the 158 orphaned chunks remain a
separate cleanup item (to delete, not repair) if ever decided.

**A third, self-inflicted interruption**: while the re-ingestion job was
running (with the ordering already fixed to insert-first), a
`docker compose up -d --build frontend` was run for a design update — and
`api` was restarted along with it (compose reconciles the whole project,
not just the requested service), again killing the exec with SIGKILL (exit
137). A direct check afterward confirmed the insert-first design had done
its job: no content gap, just sections left partially completed (e.g.
MSFT_2025/mdna had 151 chunks — 113 old + 38 new, coexisting, not
overwritten). Additional lesson: **no `docker compose up`/`--build`, on any
service, while a data-migration exec is running in the background** — not
just "don't rebuild the service running the exec", but the entire compose
project.

**General lesson for data-migration work on this machine**: "job
completed" notifications from long-running `docker compose exec` processes
are not trustworthy if Docker Desktop can stop itself (sleep) — verification
must always be done directly against the database/Qdrant after completion,
not just from the reported exit code. Second lesson: any migration script
that modifies production data should be interruption-resistant by design
(insert-first, delete-after, or atomic transactions), not just "usually
runs to completion".

## Independent verification — 2026-09-13

The completed repair was checked against actual stored data, not the background-task notification. All 16 targeted document/section pairs have exactly the fresh parser's chunk counts and identical raw bodies (after removing the contextual prefix). The initial full-corpus audit found 9,189 identical IDs/texts in PostgreSQL and Qdrant; the final audit after NVIDIA FY2023 found 9,496 in each, without missing, orphaned or mismatched entries.

Evidence: `eval/results/corpus-audit.json` and `eval/results/corpus-audit-final.json`. No additional Microsoft reingestion is required for these pairs. The last batch's 761 chunks / $0.0503 / 760 seconds are **not** totals for all remediation batches.

The old contextual-prefix heuristic still flags 159 chunks: 158 in legacy Item categories excluded from canonical retrieval, and one NVIDIA risk-factor chunk. Inspection of that NVIDIA source shows an actual agreement with Microsoft; this is a detector false positive. Counts of name matches must not be described as counts of proven wrong-company attributions.
