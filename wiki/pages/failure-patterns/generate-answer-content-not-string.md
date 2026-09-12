# response.content nu e mereu string — gemini-pro-latest intoarce blocuri structurate

## Ce s-a intamplat

`generate_answer` facea `state["answer"] = response.content`, presupunand
ca raspunsul LangChain e intotdeauna un string simplu. Cu `gemini-pro-latest`,
`response.content` poate fi o lista de blocuri structurate
(`[{"type": "text", "text": "...", "extras": {"signature": "..."}}]`), nu un
string — probabil legat de un mecanism de "thinking"/semnatura al modelului.

FastAPI valida raspunsul `/query` contra `QueryResponse` (care declara
`answer: str | None`), asa ca orice raspuns generat cu succes de LLM
arunca `ResponseValidationError` si `/query` intorcea **500 Internal Server
Error** — un raspuns bun, generat corect, era aruncat la ultimul pas.

## Fix aplicat

Inlocuit `response.content` cu `response.text` — proprietatea LangChain care
extrage robust textul indiferent daca `content` e string sau lista de
blocuri (verificat direct: functioneaza pentru ambele forme).

## Cand sa revii aici

Orice alt loc care citeste `.content` direct de pe un raspuns LangChain
(nu doar `generate.py`) ar trebui sa foloseasca `.text` in loc, ca sa nu
depinda de forma exacta intoarsa de un anume model.
