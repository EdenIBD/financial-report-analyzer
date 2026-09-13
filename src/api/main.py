import time

from dotenv import load_dotenv

load_dotenv()  # trebuie inainte de orice import care citeste os.environ la nivel de modul (embed.py, rerank.py)

import os

import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langsmith import traceable
from pydantic import BaseModel

from src.agent.graph import graph
from src.storage.query_log import log_query_to_postgres
from src.api.tracing import get_current_run_id
from src.api.documents import router as documents_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # origin-ul frontend-ului Next.js (sectiunea 8)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)

class QueryRequest(BaseModel):
    raw_query: str

class QueryResponse(BaseModel):
    answer: str | None
    persona: str | None
    query_type: str | None
    sources: list[str]
    retrieved_chunks: list[dict]
    latency_ms: int
    cost_usd: float
    langsmith_trace_id: str | None
    status: str
    ingested_entities: list[str]
    ingestion_errors: list[str]
    reasoning_trace: list[str]

class CorpusCompany(BaseModel):
    ticker: str
    company: str

class CorpusResponse(BaseModel):
    companies: list[CorpusCompany]
    filings_indexed: int
    fiscal_year_min: int | None
    fiscal_year_max: int | None

@app.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    return handle_query(request.raw_query)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/corpus", response_model=CorpusResponse)
def corpus_summary():
    """Sidebar-ul frontend-ului citeste corpusul real, nu o lista hardcodata —
    corpusul creste prin upload si ingestie dinamica, deci "14 filings" ar
    deveni fals in minute de la un query care aduce o companie noua."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ticker, company FROM filings ORDER BY ticker")
            companies = cur.fetchall()
            cur.execute("SELECT count(*), min(fiscal_year), max(fiscal_year) FROM filings")
            count, min_year, max_year = cur.fetchone()
    finally:
        conn.close()
    return {
        "companies": [{"ticker": t, "company": c} for t, c in companies],
        "filings_indexed": count,
        "fiscal_year_min": min_year,
        "fiscal_year_max": max_year,
    }

@traceable(name="handle_query")
def handle_query(raw_query: str) -> dict:
    # @traceable e necesar ca get_current_run_id() (mai jos) sa aiba ceva de intors —
    # in afara unui context trace activ, get_current_run_tree() da mereu None
    # (verificat: fara decorator, trace_id era intotdeauna null in raspuns).
    initial_state = {
        "raw_query": raw_query,
        "retry_count": 0,
        "retrieved_chunks": [],
        "sources": [],
        "use_fallback_sections": False,
        "cost_usd": 0.0,
        "ingested_entities": [],
        "ingestion_errors": [],
        "ingestion_count": 0,
        "trace": [],
    }
    start = time.time()
    final_state = initial_state
    try:
        # stream_mode="values" in loc de graph.invoke(): actualizeaza final_state
        # dupa fiecare nod reusit, deci daca un nod ulterior (ex: rerank) esueaza,
        # starea partiala (clasificare, cost acumulat) ramane, nu se pierde.
        for state_update in graph.stream(initial_state, stream_mode="values"):
            final_state = state_update
        status = "valid" if final_state.get("answer") else "invalid"
    except Exception:
        status = "error"

    latency_ms = int((time.time() - start) * 1000)
    trace_id = get_current_run_id()
    classification = final_state.get("classification")

    try:
        log_query_to_postgres(
            raw_query=raw_query,
            classification=classification,
            retrieved_chunk_ids=[c["chunk_id"] for c in final_state.get("retrieved_chunks", [])],
            latency_ms=latency_ms,
            final_answer=final_state.get("answer"),
            status=status,
            langsmith_trace_id=trace_id,
            cost_usd=final_state.get("cost_usd", 0.0),
            ingested_entities=final_state.get("ingested_entities", []),
        )
    except Exception as log_error:
        # logging esuat nu trebuie sa piarda un raspuns deja generat cu succes
        print(f"[WARN] query_logs write failed: {log_error}")

    return {
        "answer": final_state.get("answer"),
        "persona": classification.persona.value if classification else None,
        "query_type": classification.query_type.value if classification else None,
        "sources": final_state.get("sources", []),
        "retrieved_chunks": final_state.get("retrieved_chunks", []),
        "latency_ms": latency_ms,
        "cost_usd": final_state.get("cost_usd", 0.0),
        "langsmith_trace_id": trace_id,
        "status": status,
        "ingested_entities": final_state.get("ingested_entities", []),
        "ingestion_errors": final_state.get("ingestion_errors", []),
        "reasoning_trace": final_state.get("trace", []),
    }
