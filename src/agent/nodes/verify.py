from src.agent.state import AgentState, QueryType

MIN_SCORE_THRESHOLD = 0.55  # TODO: recalibrat pe eval set (scor de reranker, nu RRF)
MIN_CHUNKS_REQUIRED = 3     # TODO: recalibrat pe eval set


def _enough_good_chunks(state: AgentState) -> bool:
    good_chunks = [c for c in state["retrieved_chunks"] if c["score"] >= MIN_SCORE_THRESHOLD]
    return len(good_chunks) >= MIN_CHUNKS_REQUIRED


def verify_context(state: AgentState) -> AgentState:
    # Nod real (add_node), NU functie de conditional_edges: o functie de rutare
    # e doar citita de LangGraph — orice mutatie a starii in interiorul ei
    # (retry_count += 1) se pierde, nu se persista in starea grafului. Bug real
    # gasit: fara acest fix retry_count ramanea mereu la valoarea initiala, deci
    # verify_context -> retrieve -> rerank bucla infinit, oprita doar de
    # rate-limit-ul extern al Google (ResourceExhausted pe Rank Service).
    trace = state.setdefault("trace", [])
    if _enough_good_chunks(state):
        trace.append("Context verified as sufficient")
    elif state["retry_count"] < 2:
        state["retry_count"] += 1
        state["use_fallback_sections"] = True
        trace.append(f"Not enough high-confidence context — retrying with broader sections (attempt {state['retry_count']})")
    else:
        trace.append("Still limited context after retries — answering with what's available")
    return state


def route_after_verify(state: AgentState) -> str:
    if _enough_good_chunks(state) or state["retry_count"] >= 2:
        return "generate_answer"
    return "retrieve_single" if state["classification"].query_type != QueryType.COMPARISON else "retrieve_multi"
