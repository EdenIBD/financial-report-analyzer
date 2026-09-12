import os
from google import genai

genai_client = genai.Client(
    vertexai=True,
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
)

def embed_document(text: str) -> list[float]:
    result = genai_client.models.embed_content(
        model="gemini-embedding-001",  # gemini-embedding-2 e listat dar raspunde 404 pe acest proiect Vertex — vezi wiki/pages/failure-patterns
        contents=text,
        config={"task_type": "RETRIEVAL_DOCUMENT"},
    )
    return result.embeddings[0].values

def embed_query(text: str) -> list[float]:
    result = genai_client.models.embed_content(
        model="gemini-embedding-001",  # gemini-embedding-2 e listat dar raspunde 404 pe acest proiect Vertex — vezi wiki/pages/failure-patterns
        contents=text,
        config={"task_type": "RETRIEVAL_QUERY"},
    )
    return result.embeddings[0].values

# Important: RETRIEVAL_DOCUMENT la indexare, RETRIEVAL_QUERY la query — nu inversa
# (bug cunoscut, deja intalnit pe alt proiect).
