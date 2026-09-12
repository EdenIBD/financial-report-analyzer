"""Skeleton graph — structura e decisa; implementarea nodurilor individuale e
separata (vezi src/agent/nodes/). classify si generate_answer raman
NotImplementedError pana la clarificare (build-spec.md sectiunea 2)."""

from langgraph.graph import StateGraph, START, END

from src.agent.state import AgentState, QueryType
from src.agent.nodes.classify import classify
from src.agent.nodes.retrieve import retrieve_single, retrieve_multi
from src.agent.nodes.generate import generate_answer
from src.agent.nodes.verify import verify_context, route_after_verify
from src.retrieval.rerank import rerank

def route_after_classify(state: AgentState) -> str:
    if state["classification"].query_type == QueryType.COMPARISON:
        return "retrieve_multi"
    return "retrieve_single"

graph_builder = StateGraph(AgentState)
graph_builder.add_node("classify", classify)
graph_builder.add_node("retrieve_single", retrieve_single)
graph_builder.add_node("retrieve_multi", retrieve_multi)
graph_builder.add_node("rerank", rerank)
graph_builder.add_node("verify_context", verify_context)
graph_builder.add_node("generate_answer", generate_answer)

graph_builder.add_edge(START, "classify")
graph_builder.add_conditional_edges(
    "classify",
    route_after_classify,
    {"retrieve_single": "retrieve_single", "retrieve_multi": "retrieve_multi"},
)
graph_builder.add_edge("retrieve_single", "rerank")
graph_builder.add_edge("retrieve_multi", "rerank")
graph_builder.add_edge("rerank", "verify_context")
graph_builder.add_conditional_edges(
    "verify_context",
    route_after_verify,
    {
        "generate_answer": "generate_answer",
        "retrieve_single": "retrieve_single",
        "retrieve_multi": "retrieve_multi",
    },
)
graph_builder.add_edge("generate_answer", END)

graph = graph_builder.compile()
