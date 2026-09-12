# Log

## [2026-09-09] Edgar10QParser nu recunoaste sectiunile 10-K, fix pe regex de titlu | pages/failure-patterns/edgar10q-parser-10k-sections.md
## [2026-09-11] gemini-embedding-2 raspunde 404 pe Vertex AI, trecut pe gemini-embedding-001 | pages/failure-patterns/gemini-embedding-2-404.md
## [2026-09-11] gemini-2.5-flash/pro retrase pentru conturi noi, trecut pe alias-uri "latest" | pages/failure-patterns/gemini-2.5-models-retired.md
## [2026-09-11] qdrant_client.query_points() intoarce QueryResponse (.points), nu lista direct — fix in retrieve.py | pages/failure-patterns/qdrant-query-points-response-shape.md
## [2026-09-11] langsmith_trace_id era mereu null, fix cu @traceable pe handle_query | pages/failure-patterns/langsmith-trace-id-always-null.md
## [2026-09-11] handle_query trecut pe graph.stream(stream_mode="values") — starea partiala (persona, cost) nu se mai pierde la esec ulterior | src/api/main.py
## [2026-09-11] scripts/cost_trends.py + wiki/pages/cost-trends.md — agregare cost_usd x persona x query_type din query_logs | pages/cost-trends.md
## [2026-09-11] Discovery Engine API activat + {project} substituit in rerank.py — reranker functional pentru prima data | src/retrieval/rerank.py
## [2026-09-11] Migrare completa colima -> Docker Desktop (pg_dump + snapshot Qdrant), date pastrate (8250 chunks) | docker-compose.yml
## [2026-09-11] Bug critic: verify_context ca functie de rutare pierdea mutatiile de stare -> bucla infinita retrieve<->rerank, oprita doar de rate-limit extern | pages/failure-patterns/verify-context-infinite-retry-loop.md
## [2026-09-11] Bug critic: response.content nu e mereu string (gemini-pro-latest intoarce blocuri) -> 500 pe /query, fix cu response.text | pages/failure-patterns/generate-answer-content-not-string.md
## [2026-09-11] Pipeline complet functional end-to-end pentru prima data: status "valid", raspuns real generat si citat corect
## [2026-09-11] retrieve_multi nu producea raspuns pentru comparatii fara companie numita explicit — fix cu fallback pe toate cele 3 companii cunoscute | pages/failure-patterns/retrieve-multi-no-entity-fallback.md
