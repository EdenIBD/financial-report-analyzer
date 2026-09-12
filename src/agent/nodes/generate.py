from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.state import AgentState, Persona
from src.storage.cost import calculate_cost_usd

GENERATE_MODEL = "gemini-pro-latest"  # gemini-2.5-pro raspundea 404 (retras) — vezi wiki/pages/failure-patterns

PERSONA_TONE = {
    Persona.LEGAL: "Fii precis, citeaza exact sectiunea/clauza, ton prudent, semnaleaza explicit riscul legal.",
    Persona.AUDIT_FIRM: "Concentreaza-te pe cifre si controale, citeaza exact situatia/nota, semnaleaza orice discrepanta.",
    Persona.INVESTMENT_FIRM: "Ton narativ, concentreaza-te pe factorii care determina performanta, perspectiva forward-looking.",
    Persona.INVESTMENT_BANK: "Concis, concentrat pe structura de capital si metrici relevante pentru tranzactii.",
    Persona.TREASURY: "Concentreaza-te pe cifre de lichiditate/cash, semnaleaza riscul de deficit de numerar.",
}

BASE_PROMPT = """Esti un asistent care raspunde la intrebari despre rapoarte financiare 10-K
(Apple, Microsoft, Google), folosind EXCLUSIV fragmentele de context furnizate.

Reguli:
- Raspunde doar din context; daca informatia nu e in context, spune explicit asta.
- Pentru fiecare afirmatie, citeaza sursa in formatul [chunk_id] (identificatorul din paranteze la inceputul fiecarui fragment de context).
- Nu inventa cifre sau fapte care nu apar in context.

{persona_tone}

Context:
{context}

Intrebare: {query}"""

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

    usage = response.usage_metadata or {}
    cost = calculate_cost_usd(
        "gemini-generate-model", usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    )
    state["cost_usd"] = state.get("cost_usd", 0.0) + cost
    return state
