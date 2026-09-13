import re

from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.citations import inspect_citations
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
using ONLY the provided context fragments. Never substitute another company or fiscal year.
A filing fiscal year is distinct from a calendar year and the year it was filed.

Rules:
- Answer only from the context; if the information isn't there, say so explicitly.
- Cite every factual claim with the COMPLETE source identifier in brackets, copied exactly from the context. Never shorten it to a numeric suffix such as [61].
- Do not invent figures or facts that don't appear in the context.
- Answer in the same language the question was asked in (English or Romanian). Default to English if that's unclear.

{persona_tone}

Context:
{context}

Question: {query}"""

generate_llm = ChatGoogleGenerativeAI(model=GENERATE_MODEL)

def generate_answer(state: AgentState) -> AgentState:
    if state.get("scope_blocked") or not state.get("retrieved_chunks"):
        state["retrieved_chunks"] = []
        state["sources"] = []
        state["abstained"] = True
        romanian = re.search(r"\b(care|raportul|din|pentru|rezumă|rezuma|compară|compara)\b", state["raw_query"], re.I)
        state["answer"] = (
            "Nu am putut obține documentele pentru compania și anul cerute. Nu pot oferi un rezumat verificabil din corpusul disponibil. Consultați detaliile ingestiei."
            if romanian else
            "I could not obtain evidence for the requested company and fiscal year. I cannot provide a supported summary from the available corpus. See the ingestion details."
        )
        state.setdefault("trace", []).append("Abstained because the requested evidence is unavailable")
        return state
    persona = state["classification"].persona
    context = "\n\n".join(
        f"[{c['chunk_id']}]\nCompany: {c['company']}; fiscal year: {c['fiscal_year']}; section: {c['section']}\n{c['text']}"
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
    citations = inspect_citations(state["answer"], {c["chunk_id"] for c in state["retrieved_chunks"]})
    if citations["all_ids_exist"]:
        state["sources"] = citations["cited_ids"]
        state.setdefault("trace", []).append(f"Generated answer with {len(state['sources'])} resolvable source citations")
    else:
        state["abstained"] = True
        state["sources"] = []
        state["answer"] = (
            "Nu am putut genera un răspuns cu identificatori valizi ai surselor. Încercați din nou."
            if re.search(r"\b(care|raportul|din|pentru|rezumă|rezuma|compara|ce|cum)\b", state["raw_query"], re.I)
            else "I could not generate an answer with valid source identifiers. Please try again."
        )
        state.setdefault("trace", []).append("Citation validation failed; unsupported identifiers were not returned as an answer")

    usage = response.usage_metadata or {}
    cost = calculate_cost_usd(
        GENERATE_MODEL, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    )
    state["cost_usd"] = state.get("cost_usd", 0.0) + cost
    return state
