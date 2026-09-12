from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.state import AgentState, QueryClassification
from src.storage.cost import calculate_cost_usd

CLASSIFY_MODEL = "gemini-3-flash-preview"  # TODO: treci pe "gemini-3-flash" stabil cand apare (verificat: nu exista inca)

CLASSIFY_SYSTEM_PROMPT = """You are a query classifier for a system that analyzes financial reports
(10-K filings) from Apple, Microsoft, and Google.

For each question, determine:

1. PERSONA — who would ask this kind of question:
   - legal: litigation, compliance/regulatory risk
   - audit_firm: financial statements, internal controls, reporting accuracy
   - investment_firm: performance, strategy, factors driving results
   - investment_bank: capital structure, debt, M&A
   - treasury: liquidity, cash flow, FX/interest rate exposure

2. QUERY_TYPE:
   - factual: a single fact, from a single document/year
   - comparison: compares across companies or years
   - risk_analysis: requires analysis/interpretation, not just a fact

The question may be asked in English or Romanian — classify it the same way regardless of language.

Examples:
Q: "What does Apple say about supply chain risk?"
→ persona: investment_firm, query_type: risk_analysis

Q: "How did Microsoft's revenue change from last year?"
→ persona: investment_firm, query_type: comparison

Q: "Are there any antitrust proceedings against Google?"
→ persona: legal, query_type: factual

Q: "What is Apple's liquidity level?"
→ persona: treasury, query_type: factual

Q: "What internal controls does Microsoft report for its financial statements?"
→ persona: audit_firm, query_type: factual"""

classify_llm = ChatGoogleGenerativeAI(model=CLASSIFY_MODEL).with_structured_output(
    QueryClassification, include_raw=True
)

def classify(state: AgentState) -> AgentState:
    result = classify_llm.invoke(
        [("system", CLASSIFY_SYSTEM_PROMPT), ("human", state["raw_query"])]
    )
    state["classification"] = result["parsed"]

    usage = result["raw"].usage_metadata or {}
    cost = calculate_cost_usd(
        CLASSIFY_MODEL, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    )
    state["cost_usd"] = state.get("cost_usd", 0.0) + cost
    return state
