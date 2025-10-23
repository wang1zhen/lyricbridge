from __future__ import annotations

import asyncio
from typing import Dict, Iterable, List

from fastapi import Depends

from app.config import AppSettings, get_settings
from app.models.common import Result, SongLyricBundle
from app.models.enums import SearchSourceEnum, SearchTypeEnum
from app.models.search import (
    BlurSearchRequest,
    BlurSearchResponse,
    BlurSearchGroup,
    PreciseSearchRequest,
    PreciseSearchResponse,
)
from app.models.settings import SettingsState
from app.services.settings import SettingsService, get_settings_service

from .music.registry import get_provider


class SearchService:
    def __init__(self, app_settings: AppSettings, settings_service: SettingsService) -> None:
        self._app_settings = app_settings
        self._settings_service = settings_service

    async def _resolve_settings(self, override: SettingsState | None) -> SettingsState:
        if override is not None:
            return override
        response = await self._settings_service.read_settings()
        return SettingsState(config=response.config, param=response.param)

    async def precise_search(self, payload: PreciseSearchRequest) -> PreciseSearchResponse:
        settings = await self._resolve_settings(payload.settings_override)

        # New behavior: accept exactly one URL and extract a single song id/provider
        token = (payload.search_text or "").strip()
        if not token:
            return PreciseSearchResponse(summary=Result.fail("请输入有效的歌曲链接（URL）"))

        # Trim wrappers like [url]
        if token.startswith("[") and token.endswith("]") and len(token) > 2:
            token = token[1:-1].strip()

        provider_source: SearchSourceEnum | None = None
        song_id: str | None = None
        display_id: str | None = None

        if "music.163.com" in token:
            provider_source = SearchSourceEnum.NET_EASE
            if "id=" in token:
                part = token.split("id=")[-1]
                digits = "".join(ch for ch in part if ch.isdigit())
                if digits:
                    song_id = digits
                    display_id = digits
        elif "y.qq.com" in token or ".qq.com" in token:
            provider_source = SearchSourceEnum.QQ
            if "songmid=" in token:
                part = token.split("songmid=")[-1]
                part = part.split("&")[0]
                display_id = part.strip()
                song_id = display_id
            elif "/songDetail/" in token:
                part = token.split("/songDetail/")[-1]
                part = part.split("?")[0]
                display_id = part.strip()
                song_id = display_id
            elif "songid=" in token:
                part = token.split("songid=")[-1]
                part = part.split("&")[0]
                song_id = part.strip()
                display_id = song_id

        if provider_source is None or not song_id:
            return PreciseSearchResponse(summary=Result.fail("无法从链接解析来源或歌曲 ID，仅支持单曲 URL"))

        provider = get_provider(provider_source, self._app_settings)

        song_map = await provider.get_songs([song_id])

        results: List[SongLyricBundle] = []
        errors: Dict[str, str] = {}

        async def fetch_bundle(index: int, song_id: str) -> SongLyricBundle | None:
            result_vo = song_map.get(song_id)
            if result_vo is None or not result_vo.success or result_vo.data is None:
                errors[song_id] = result_vo.error if result_vo else "歌曲信息暂未被收录或查询失败"
                return None

            song = result_vo.data
            lyric_res = await provider.get_lyric(song_id, song.display_id, payload.include_verbatim)
            if not lyric_res.success or lyric_res.data is None:
                errors[song_id] = lyric_res.error or "歌词信息暂未被收录或查询失败"
                return None

            return SongLyricBundle(index=index, song=song, lyric=lyric_res.data, duration_ms=song.duration_ms)

        bundles = await asyncio.gather(fetch_bundle(1, song_id))

        for bundle in bundles:
            if bundle is not None:
                results.append(bundle)

        console_output = None

        summary = Result.ok("success") if results else Result.fail("查询结果为空，请修改查询条件")
        return PreciseSearchResponse(results=results, errors=errors, console_output=console_output, summary=summary)

    async def blur_search(self, payload: BlurSearchRequest) -> BlurSearchResponse:
        if payload.aggregated:
            providers = [get_provider(source, self._app_settings) for source in SearchSourceEnum]
        else:
            providers = [get_provider(payload.search_source, self._app_settings)]

        groups: List[BlurSearchGroup] = []

        for provider in providers:
            result = await provider.search(payload.keyword.strip(), payload.search_type)
            if result.success and result.data:
                groups.append(result.data)

        return BlurSearchResponse(groups=groups)


def get_search_service(
    settings: AppSettings = Depends(get_settings), settings_service: SettingsService = Depends(get_settings_service)
) -> SearchService:
    return SearchService(settings, settings_service)
