from __future__ import annotations

from typing import Iterable, Any

import base64
import time
import httpx
import json

from app.models.common import LyricPayload, Result, SimpleSong
from app.models.enums import SearchSourceEnum, SearchTypeEnum
from app.models.search import BlurSearchGroup

from .base import MusicProvider


class QQMusicProvider(MusicProvider):
    source = SearchSourceEnum.QQ

    async def get_playlist(self, playlist_id: str) -> Result[list[SimpleSong]]:
        return Result.fail("QQ 音乐歌单查询尚未实现")

    async def get_album(self, album_id: str) -> Result[list[SimpleSong]]:
        return Result.fail("QQ 音乐专辑查询尚未实现")

    async def get_songs(self, song_ids: Iterable[str]) -> dict[str, Result[SimpleSong]]:
        mapping: dict[str, Result[SimpleSong]] = {}
        cookie = self._cookie_supplier() or ""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://y.qq.com/",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://y.qq.com",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            for raw in song_ids:
                mid = str(raw)
                try:
                    params = {
                        "songmid": mid,
                        "tpl": "yqq_song_detail",
                        "format": "json",
                        "platform": "yqq",
                    }
                    resp = await client.get(
                        "https://c.y.qq.com/v8/fcg-bin/fcg_play_single_song.fcg", params=params
                    )
                    if resp.status_code != 200:
                        mapping[mid] = Result.fail(f"HTTP {resp.status_code}")
                        continue
                    data = resp.json()
                    lst = data.get("data") or []
                    if not lst:
                        mapping[mid] = Result.fail("未找到歌曲详情")
                        continue
                    s = lst[0]
                    name = s.get("name") or s.get("songname") or mid
                    singers = [a.get("name") for a in (s.get("singer") or []) if a.get("name")]
                    album = (s.get("album") or {}).get("name") or s.get("albumname") or ""
                    # duration might be in seconds ('interval')
                    interval = s.get("interval")
                    duration_ms = int(float(interval) * 1000) if interval else 0

                    mapping[mid] = Result.ok(
                        SimpleSong(
                            id=mid,
                            display_id=mid,
                            name=name,
                            singer=singers,
                            album=album,
                            duration_ms=duration_ms,
                        )
                    )
                except Exception:
                    mapping[mid] = Result.fail("歌曲详情解析失败")

        return mapping

    async def get_song_link(self, song_id: str) -> Result[str]:
        return Result.fail("QQ 音乐试听链接尚未实现")

    async def get_lyric(
        self, song_id: str, display_id: str | None = None, verbatim: bool = False
    ) -> Result[LyricPayload]:
        # Use QQ Music lyric API. Prefer songmid when available (QQ uses songmid widely).
        songmid = display_id or song_id

        base_url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
        params = {
            "songmid": songmid,
            "format": "json",
            "nobase64": "1",
            "platform": "yqq.json",
            "pcachetime": str(int(time.time() * 1000)),
        }

        cookie = self._cookie_supplier() or ""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://y.qq.com/",
            "Accept": "application/json, text/plain, */*",
            # Some deployments require an Origin; add a permissive one
            "Origin": "https://y.qq.com",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(base_url, params=params, headers=headers)
            except httpx.HTTPError as e:
                return Result.fail(f"网络请求失败: {e}")

        if resp.status_code != 200:
            return Result.fail(f"HTTP {resp.status_code}")

        # Some mirrors return JSONP even when format=json; strip if needed
        text = resp.text.strip()
        if text.startswith("callback(") and text.endswith(")"):
            text = text[len("callback(") : -1]

        try:
            data: dict[str, Any] = resp.json() if text == resp.text else json.loads(text)
        except Exception:
            # Retry with nobase64=0 and manual decode as a fallback
            try:
                fb_params = {**params, "nobase64": "0"}
                async with httpx.AsyncClient(timeout=15) as client:
                    fb_resp = await client.get(base_url, params=fb_params, headers=headers)
                fb_data: dict[str, Any] = fb_resp.json()
            except Exception:
                return Result.fail("无法解析歌词响应")
            data = fb_data

        def _get_field(key: str) -> str | None:
            val = data.get(key)
            if not val:
                return None
            if isinstance(val, str):
                return val if val.strip() else None
            return None

        origin = _get_field("lyric")
        translation = _get_field("trans") or _get_field("transcode")

        # Fallback: try base64 decoding if strings look encoded (when nobase64=0)
        def _try_b64(s: str | None) -> str | None:
            if not s:
                return None
            try:
                decoded = base64.b64decode(s).decode("utf-8", errors="ignore")
                return decoded if decoded.strip() else None
            except Exception:
                return s

        if origin and "[" not in origin and ":" not in origin:
            origin = _try_b64(origin)
        if translation and "[" not in translation and ":" not in translation:
            translation = _try_b64(translation)

        if not origin and not translation:
            return Result.fail("未获取到歌词（可能需要有效 Cookie 或 songmid）")

        payload = LyricPayload(
            origin=origin,
            translation=translation,
            transliteration=None,
            pinyin=None,
            is_pure_music=_is_pure_music(origin or ""),
            search_source=self.source,
        )
        return Result.ok(payload)

    async def search(self, keyword: str, search_type: SearchTypeEnum) -> Result[BlurSearchGroup]:
        return Result.ok(BlurSearchGroup(search_source=self.source, search_type=search_type, entries=[]))


def _is_pure_music(text: str) -> bool:
    norm = text.lower()
    return ("纯音乐" in text) or ("instrumental" in norm)
