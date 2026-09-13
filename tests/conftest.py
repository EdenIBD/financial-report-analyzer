import os

# embed.py instantiaza genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"])
# la nivel de modul — fara valoare in mediu, importul pica cu KeyError chiar
# si pentru teste care nu apeleaza API-ul real.
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-placeholder-project")
os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder-key")

# Database calls are mocked in unit tests; no live credentials required.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
