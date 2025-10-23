from __future__ import annotations

from typing import Iterable, Any

import httpx

from app.models.common import LyricPayload, Result, SimpleSong
from app.models.enums import SearchSourceEnum, SearchTypeEnum
from app.models.search import BlurSearchGroup, BlurSearchEntry

from .base import MusicProvider


class NetEaseMusicProvider(MusicProvider):
    source = SearchSourceEnum.NET_EASE

    async def get_playlist(self, playlist_id: str) -> Result[list[SimpleSong]]:
        return Result.fail("网易云歌单查询尚未实现")

    async def get_album(self, album_id: str) -> Result[list[SimpleSong]]:
        return Result.fail("网易云专辑查询尚未实现")

    async def get_songs(self, song_ids: Iterable[str]) -> dict[str, Result[SimpleSong]]:
        mapping: dict[str, Result[SimpleSong]] = {}
        ids = [str(x) for x in song_ids]

        # Query detail API per id to keep implementation simple and robust
        cookie = self._cookie_supplier() or ""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://music.163.com/",
            "Accept": "application/json, text/plain, */*",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            for sid in ids:
                try:
                    # song detail endpoint; ids as JSON array string
                    resp = await client.get(
                        "https://music.163.com/api/song/detail",
                        params={"ids": f"[{sid}]"},
                    )
                    if resp.status_code != 200:
                        mapping[sid] = Result.fail(f"HTTP {resp.status_code}")
                        continue
                    data = resp.json()
                    songs = (data or {}).get("songs") or []
                    if not songs:
                        mapping[sid] = Result.fail("未找到歌曲详情")
                        continue
                    s = songs[0]
                    name = s.get("name") or sid
                    artists = [a.get("name") for a in (s.get("artists") or s.get("ar") or []) if a.get("name")]
                    album = ((s.get("album") or s.get("al") or {}).get("name")) or ""
                    duration_ms = int(s.get("duration") or s.get("dt") or 0)

                    mapping[sid] = Result.ok(
                        SimpleSong(
                            id=sid,
                            display_id=sid,
                            name=name,
                            singer=artists,
                            album=album,
                            duration_ms=duration_ms,
                        )
                    )
                except Exception:
                    mapping[sid] = Result.fail("歌曲详情解析失败")

        return mapping

    async def get_song_link(self, song_id: str) -> Result[str]:
        return Result.fail("网易云试听链接尚未实现")

    async def get_lyric(
        self, song_id: str, display_id: str | None = None, verbatim: bool = False
    ) -> Result[LyricPayload]:
        # Implements lyric retrieval via the public lyric API endpoint. Requires a valid cookie for best reliability.
        # API shape typically returns keys: lrc, tlyric, klyric, yrc, romalrc
        url = "https://music.163.com/api/song/lyric"
        params = {
            "id": song_id,
            # Request all variants where possible
            "lv": "-1",  # normal lrc
            "kv": "-1",  # karaoke lrc (klyric)
            "tv": "-1",  # translated lrc (tlyric)
        }

        cookie = self._cookie_supplier() or ""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://music.163.com/",
            "Accept": "application/json, text/plain, */*",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                return Result.fail(f"网络请求失败: {e}")

        if resp.status_code != 200:
            return Result.fail(f"HTTP {resp.status_code}")

        try:
            data: dict[str, Any] = resp.json()
        except Exception:
            return Result.fail("无法解析歌词响应")

        def _extract(field: str) -> str | None:
            node = data.get(field)
            if isinstance(node, dict):
                text = node.get("lyric")
                if isinstance(text, str) and text.strip():
                    return text
            return None

        lrc = _extract("lrc")
        tlyric = _extract("tlyric")
        klyric = _extract("klyric") or _extract("yrc")
        romalrc = _extract("romalrc")

        # When requesting verbatim mode, prefer klyric/yrc if present
        origin = (klyric or lrc) if verbatim else (lrc or klyric or romalrc)

        if not any([origin, tlyric, romalrc]):
            return Result.fail("未获取到歌词（可能需要有效 Cookie）")

        payload = LyricPayload(
            origin=origin,
            translation=tlyric,
            transliteration=romalrc,
            pinyin=None,
            is_pure_music=_is_pure_music(origin or ""),
            search_source=self.source,
        )
        return Result.ok(payload)

    async def search(self, keyword: str, search_type: SearchTypeEnum) -> Result[BlurSearchGroup]:
        if search_type != SearchTypeEnum.SONG:
            # Minimal implementation focuses on song search first
            return Result.ok(BlurSearchGroup(search_source=self.source, search_type=search_type, entries=[]))

        url = "https://music.163.com/api/cloudsearch/pc"
        params = {"type": 1, "s": keyword, "limit": 10}

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://music.163.com/",
            "Accept": "application/json, text/plain, */*",
        }
        cookie = self._cookie_supplier() or ""
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code != 200:
                    return Result.fail(f"HTTP {resp.status_code}")
                data = resp.json()
            except httpx.HTTPError as e:
                return Result.fail(f"网络请求失败: {e}")
            except Exception:
                return Result.fail("无法解析搜索响应")

        songs = (data or {}).get("result", {}).get("songs", []) or []
        entries: list[BlurSearchEntry] = []
        for s in songs:
            try:
                sid = str(s.get("id"))
                title = s.get("name") or sid
                artists = [a.get("name") for a in (s.get("ar") or []) if a.get("name")]
                album = (s.get("al") or {}).get("name")
                duration = s.get("dt")
                entries.append(
                    BlurSearchEntry(
                        display_id=sid,
                        title=title,
                        subtitle=None,
                        album=album,
                        artist=artists,
                        duration_ms=duration,
                        extra={},
                    )
                )
            except Exception:
                continue

        return Result.ok(BlurSearchGroup(search_source=self.source, search_type=search_type, entries=entries))


def _is_pure_music(text: str) -> bool:
    norm = text.lower()
    return ("纯音乐" in text) or ("instrumental" in norm)
