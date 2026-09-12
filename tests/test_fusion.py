from types import SimpleNamespace

from src.retrieval.fusion import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_merges_and_ranks():
    dense = [SimpleNamespace(id="a"), SimpleNamespace(id="b"), SimpleNamespace(id="c")]
    keyword = [SimpleNamespace(id="b"), SimpleNamespace(id="d")]

    result = reciprocal_rank_fusion(dense, keyword, top_k=8, rrf_k=60)
    ids = [r.id for r in result]

    assert ids[0] == "b"  # apare in ambele liste, cel mai bine clasat
    assert set(ids) == {"a", "b", "c", "d"}


def test_reciprocal_rank_fusion_respects_top_k():
    dense = [SimpleNamespace(id=str(i)) for i in range(10)]
    result = reciprocal_rank_fusion(dense, [], top_k=3)
    assert len(result) == 3
