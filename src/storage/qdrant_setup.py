import os

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, TextIndexParams, TokenizerType

# QDRANT_URL: "http://localhost:6333" local (implicit), "http://qdrant:6333" in docker-compose
client = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))

client.create_collection(
    collection_name="financial_reports",
    vectors_config=VectorParams(size=3072, distance=Distance.COSINE),  # gemini-embedding-001, dimensiune confirmata
)

client.create_payload_index(
    collection_name="financial_reports",
    field_name="text",
    field_schema=TextIndexParams(type="text", tokenizer=TokenizerType.WORD, min_token_len=2, lowercase=True),
)
