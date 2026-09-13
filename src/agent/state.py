from enum import Enum
from typing import Optional, List, TypedDict
from pydantic import BaseModel, Field

class Persona(str, Enum):
    LEGAL = "legal"
    INVESTMENT_FIRM = "investment_firm"
    AUDIT_FIRM = "audit_firm"
    INVESTMENT_BANK = "investment_bank"
    TREASURY = "treasury"

class QueryType(str, Enum):
    FACTUAL = "factual"
    COMPARISON = "comparison"
    RISK_ANALYSIS = "risk_analysis"

class QueryClassification(BaseModel):
    persona: Persona = Field(description="Ce tip de utilizator/scop are query-ul")
    query_type: QueryType = Field(description="Ce fel de operatie necesita raspunsul")
    reasoning: Optional[str] = Field(default=None, description="Justificare, pentru logging/debug")

class RetrievedChunk(TypedDict):
    chunk_id: str
    text: str
    company: str
    fiscal_year: int
    section: str
    score: float

class AgentState(TypedDict):
    raw_query: str
    requested_tickers: List[str]
    requested_years: List[int]
    scope_doc_ids: List[str]
    scope_blocked: bool
    abstained: bool
    classification: Optional[QueryClassification]
    retrieved_chunks: List[RetrievedChunk]
    retry_count: int
    use_fallback_sections: bool
    answer: Optional[str]
    sources: List[str]
    cost_usd: float  # acumulat de fiecare nod care face un apel LLM/embedding/rerank
    ingested_entities: List[str]  # ce s-a ingerat live in acest query
    ingestion_details: List[dict]  # {ticker, company, fiscal_year, filing_type, chunks} per filing ingerat
    ingestion_errors: List[str]  # ce nu s-a putut ingera, cu motiv
    ingestion_count: int  # contra MAX_INGESTIONS_PER_QUERY
    trace: List[str]  # pasii reali facuti de pipeline, afisati in UI ca "chain of thought"
