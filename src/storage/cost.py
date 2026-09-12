PRICING_PER_MILLION_TOKENS = {
    # placeholder — verifica preturile curente pe pagina de pricing Vertex AI inainte de a te baza pe cifre reale.
    # Cheile trebuie sa fie exact stringul de model folosit in cod (CLASSIFY_MODEL/
    # GENERATE_MODEL/CONTEXT_MODEL) — o cheie care nu corespunde modelului real
    # invocat a fost deja un bug gasit si reparat aici.
    "gemini-3-flash-preview": {"input": 0.75, "output": 3.75},  # classify + generate
    "gemini-embedding-001": {"input": 0.20, "output": 0.0},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},  # contextual retrieval
}

# Reranker (Vertex AI Ranking API) se taxeaza per query, nu per token.
RERANK_COST_PER_QUERY_USD = 0.0  # TODO: confirma pricing curent Vertex AI Ranking API

def calculate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price = PRICING_PER_MILLION_TOKENS.get(model, {"input": 0, "output": 0})
    return (tokens_in * price["input"] + tokens_out * price["output"]) / 1_000_000
