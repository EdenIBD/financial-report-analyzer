PRICING_PER_MILLION_TOKENS = {
    # placeholder — verifica preturile curente pe pagina de pricing Vertex AI inainte de a te baza pe cifre reale
    "gemini-classify-model": {"input": 0.10, "output": 0.40},
    "gemini-generate-model": {"input": 0.10, "output": 0.40},
    "gemini-embedding-2": {"input": 0.20, "output": 0.0},
    "gemini-flash-lite": {"input": 0.10, "output": 0.40},  # contextual retrieval
}

# Reranker (Vertex AI Ranking API) se taxeaza per query, nu per token.
RERANK_COST_PER_QUERY_USD = 0.0  # TODO: confirma pricing curent Vertex AI Ranking API

def calculate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price = PRICING_PER_MILLION_TOKENS.get(model, {"input": 0, "output": 0})
    return (tokens_in * price["input"] + tokens_out * price["output"]) / 1_000_000
