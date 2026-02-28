"""
Text → vector embedding via OpenAI text-embedding-3-small.
Used for both photo indexing and query embedding.
"""

from openai import AsyncOpenAI
from backend.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)

EMBED_MODEL = "text-embedding-3-small"


async def embed_text(text: str) -> list[float]:
    text = text.strip().replace("\n", " ")
    response = await client.embeddings.create(model=EMBED_MODEL, input=text)
    return response.data[0].embedding
