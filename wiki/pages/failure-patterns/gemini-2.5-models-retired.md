# gemini-2.5-flash / gemini-2.5-pro raspund 404 pentru cont nou

## Ce s-a intamplat

`src/agent/nodes/classify.py` (`CLASSIFY_MODEL = "gemini-2.5-flash"`) si
`src/agent/nodes/generate.py` (`GENERATE_MODEL = "gemini-2.5-pro"`) — alese initial
cu comentariu `# TODO: confirma modelul` — esuau la primul apel real prin
`ChatGoogleGenerativeAI`, cu:

```
404 NOT_FOUND: This model models/gemini-2.5-flash is no longer available to new
users. Please update your code to use models/gemini-3.6-flash...
```

La fel ca la `gemini-embedding-2` (vezi failure-pattern separat), modelul **apare
in catalogul `client.models.list()`**, dar nu e de fapt invocabil — de data asta
motivul e explicit in eroare: retras pentru conturi noi.

Eroarea aparea in graf ca `status: "error"` fara niciun detaliu, pentru ca
`handle_query` prinde orice exceptie din `graph.invoke()` intr-un `except Exception:`
generic, fara sa logheze mesajul (cod dat exact de spec). Diagnosticat rulind
`graph.invoke()` direct, in afara try/except-ului, ca sa vada traceback-ul real.

## Fix aplicat

Testat direct (`generate_content`, nu doar `models.list()`) mai multe modele
disponibile prin acelasi API key:

| Model | Rezultat |
|---|---|
| gemini-2.5-flash | 404 (retras) |
| gemini-2.5-pro | 404 (retras) |
| gemini-3.6-flash | OK |
| gemini-flash-latest | OK |
| gemini-pro-latest | OK |
| gemini-3.1-pro-preview | OK |

Ales `gemini-flash-latest` (classify) si `gemini-pro-latest` (generate) — alias-uri
"latest" in loc de versiuni fixe, ca sa nu se repete problema la urmatoarea retragere
de model.

## Cand sa revii aici

`handle_query` inghite tacut orice exceptie din graf — daca reapar erori "error"
fara raspuns, ruleaza `graph.invoke()` direct (fara try/except) ca sa vezi
traceback-ul real, nu presupune cauza.
