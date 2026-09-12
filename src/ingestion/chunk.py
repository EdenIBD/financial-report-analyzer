from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " "],
)

def chunk_section(text: str) -> list[str]:
    """Aplicat separat pe fiecare sectiune extrasa (nu pe documentul brut)."""
    return splitter.split_text(text)
