import tiktoken

ENCODING_NAME = "cl100k_base"  # confirmat
encoding = tiktoken.get_encoding(ENCODING_NAME)

def count_tokens(text: str) -> int:
    """Doar pentru dimensionarea chunk-urilor (chunks.token_count).
    Costul real (src/storage/cost.py) se calculeaza din usage-ul returnat
    de API la fiecare apel, nu din acest tokenizer aproximativ."""
    return len(encoding.encode(text))
