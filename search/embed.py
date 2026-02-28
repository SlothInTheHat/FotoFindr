"""
Text → CLIP vector embedding (512-dim, same space as stored image embeddings).
Delegating to pipeline/clip_embed so there is one model instance for both
indexing and search.
"""

from pipeline.clip_embed import embed_text_async


async def embed_text(text: str) -> list[float]:
    return await embed_text_async(text)
