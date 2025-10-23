from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from app.models.common import LyricPayload, SimpleSong
from app.models.enums import SearchSourceEnum, SearchTypeEnum
from app.models.search import BlurSearchGroup
from app.models.common import Result


class MusicProvider(ABC):
    """
    Base class that mirrors the IMusicApi contract from the original project.
    """

    def __init__(self, cookie_supplier: callable[[], str | None]) -> None:
        self._cookie_supplier = cookie_supplier

    @property
    @abstractmethod
    def source(self) -> SearchSourceEnum:
        ...

    @abstractmethod
    async def get_playlist(self, playlist_id: str) -> Result[list[SimpleSong]]:
        ...

    @abstractmethod
    async def get_album(self, album_id: str) -> Result[list[SimpleSong]]:
        ...

    @abstractmethod
    async def get_songs(self, song_ids: Iterable[str]) -> dict[str, Result[SimpleSong]]:
        ...

    @abstractmethod
    async def get_song_link(self, song_id: str) -> Result[str]:
        ...

    @abstractmethod
    async def get_lyric(
        self, song_id: str, display_id: str | None = None, verbatim: bool = False
    ) -> Result[LyricPayload]:
        ...

    @abstractmethod
    async def search(self, keyword: str, search_type: SearchTypeEnum) -> Result[BlurSearchGroup]:
        ...
