import os

from qdrant_client import QdrantClient

from src.agent.state import AgentState, Persona, RetrievedChunk
from src.retrieval.embed import embed_query
from src.retrieval.fusion import reciprocal_rank_fusion

# QDRANT_URL: "http://localhost:6333" local (implicit), "http://qdrant:6333" in docker-compose
qdrant_client = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))

# Categorii canonice (src/ingestion/sections.py), nu numere brute de Item —
# 10-K si 10-Q numeroteaza acelasi continut diferit (MD&A e Item7 la 10-K,
# Item2 la 10-Q), deci filtrarea trebuie sa fie pe categorie semantica,
# comuna intre tipurile de filing, nu pe Item.
PERSONA_SECTIONS = {
    Persona.LEGAL: ["legal_proceedings", "risk_factors"],
    Persona.AUDIT_FIRM: ["financial_statements", "controls_procedures"],
    Persona.INVESTMENT_FIRM: ["mdna", "financial_statements"],
    Persona.INVESTMENT_BANK: ["mdna", "market_risk", "financial_statements"],
    Persona.TREASURY: ["market_risk", "financial_statements"],
}
FALLBACK_SECTIONS = ["risk_factors", "mdna", "market_risk", "financial_statements"]

KNOWN_ENTITIES = {
    "AAPL": ["apple", "aapl"],
    "MSFT": ["microsoft", "msft"],
    "GOOGL": ["google", "alphabet", "googl"],
}

def extract_entities(query: str) -> list[str]:
    query_lower = query.lower()
    return [ticker for ticker, aliases in KNOWN_ENTITIES.items() if any(a in query_lower for a in aliases)]

def format_chunk(result) -> RetrievedChunk:
    payload = result.payload
    return {
        # result.id e ID-ul intern Qdrant (UUID) — nu poate fi chunk_id-ul logic
        # (Postgres chunks.chunk_id, folosit si pentru citarile din generate.py),
        # care e string arbitrar, deci nu poate fi si ID de punct Qdrant.
        "chunk_id": payload["chunk_id"],
        "text": payload["text"],
        "company": payload["company"],
        "fiscal_year": payload["fiscal_year"],
        "section": payload["section"],
        "score": result.score,
    }

def retrieve_single(state: AgentState) -> AgentState:
    persona = state["classification"].persona
    allowed_sections = FALLBACK_SECTIONS if state["use_fallback_sections"] else PERSONA_SECTIONS[persona]
    query_text = state["raw_query"]
    # embed.py nu expune usage/token count in return; costul embedding-ului
    # (sectiunea 7) nu poate fi calculat aici din raspunsul real al API-ului
    # fara sa dublam apelul — nu tracked, spre diferenta de classify/generate/rerank.
    dense_vec = embed_query(query_text)
    # query_points() intoarce un QueryResponse (are .points), nu o lista direct —
    # reciprocal_rank_fusion asteapta obiecte cu .id/.score, deci extragem .points.
    dense_results = qdrant_client.query_points(
        collection_name="financial_reports",
        query=dense_vec,
        query_filter={"must": [{"key": "section", "match": {"any": allowed_sections}}]},
        limit=15,
    ).points
    keyword_results = qdrant_client.query_points(
        collection_name="financial_reports",
        query_filter={
            "must": [
                {"key": "section", "match": {"any": allowed_sections}},
                {"key": "text", "match": {"text": query_text}},
            ]
        },
        limit=15,
    ).points
    merged = reciprocal_rank_fusion(dense_results, keyword_results, top_k=8)
    state["retrieved_chunks"] = [format_chunk(r) for r in merged]
    return state


def retrieve_multi(state: AgentState) -> AgentState:
    persona = state["classification"].persona
    allowed_sections = FALLBACK_SECTIONS if state["use_fallback_sections"] else PERSONA_SECTIONS[persona]
    query_text = state["raw_query"]
    entities = extract_entities(query_text)
    if not entities:
        # Query de comparatie fara nicio companie numita explicit (ex: "cum s-au
        # schimbat factorii de risc din 2024 vs 2025") — fara fallback, bucla
        # de mai jos nu ruleaza deloc, retrieved_chunks ramane gol si nu se
        # genereaza niciun raspuns. Corpusul are doar 3 companii cunoscute,
        # deci cautam in toate 3 in loc sa esuam silentios.
        entities = list(KNOWN_ENTITIES.keys())
    dense_vec = embed_query(query_text)

    all_chunks = []
    for entity in entities:
        base_filter = [
            {"key": "section", "match": {"any": allowed_sections}},
            {"key": "company", "match": {"value": entity}},
        ]
        dense_results = qdrant_client.query_points(
            collection_name="financial_reports",
            query=dense_vec,
            query_filter={"must": base_filter},
            limit=10,
        ).points
        keyword_results = qdrant_client.query_points(
            collection_name="financial_reports",
            query_filter={"must": base_filter + [{"key": "text", "match": {"text": query_text}}]},
            limit=10,
        ).points
        # RRF separat per entitate, nu una globala: la o comparatie intre companii,
        # o singura fuziune globala ar putea intoarce top 8 dintr-o singura companie.
        merged = reciprocal_rank_fusion(dense_results, keyword_results, top_k=5)
        all_chunks.extend([format_chunk(r) for r in merged])

    state["retrieved_chunks"] = all_chunks
    return state
