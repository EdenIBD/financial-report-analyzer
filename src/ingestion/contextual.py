from google import genai

genai_client = genai.Client()
CONTEXT_MODEL = "gemini-3.1-flash-lite"  # exact cum a cerut spec-ul — verificat direct, functioneaza

def llm_call(prompt: str) -> str:
    response = genai_client.models.generate_content(model=CONTEXT_MODEL, contents=prompt)
    return response.text.strip()

def add_context(chunk_text: str, doc_id: str, section: str) -> str:
    context_prompt = f"""Genereaza 1-2 propozitii scurte care situeaza urmatorul
fragment: din ce raport financiar vine (companie, an), din ce sectiune ({section}).
Fragment: {chunk_text[:300]}..."""
    context = llm_call(context_prompt)  # vezi TODO mai jos
    return f"{context}\n\n{chunk_text}"

# Aplicat uniform pe toate sectiunile, nu selectiv.
