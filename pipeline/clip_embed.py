"""
CLIP embeddings — shared model for both images and text.

Using ViT-B-32/openai (512-dim). Because image and text live in the same
embedding space, a plain cosine similarity between a text query and a stored
image embedding is all you need for semantic search.

torch is already present via ultralytics, so open-clip-torch is lightweight.
"""

import asyncio
import io
from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=1)
def _load():
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai"
    )
    model.eval()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    return model, preprocess, tokenizer


def embed_image(image_bytes: bytes) -> list[float]:
    import torch

    model, preprocess, _ = _load()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(img).unsqueeze(0)
    with torch.no_grad():
        feat = model.encode_image(tensor)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat[0].tolist()


def embed_text(text: str) -> list[float]:
    import torch

    model, _, tokenizer = _load()
    tokens = tokenizer([text])
    with torch.no_grad():
        feat = model.encode_text(tokens)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat[0].tolist()


async def embed_image_async(image_bytes: bytes) -> list[float]:
    return await asyncio.to_thread(embed_image, image_bytes)


async def embed_text_async(text: str) -> list[float]:
    return await asyncio.to_thread(embed_text, text)
