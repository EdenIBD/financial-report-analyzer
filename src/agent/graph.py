from langgraph.graph import StateGraph, START, END

from src.agent.state import AgentState, QueryType
from src.agent.nodes.classify import classify
from src.agent.nodes.check_entity import check_entity_exists
from src.agent.nodes.retrieve import retrieve_single, retrieve_multi
from src.agent.nodes.generate import generate_answer
from src.agent.nodes.verify import verify_context, route_after_verify
from src.retrieval.rerank import rerank

def route_after_classify(state: AgentState) -> str:
    if state.get("scope_blocked"):
        return "generate_answer"
    if state["classification"].query_type == QueryType.COMPARISON:
        return "retrieve_multi"
    return "retrieve_single"

graph_builder = StateGraph(AgentState)
graph_builder.add_node("classify", classify)
graph_builder.add_node("check_entity_exists", check_entity_exists)
graph_builder.add_node("retrieve_single", retrieve_single)
graph_builder.add_node("retrieve_multi", retrieve_multi)
graph_builder.add_node("rerank", rerank)
graph_builder.add_node("verify_context", verify_context)
graph_builder.add_node("generate_answer", generate_answer)

graph_builder.add_edge(START, "classify")
# check_entity_exists intre classify si retrieval, pe ambele ramuri: companiile
# necunoscute trebuie ingerate inainte sa se caute in ele. Bucla de retry din
# verify_context sare peste el — corpusul nu se schimba intre incercari.
graph_builder.add_edge("classify", "check_entity_exists")
graph_builder.add_conditional_edges(
    "check_entity_exists",
    route_after_classify,
    {"retrieve_single": "retrieve_single", "retrieve_multi": "retrieve_multi", "generate_answer": "generate_answer"},
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
