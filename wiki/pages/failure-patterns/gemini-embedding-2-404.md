# gemini-embedding-2 raspunde 404 pe Vertex AI, desi apare in catalog

## Ce s-a intamplat

`src/retrieval/embed.py` folosea `model="gemini-embedding-2"` (marcat "confirmat" in
build-spec.md). La primul apel real `embed_content(model="gemini-embedding-2", ...)`
in modul Vertex AI (`genai.Client(vertexai=True, project=..., location="us-central1")`),
API-ul a raspuns:

```
404 NOT_FOUND: Publisher model
`projects/<proiect>/locations/us-central1/publishers/google/models/gemini-embedding-2`
was not found or your project does not have access to it.
```

`client.models.list()` chiar listeaza `publishers/google/models/gemini-embedding-2`
ca model existent — dar listarea nu garanteaza ca modelul e de fapt invocabil pentru
proiectul/regiunea curenta (posibil preview/allowlist, neclar din raspunsul API).

## Fix aplicat

Testat direct `gemini-embedding-001` (acelasi proiect, aceeasi regiune `us-central1`) —
functioneaza, si intoarce exact **3072 dimensiuni**, identic cu ce era deja configurat
in `qdrant_setup.py` (`VectorParams(size=3072)`). Schimbat `embed_document`/`embed_query`
din `src/retrieval/embed.py` sa foloseasca `gemini-embedding-001`. Nicio alta schimbare
de cod necesara — interfata `embed_content(..., config={"task_type": ...})` e identica.

## Cand sa revii aici

Daca modelul redevine indisponibil sau se schimba din nou pricing/versiune, verifica
intai empiric cu un apel real (`embed_content`) inainte sa presupui ca un nume de model
listat in catalog e si invocabil — `client.models.list()` nu e o garantie de acces real.
