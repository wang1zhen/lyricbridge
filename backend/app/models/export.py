from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field

from .common import Result
from .enums import SearchSourceEnum
from .settings import SettingsState


class ExportSongInput(BaseModel):
    id: str = Field(description="Provider-specific internal song identifier")
    display_id: str | None = Field(
        default=None, description="Display identifier (some providers differentiate between ids and mids)"
    )
    search_source: SearchSourceEnum = Field(default=SearchSourceEnum.NET_EASE)


class ExportBatchRequest(BaseModel):
    songs: list[ExportSongInput] = Field(default_factory=list)
    settings_override: SettingsState | None = None
    target_directory: str | None = Field(
        default=None,
        description="Optional path where the backend should persist exported files. When omitted, "
        "an artifact package is created and can be fetched through the download endpoint.",
    )


class ExportBatchResponse(BaseModel):
    success_count: int = 0
    skipped: Dict[str, str] = Field(default_factory=dict)
    artifact_id: str | None = None
    summary: Result[str] = Field(default_factory=lambda: Result.ok("success"))


class SongAssetRequest(BaseModel):
    songs: list[ExportSongInput]


class SongAssetResponse(BaseModel):
    assets: Dict[str, str] = Field(default_factory=dict)
    summary: Result[str] = Field(default_factory=lambda: Result.ok("success"))
