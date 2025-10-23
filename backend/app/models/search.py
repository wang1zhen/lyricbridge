from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field

from .common import Result, SongLyricBundle
from .enums import SearchSourceEnum, SearchTypeEnum
from .settings import SettingsState


class PreciseSearchRequest(BaseModel):
    search_text: str = Field(description="User input (IDs, URLs, or keywords depending on search type)")
    search_source: SearchSourceEnum = Field(default=SearchSourceEnum.NET_EASE)
    search_type: SearchTypeEnum = Field(default=SearchTypeEnum.SONG)
    include_verbatim: bool = Field(
        default=False, description="Whether to request verbatim (karaoke-mode) lyrics when available"
    )
    settings_override: SettingsState | None = Field(
        default=None,
        description="Optional override for settings used while executing the search. "
        "When omitted, persisted settings will be used.",
    )


class PreciseSearchResponse(BaseModel):
    results: List[SongLyricBundle] = Field(default_factory=list)
    errors: Dict[str, str] = Field(default_factory=dict)
    console_output: str | None = None
    summary: Result[str] = Field(default_factory=lambda: Result.ok("success"))


class BlurSearchRequest(BaseModel):
    keyword: str
    search_source: SearchSourceEnum = Field(default=SearchSourceEnum.NET_EASE)
    search_type: SearchTypeEnum = Field(default=SearchTypeEnum.SONG)
    aggregated: bool = Field(default=False, description="If true, perform blur search across all providers")


class BlurSearchEntry(BaseModel):
    display_id: str
    title: str
    subtitle: str | None = None
    album: str | None = None
    artist: list[str] = Field(default_factory=list)
    duration_ms: int | None = None
    extra: dict = Field(default_factory=dict)


class BlurSearchGroup(BaseModel):
    search_source: SearchSourceEnum
    search_type: SearchTypeEnum
    entries: list[BlurSearchEntry] = Field(default_factory=list)


class BlurSearchResponse(BaseModel):
    groups: list[BlurSearchGroup] = Field(default_factory=list)
