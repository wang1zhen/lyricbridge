from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from .enums import SearchSourceEnum


T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    success: bool = Field(default=True, description="Flag that indicates whether the operation succeeded")
    error: str | None = Field(default=None, description="Error message if success is False")
    data: T | None = Field(default=None, description="Payload returned by the operation")

    @classmethod
    def ok(cls, data: T) -> "Result[T]":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "Result[T]":
        return cls(success=False, error=error)


class SimpleSong(BaseModel):
    id: str
    display_id: str
    name: str
    singer: list[str] = Field(default_factory=list)
    album: str = ""
    duration_ms: int = 0


class LyricPayload(BaseModel):
    origin: str | None = None
    translation: str | None = None
    transliteration: str | None = None
    pinyin: str | None = None
    is_pure_music: bool = False
    search_source: SearchSourceEnum


class SongLyricBundle(BaseModel):
    index: int
    song: SimpleSong
    lyric: LyricPayload
    duration_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
