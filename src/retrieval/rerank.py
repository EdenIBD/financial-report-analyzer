import os
from functools import lru_cache

from google.cloud import discoveryengine_v1 as discoveryengine

from src.storage.cost import RERANK_COST_PER_QUERY_USD

@lru_cache(maxsize=1)
def get_ranking_client():
    return discoveryengine.RankServiceClient()
RANKING_CONFIG = (
    f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/locations/global/"
    "rankingConfigs/default_ranking_config"
)

def rerank(state):
    if not state["retrieved_chunks"]:
        return state
    query_text = state["raw_query"]
    chunk_by_id = {c["chunk_id"]: c for c in state["retrieved_chunks"]}
    request = discoveryengine.RankRequest(
        ranking_config=RANKING_CONFIG,
        model="semantic-ranker-default-004",
        query=query_text,
        records=[
            discoveryengine.RankingRecord(id=c["chunk_id"], content=c["text"])
            for c in state["retrieved_chunks"]
        ],
        top_n=8,
    )
    response = get_ranking_client().rank(request=request)
    state["retrieved_chunks"] = [
        {**chunk_by_id[r.id], "score": r.score} for r in response.records
    ]
    state["cost_usd"] = state.get("cost_usd", 0.0) + RERANK_COST_PER_QUERY_USD

    scores = [c["score"] for c in state["retrieved_chunks"]]
    top_score = f"{max(scores):.2f}" if scores else "n/a"
    state.setdefault("trace", []).append(
        f"Reranked to top {len(scores)} chunks via Vertex AI (top score {top_score})"
    )
    return state
