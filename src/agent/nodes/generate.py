from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.state import AgentState, Persona
from src.storage.cost import calculate_cost_usd

GENERATE_MODEL = "gemini-3-flash-preview"  # TODO: treci pe "gemini-3-flash" stabil cand apare (verificat: nu exista inca)

PERSONA_TONE = {
    Persona.LEGAL: "Be precise, quote the exact section/clause, cautious tone, explicitly flag legal risk.",
    Persona.AUDIT_FIRM: "Focus on figures and controls, cite the exact statement/note, flag any discrepancy.",
    Persona.INVESTMENT_FIRM: "Narrative tone, focus on the factors driving performance, forward-looking perspective.",
    Persona.INVESTMENT_BANK: "Concise, focused on capital structure and metrics relevant to transactions.",
    Persona.TREASURY: "Focus on liquidity/cash figures, flag cash-shortfall risk.",
}

BASE_PROMPT = """You are an assistant that answers questions about 10-K financial reports
(Apple, Microsoft, Google), using ONLY the provided context fragments.

Rules:
- Answer only from the context; if the information isn't there, say so explicitly.
- Cite the source for every claim in the format [chunk_id] (the identifier in brackets at the start of each context fragment).
- Do not invent figures or facts that don't appear in the context.
- Answer in the same language the question was asked in (English or Romanian). Default to English if that's unclear.

{persona_tone}

Context:
{context}

Question: {query}"""

generate_llm = ChatGoogleGenerativeAI(model=GENERATE_MODEL)

def generate_answer(state: AgentState) -> AgentState:
    persona = state["classification"].persona
    context = "\n\n".join(
        f"[{c['chunk_id']} | {c['company']} {c['fiscal_year']} | {c['section']}]\n{c['text']}"
        for c in state["retrieved_chunks"]
    )
    prompt = BASE_PROMPT.format(
        persona_tone=PERSONA_TONE[persona], context=context, query=state["raw_query"]
    )
    response = generate_llm.invoke(prompt)
    # response.content poate fi un string simplu SAU o lista de blocuri
    # structurate (ex: [{"type": "text", "text": "...", "extras": {...}}])
    # in functie de model — gemini-pro-latest intoarce blocuri, nu string.
    # .text e proprietatea LangChain care extrage robust indiferent de forma.
    state["answer"] = response.text
    state["sources"] = [c["chunk_id"] for c in state["retrieved_chunks"]]
    state.setdefault("trace", []).append(
        f"Generated answer citing {len(state['sources'])} source chunks"
    )

    usage = response.usage_metadata or {}
    cost = calculate_cost_usd(
        GENERATE_MODEL, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    )
    state["cost_usd"] = state.get("cost_usd", 0.0) + cost
    return state
