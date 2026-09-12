 # langsmith_trace_id era intotdeauna null in raspunsul /query

## Ce s-a intamplat

`src/api/tracing.py::get_current_run_id()` foloseste `get_current_run_tree()` din
`langsmith.run_helpers`, apelat in `handle_query` (`main.py`) **dupa** ce
`graph.invoke()` s-a terminat deja. Contextul de run al LangSmith (populat prin
Python contextvars) exista doar cat timp codul ruleaza *in interiorul* unui apel
urmarit (traced) — dupa ce acel apel se termina si iese din stack, contextul
dispare, deci `get_current_run_tree()` intoarce mereu `None` cand e apelat "dupa
fapt", chiar daca graph.invoke() a fost el insusi urmarit corect.

Verificat empiric: LangGraph traceaza automat FIECARE nod din graf (classify,
retrieve_single, rerank...) in LangSmith cand `LANGCHAIN_TRACING_V2=true` — deci
infrastructura de baza exista si functioneaza (confirmat cu apel direct la API-ul
LangSmith, `GET /api/v1/runs/query`, care arata run-uri reale cu clasificare,
chunk-uri recuperate, cost). Problema era doar la nivelul lui `handle_query`,
care nu avea el insusi un context de trace activ in care sa "prinda" id-ul.

## Fix aplicat

Adaugat `@traceable(name="handle_query")` din pachetul `langsmith` pe functia
`handle_query` — asta creeaza un run-tree activ pentru toata executia functiei,
in interiorul caruia `get_current_run_tree()` (apelat dupa `graph.invoke()`, tot
in interiorul functiei decorate) gaseste id-ul real. Testat direct: fara
decorator, `run_tree` e `None`; cu decorator, e un UUID real.

## Cand sa revii aici

Daca se adauga alte functii care apeleaza `graph.invoke()` din afara lui
`handle_query` (ex: un script CLI separat) si au nevoie de trace_id, trebuie
decorate la fel cu `@traceable`, altfel `get_current_run_id()` va intoarce `None`
acolo si.
