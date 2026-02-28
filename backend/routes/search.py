from fastapi import APIRouter
from backend.models import SearchRequest, SearchResult, PhotoMetadata
from backend.db import search_photos_by_vector
from search.embed import embed_text
from search.query import parse_filters
from search.narration import generate_narration

router = APIRouter()


@router.post("/", response_model=SearchResult)
async def search_photos(req: SearchRequest):
    # 1. Embed the natural language query
    embedding = await embed_text(req.query)

    # 2. Extract structured filters from query text
    filters = parse_filters(req.query)

    # 3. Vector similarity search with metadata filters
    rows = search_photos_by_vector(
        embedding=embedding,
        user_id=str(req.user_id),
        filters=filters,
        limit=req.limit,
    )

    photos = [PhotoMetadata(**row) for row in rows]

    # 4. Generate ElevenLabs narration
    narration_text, narration_url = await generate_narration(req.query, photos)

    return SearchResult(
        photos=photos,
        narration=narration_url,
        narration_text=narration_text,
        total=len(photos),
    )
