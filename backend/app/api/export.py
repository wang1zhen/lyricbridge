from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.models.export import (
    ExportBatchRequest,
    ExportBatchResponse,
    SongAssetRequest,
    SongAssetResponse,
)
from app.services.export import ExportService, get_export_service

router = APIRouter()


@router.post("/lyrics", response_model=ExportBatchResponse, summary="Export lyrics for one or many songs")
async def export_lyrics(
    payload: ExportBatchRequest, service: ExportService = Depends(get_export_service)
) -> ExportBatchResponse:
    return await service.export_batch(payload)


@router.post("/song-link", response_model=SongAssetResponse, summary="Retrieve streaming link for songs")
async def song_link(
    payload: SongAssetRequest, service: ExportService = Depends(get_export_service)
) -> SongAssetResponse:
    return await service.get_song_links(payload)


@router.post("/song-pic", response_model=SongAssetResponse, summary="Retrieve album artwork links for songs")
async def song_pic(
    payload: SongAssetRequest, service: ExportService = Depends(get_export_service)
) -> SongAssetResponse:
    return await service.get_song_pics(payload)


@router.get("/download/{artifact_id}", summary="Download packaged artifact produced during export")
async def download_artifact(
    artifact_id: str, service: ExportService = Depends(get_export_service)
) -> FileResponse:
    return await service.download_artifact(artifact_id)
