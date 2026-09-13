"""Resolve every named company and required filing before retrieval."""
import os
import re
from datetime import date

import psycopg2
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.agent.nodes.classify import CLASSIFY_MODEL
from src.agent.nodes.retrieve import extract_entities
from src.agent.state import AgentState
from src.ingestion.pipeline import ingest_company, resolve_company
from src.storage.cost import calculate_cost_usd

MAX_INGESTIONS_PER_QUERY = 1
DEFAULT_FILING_TYPE = "10-K"
DEFAULT_FILING_COUNT = 1

EXTRACT_SYSTEM_PROMPT = """Extract ALL company names or stock tickers explicitly mentioned in the question.
Keep the exact names; never replace a subsidiary with its parent or invent companies.
Return an empty list for a general question without named companies.
The question may be in English or Romanian. This is entity extraction, not answering."""

class ExtractedEntities(BaseModel):
    companies: list[str] = Field(description="All explicitly named companies/tickers")

_entity_llm = ChatGoogleGenerativeAI(model=CLASSIFY_MODEL).with_structured_output(
    ExtractedEntities, include_raw=True
)


def resolve_unknown_companies(query: str) -> tuple[list[str], float, list[str]]:
    result = _entity_llm.invoke([("system", EXTRACT_SYSTEM_PROMPT), ("human", query)])
    usage = result["raw"].usage_metadata or {}
    cost = calculate_cost_usd(CLASSIFY_MODEL, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
    if result.get("parsed") is None:
        raise ValueError("Company extraction returned no valid structured result")
    tickers, unresolved = [], []
    for name in result["parsed"].companies:
        # Local aliases support uploaded filings and Google/Alphabet too.
        local = extract_entities(name)
        company = None if local else resolve_company(name)
        if local:
            tickers.extend(local)
        elif company:
            tickers.append(company["ticker"])
        else:
            unresolved.append(name)
    return list(dict.fromkeys(tickers)), cost, unresolved


def available_filings(ticker: str, fiscal_year: int | None, filing_type: str) -> list[str]:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT f.doc_id FROM filings f
                WHERE ticker = %s AND filing_type = %s AND ingestion_status = 'ready'
                AND (%s IS NULL OR fiscal_year = %s)
                AND EXISTS (SELECT 1 FROM chunks c WHERE c.doc_id = f.doc_id)""",
                (ticker, filing_type, fiscal_year, fiscal_year))
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def requested_years(query: str) -> list[int]:
    years = {int(y) for y in re.findall(r'(?<![0-9])(?:19|20)\d{2}\b', query)}
    if not years and re.search(r'\b(this year|anul acesta|anul curent)\b', query, re.I):
        years.add(date.today().year)
    # A range is inclusive; a comparison (2023 vs 2025) is not a range.
    for start, end in re.findall(r'\b((?:19|20)\d{2})\s*(?:-|–|to|până în)\s*((?:19|20)\d{2})\b', query, re.I):
        if 0 <= int(end) - int(start) <= 20:
            years.update(range(int(start), int(end) + 1))
    return sorted(years)


def check_entity_exists(state: AgentState) -> AgentState:
    trace = state.setdefault("trace", [])
    errors = state.setdefault("ingestion_errors", [])
    state["requested_years"] = requested_years(state["raw_query"])
    state["requested_tickers"] = []
    state["scope_doc_ids"] = []
    state["scope_blocked"] = False
    filing_type = "10-Q" if re.search(r'10\s*-?\s*Q\b', state["raw_query"], re.I) else DEFAULT_FILING_TYPE
    try:
        # Always extract: a known Apple must not hide an unknown Nvidia in the same question.
        requested, cost, unresolved = resolve_unknown_companies(state["raw_query"])
        state["cost_usd"] = state.get("cost_usd", 0.0) + cost
        state["requested_tickers"] = requested
        for name in unresolved:
            errors.append(f'{name}: could not resolve an exact registrant in the SEC ticker catalog. '
                          'Coverage excludes some registrants without tickers; no other company was substituted.')
        state["scope_blocked"] = bool(unresolved)
    except Exception as exc:
        errors.append(f"Could not establish the requested company scope: {exc}")
        state["scope_blocked"] = True
        trace.append("Company resolution failed — retrieval blocked to avoid unrelated sources")
        return state

    for ticker in requested:
        for year in state["requested_years"] or [None]:
            docs = available_filings(ticker, year, filing_type)
            if not docs:
                label = f"{ticker} {filing_type}" + (f" FY{year}" if year else " (latest)")
                if state["ingestion_count"] >= MAX_INGESTIONS_PER_QUERY:
                    errors.append(f"{label}: per-query ingestion limit reached, not fetched")
                    state["scope_blocked"] = True
                    continue
                # Count attempts, including failures, to bound latency and external calls.
                state["ingestion_count"] += 1
                trace.append(f"Missing {label} — fetching from SEC EDGAR")
                try:
                    result = ingest_company(ticker, filing_type, DEFAULT_FILING_COUNT, fiscal_year=year)
                    state["cost_usd"] += result["cost_usd"]
                    errors.extend(result["errors"])
                    if result["filings_ingested"]:
                        state["ingested_entities"].append(ticker)
                        state.setdefault("ingestion_details", []).extend({"ticker": ticker, **f} for f in result["filings"])
                        trace.append(f"Indexed {ticker}: {result['chunks_indexed']} chunks")
                    docs = available_filings(ticker, year, filing_type)
                except Exception as exc:
                    errors.append(f"{label}: {exc}")
                if not docs:
                    state["scope_blocked"] = True
            state["scope_doc_ids"].extend(docs)
    trace.append(f"Resolved scope: {', '.join(requested) or 'general corpus'}; fiscal years: {state['requested_years'] or 'unspecified'}")
    if state["scope_blocked"]:
        trace.append("Requested evidence unavailable — no unrelated-company/year fallback")
    return state
