"""Ingestie dinamica: daca intrebarea mentioneaza o companie care nu e in corpus,
o aduce de pe EDGAR inainte de retrieval, in acelasi request.

Treapta 2 de extractie (LLM + resolve pe EDGAR) sta aici, nu in extract_entities,
ca sa ruleze doar cand chiar e nevoie — extract_entities e apelat si de nodurile
de retrieval, unde un apel LLM in plus la fiecare query ar fi risipa.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.agent.nodes.classify import CLASSIFY_MODEL
from src.agent.nodes.retrieve import extract_entities, known_tickers
from src.agent.state import AgentState
from src.ingestion.pipeline import ingest_company, resolve_company
from src.storage.cost import calculate_cost_usd

# [valori de pornire] Ingestia dureaza 1-3 minute per filing: un query de
# comparatie cu 3 companii necunoscute ar bloca request-ul ~9 minute. Restul
# intra ca eroare explicita in raspuns, nu ca asteptare tacuta.
MAX_INGESTIONS_PER_QUERY = 1  # TODO: recalibrat dupa masurarea latentei reale
DEFAULT_FILING_TYPE = "10-K"
DEFAULT_FILING_COUNT = 1

EXTRACT_SYSTEM_PROMPT = """Extract the names of any companies mentioned in the question.
Return only company names as they appear (free text), nothing else. If no company is
mentioned, return an empty list. The question may be in English or Romanian."""


class ExtractedEntities(BaseModel):
    companies: list[str] = Field(description="Nume de companii mentionate in intrebare, ca text liber")


# CLASSIFY_MODEL, nu "gemini-3-flash" cum cere spec-ul: acel nume raspunde 404 pe
# acest proiect (verificat, vezi wiki/pages/failure-patterns). Constanta e aceeasi
# pe care o foloseste deja classify.py, deci nu poate diverge de pricing.
_entity_llm = ChatGoogleGenerativeAI(model=CLASSIFY_MODEL).with_structured_output(
    ExtractedEntities, include_raw=True
)


def resolve_unknown_companies(query: str) -> tuple[list[str], float]:
    """Treapta 2: numele libere din intrebare -> tickere reale de pe EDGAR.
    Intoarce (tickere, cost real al apelului LLM)."""
    result = _entity_llm.invoke([("system", EXTRACT_SYSTEM_PROMPT), ("human", query)])
    usage = result["raw"].usage_metadata or {}
    cost = calculate_cost_usd(
        CLASSIFY_MODEL, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    )

    tickers = []
    for name in result["parsed"].companies:
        company = resolve_company(name)
        if company:
            tickers.append(company["ticker"])
    return tickers, cost


def check_entity_exists(state: AgentState) -> AgentState:
    trace = state.setdefault("trace", [])

    requested = extract_entities(state["raw_query"])
    if not requested:
        requested, cost = resolve_unknown_companies(state["raw_query"])
        state["cost_usd"] = state.get("cost_usd", 0.0) + cost
        if requested:
            trace.append(f"No corpus match — resolved via LLM + SEC EDGAR: {', '.join(requested)}")

    known = known_tickers()
    missing = [ticker for ticker in requested if ticker not in known]
    if requested and not missing:
        trace.append(f"Companies mentioned already in corpus: {', '.join(requested)}")

    for ticker in missing:
        if state["ingestion_count"] >= MAX_INGESTIONS_PER_QUERY:
            state["ingestion_errors"].append(
                f"{ticker}: per-query ingestion limit reached, not fetched"
            )
            trace.append(f"{ticker} not in corpus, but per-query ingestion limit reached — skipped")
            break
        trace.append(f"{ticker} not in corpus — fetching latest 10-K from SEC EDGAR")
        try:
            result = ingest_company(ticker, DEFAULT_FILING_TYPE, DEFAULT_FILING_COUNT)
            state["cost_usd"] = state.get("cost_usd", 0.0) + result["cost_usd"]
            state["ingestion_errors"].extend(result["errors"])
            if result["filings_ingested"]:
                state["ingested_entities"].append(ticker)
                state["ingestion_count"] += 1
                trace.append(f"Indexed {ticker}: {result['chunks_indexed']} chunks")
            elif result["errors"]:
                trace.append(f"Could not index {ticker}: {result['errors'][-1]}")
        except Exception as e:
            # Orice esec de ingestie (ticker inexistent, 429 de la EDGAR, parsing
            # esuat) e raportat, nu propagat: query-ul continua cu ce are deja.
            state["ingestion_errors"].append(f"{ticker}: {e}")
            trace.append(f"Could not index {ticker}: {e}")

    return state
