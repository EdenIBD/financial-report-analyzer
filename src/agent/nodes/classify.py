from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.state import AgentState, QueryClassification
from src.storage.cost import calculate_cost_usd

CLASSIFY_MODEL = "gemini-flash-latest"  # gemini-2.5-flash raspundea 404 (retras) — vezi wiki/pages/failure-patterns

CLASSIFY_SYSTEM_PROMPT = """Ești un clasificator de întrebări pentru un sistem de analiză a rapoartelor financiare
(10-K) ale Apple, Microsoft și Google.

Pentru fiecare întrebare, determină:

1. PERSONA — cine ar pune o astfel de întrebare:
   - legal: procese, litigii, riscuri de conformitate/reglementare
   - audit_firm: situații financiare, controale interne, acuratețea raportării
   - investment_firm: performanță, strategie, factori care influențează rezultatele
   - investment_bank: structură de capital, datorii, fuziuni/achiziții
   - treasury: lichiditate, cash flow, expunere valutară/dobândă

2. QUERY_TYPE:
   - factual: o singură informație, dintr-un singur document/an
   - comparison: compară între companii sau între ani
   - risk_analysis: cere analiză/interpretare, nu doar un fapt

Exemple:
Q: "Ce spune Apple despre riscul din lanțul de aprovizionare?"
→ persona: investment_firm, query_type: risk_analysis

Q: "Cum s-a schimbat cifra de afaceri Microsoft față de anul trecut?"
→ persona: investment_firm, query_type: comparison

Q: "Există procese antitrust în curs împotriva Google?"
→ persona: legal, query_type: factual

Q: "Care e nivelul de lichiditate al Apple?"
→ persona: treasury, query_type: factual

Q: "Ce controale interne raportează Microsoft pentru situațiile financiare?"
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
        "gemini-classify-model", usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    )
    state["cost_usd"] = state.get("cost_usd", 0.0) + cost
    return state
