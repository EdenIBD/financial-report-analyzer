from src.agent.nodes.verify import route_after_verify, verify_context
from src.agent.state import QueryType


class FakeClassification:
    def __init__(self, query_type):
        self.query_type = query_type


def make_state(scores, retry_count=0, query_type=QueryType.FACTUAL):
    return {
        "retrieved_chunks": [{"score": s} for s in scores],
        "retry_count": retry_count,
        "use_fallback_sections": False,
        "classification": FakeClassification(query_type),
    }


def test_enough_good_chunks_generates_answer():
    state = make_state([0.9, 0.8, 0.7])
    state = verify_context(state)
    assert route_after_verify(state) == "generate_answer"
    # nu ar trebui sa incrementeze inutil retry_count daca oricum e suficient
    assert state["retry_count"] == 0


def test_insufficient_chunks_retries_and_sets_fallback():
    state = make_state([0.9], retry_count=0)
    state = verify_context(state)
    assert state["retry_count"] == 1
    assert state["use_fallback_sections"] is True
    assert route_after_verify(state) == "retrieve_single"


def test_insufficient_chunks_routes_to_retrieve_multi_for_comparison():
    state = make_state([0.9], retry_count=0, query_type=QueryType.COMPARISON)
    state = verify_context(state)
    assert route_after_verify(state) == "retrieve_multi"


def test_max_retries_forces_generate_answer():
    state = make_state([0.1], retry_count=2)
    state = verify_context(state)
    # la limita, nu mai incrementeaza peste 2
    assert state["retry_count"] == 2
    assert route_after_verify(state) == "generate_answer"


def test_verify_context_appends_reasoning_trace_entry():
    sufficient = verify_context(make_state([0.9, 0.8, 0.7]))
    assert "sufficient" in sufficient["trace"][-1]

    retrying = verify_context(make_state([0.1], retry_count=0))
    assert "retrying" in retrying["trace"][-1].lower()

    exhausted = verify_context(make_state([0.1], retry_count=2))
    assert "retries" in exhausted["trace"][-1].lower()


def test_retry_count_eventually_reaches_limit_and_stops():
    # regresie pentru bug-ul real gasit: fara ca verify_context sa fie NOD
    # (nu functie de conditional_edges), retry_count nu se incrementa
    # niciodata in graf, cauzand bucla infinita retrieve<->rerank. Simulam
    # aici 2 iterații complete (nod + rutare), ca in graf.
    state = make_state([0.1], retry_count=0)
    for _ in range(2):
        state = verify_context(state)
        route = route_after_verify(state)
        if route == "generate_answer":
            break
    assert state["retry_count"] == 2
    assert route == "generate_answer"
