from google import genai

from src.storage.cost import calculate_cost_usd

genai_client = genai.Client()
CONTEXT_MODEL = "gemini-3.1-flash-lite"  # exact cum a cerut spec-ul — verificat direct, functioneaza

def llm_call(prompt: str) -> tuple[str, float]:
    """Intoarce si costul real (din usage_metadata al raspunsului, nu estimat):
    ingestia live a unui filing face un apel per chunk, deci costul ei domina
    complet costul unui query si trebuie contabilizat in cost_usd."""
    response = genai_client.models.generate_content(model=CONTEXT_MODEL, contents=prompt)
    usage = response.usage_metadata
    cost = calculate_cost_usd(
        CONTEXT_MODEL,
        getattr(usage, "prompt_token_count", 0) or 0,
        getattr(usage, "candidates_token_count", 0) or 0,
    )
    return response.text.strip(), cost

def add_context(chunk_text: str, doc_id: str, section: str) -> tuple[str, float]:
    # DOUA BUG-URI REALE (2026-09-12), gasite citind efectiv chunk-uri retrieved
    # in UI, nu presupunand ca ies bune — vezi
    # wiki/pages/failure-patterns/contextual-retrieval-wrong-company.md:
    #
    # 1. doc_id era acceptat ca parametru dar nu ajungea niciodata in prompt —
    #    modelul trebuia sa GHICEASCA firma/anul doar din primele 300 caractere
    #    ale fragmentului si de multe ori ghicea gresit (~20-35% din chunk-urile
    #    MSFT/GOOGL/NVDA aveau propozitia de context "acest fragment vine de
    #    la Apple Inc."). Fix: doc_id e dat explicit modelului mai jos.
    #
    # 2. Chiar cu identificatorul dat explicit, gemini-3.1-flash-lite tot nu
    #    respecta un prompt formulat conversational — raspundea cu "Iata doua
    #    variante..." si text explicativ in loc de o propozitie directa, care
    #    ajungea stocat ca parte din chunk (inaintea embeddingului). Fix:
    #    instructiune stricta de output, o singura propozitie, fara alternative.
    context_prompt = f"""This fragment is from filing "{doc_id}", section "{section}".
Write exactly ONE short sentence stating this (use this exact identifier, do not guess
or substitute a different company/year). Output ONLY that sentence — no alternatives,
no explanations, no "here are two options".
Fragment: {chunk_text[:300]}..."""
    context, cost = llm_call(context_prompt)  # vezi TODO mai jos
    return f"{context}\n\n{chunk_text}", cost

# Aplicat uniform pe toate sectiunile, nu selectiv.
