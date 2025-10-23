from fastapi import APIRouter, Depends

from app.models.search import (
    BlurSearchRequest,
    BlurSearchResponse,
    PreciseSearchRequest,
    PreciseSearchResponse,
)
from app.services.search import SearchService, get_search_service

router = APIRouter()


@router.post("/precise", response_model=PreciseSearchResponse, summary="Precise search by song/album/playlist IDs")
async def precise_search(
    payload: PreciseSearchRequest, service: SearchService = Depends(get_search_service)
) -> PreciseSearchResponse:
    return await service.precise_search(payload)


@router.post("/blur", response_model=BlurSearchResponse, summary="Fuzzy keyword search")
async def blur_search(
    payload: BlurSearchRequest, service: SearchService = Depends(get_search_service)
) -> BlurSearchResponse:
    return await service.blur_search(payload)
