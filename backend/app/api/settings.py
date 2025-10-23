from fastapi import APIRouter, Depends

from app.models.settings import SettingsPayload, SettingsResponse
from app.services.settings import SettingsService, get_settings_service

router = APIRouter()


@router.get("/", response_model=SettingsResponse, summary="Fetch persisted application settings")
async def read_settings(service: SettingsService = Depends(get_settings_service)) -> SettingsResponse:
    return await service.read_settings()


@router.put("/", response_model=SettingsResponse, summary="Persist application settings")
async def update_settings(
    payload: SettingsPayload, service: SettingsService = Depends(get_settings_service)
) -> SettingsResponse:
    return await service.write_settings(payload)
