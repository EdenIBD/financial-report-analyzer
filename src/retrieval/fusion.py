def reciprocal_rank_fusion(dense_results, keyword_results, top_k=8, rrf_k=60):
    scores = {}
    pool = {}
    for rank, r in enumerate(dense_results):
        scores[r.id] = scores.get(r.id, 0) + 1 / (rrf_k + rank + 1)
        pool[r.id] = r
    for rank, r in enumerate(keyword_results):
        scores[r.id] = scores.get(r.id, 0) + 1 / (rrf_k + rank + 1)
        pool[r.id] = r
    ranked_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
    return [pool[i] for i in ranked_ids]
