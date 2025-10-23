from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import AppSettings, get_settings
from app.models.common import Result
from app.models.enums import SearchSourceEnum
from app.models.export import (
    ExportBatchRequest,
    ExportBatchResponse,
    SongAssetRequest,
    SongAssetResponse,
)
from app.models.settings import SettingsState
from app.services.search import SearchService, get_search_service
from .music.registry import get_provider


class ExportService:
    def __init__(self, app_settings: AppSettings, search_service: SearchService) -> None:
        self._settings = app_settings
        self._search_service = search_service
        self._settings.ensure_runtime_dirs()

    async def _resolve_settings(self, override: SettingsState | None) -> SettingsState:
        if override is not None:
            return override
        state = await self._search_service._resolve_settings(None)  # leverage search service helper
        return state

    async def export_batch(self, payload: ExportBatchRequest) -> ExportBatchResponse:
        if not payload.songs:
            return ExportBatchResponse(summary=Result.fail("您必须先搜索，才能保存内容"))

        settings_state = await self._resolve_settings(payload.settings_override)

        artifact_id = uuid.uuid4().hex
        out_root = Path(payload.target_directory) if payload.target_directory else (self._settings.artifacts_dir / artifact_id)
        await asyncio.to_thread(out_root.mkdir, True, True)

        success = 0
        skipped: dict[str, str] = {}

        # Encoding from settings
        encoding = (settings_state.param.encoding or "utf-8")

        for item in payload.songs:
            try:
                provider = get_provider(item.search_source, self._settings)
                song_map = await provider.get_songs([item.id])
                song_vo = song_map.get(item.id)
                if not song_vo or not song_vo.success or not song_vo.data:
                    skipped[item.id] = song_vo.error if song_vo else "歌曲信息获取失败"
                    continue

                song = song_vo.data
                lyric_res = await provider.get_lyric(item.id, item.display_id or song.display_id, False)
                if not lyric_res.success or not lyric_res.data:
                    skipped[item.id] = lyric_res.error or "歌词获取失败"
                    continue

                text = lyric_res.data.origin or lyric_res.data.translation or lyric_res.data.transliteration or ""
                srt = _lrc_to_srt(text)
                if not srt:
                    # write plain text as fallback
                    srt = text

                filename_base = song.name or item.display_id or item.id
                safe_name = _safe_filename(filename_base)
                out_path = out_root / f"{safe_name}.srt"
                await asyncio.to_thread(out_path.write_text, srt, encoding)
                success += 1
            except Exception as e:  # noqa: BLE001
                skipped[item.id] = f"导出失败: {e}"

        artifact_path: Path | None = None
        if not payload.target_directory:
            # Zip outputs
            artifact_path = self._settings.artifacts_dir / f"{artifact_id}.zip"
            await asyncio.to_thread(self._zip_dir, out_root, artifact_path)

        summary = Result.ok("success") if success else Result.fail("保存失败或无可保存内容")
        return ExportBatchResponse(success_count=success, skipped=skipped, artifact_id=(artifact_path.name if artifact_path else None), summary=summary)

    async def get_song_links(self, payload: SongAssetRequest) -> SongAssetResponse:
        if not payload.songs:
            return SongAssetResponse(summary=Result.fail("您必须先搜索，才能获取歌曲链接"))

        # TODO: use provider.get_song_link for each song.
        assets = {song.id: "未实现" for song in payload.songs}
        return SongAssetResponse(assets=assets, summary=Result.fail("歌曲链接功能尚未实现"))

    async def get_song_pics(self, payload: SongAssetRequest) -> SongAssetResponse:
        if not payload.songs:
            return SongAssetResponse(summary=Result.fail("您必须先搜索，才能获取歌曲封面"))

        # TODO: return song pictures derived from song metadata (requires caching search results).
        assets = {song.id: "未实现" for song in payload.songs}
        return SongAssetResponse(assets=assets, summary=Result.fail("歌曲封面功能尚未实现"))

    async def download_artifact(self, artifact_id: str) -> FileResponse:
        artifact_path = self._settings.artifacts_dir / f"{artifact_id}.zip"
        if not artifact_path.exists():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path=artifact_path, filename=artifact_path.name, media_type="application/zip")

    @staticmethod
    def _create_placeholder_artifact(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    @staticmethod
    def _zip_dir(src_dir: Path, zip_path: Path) -> None:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
            for p in src_dir.rglob("*"):
                if p.is_file():
                    zf.write(p, p.name)


def _safe_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    return "".join(c if c not in bad else "_" for c in name).strip() or "lyric"


def _lrc_to_srt(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    entries: list[tuple[int, str]] = []
    import re

    time_re = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
    for raw in lines:
        last = 0
        times: list[int] = []
        for m in time_re.finditer(raw):
            mm = int(m.group(1) or 0)
            ss = int(m.group(2) or 0)
            frac = (m.group(3) or "0").ljust(3, "0")[:3]
            ms = int(frac)
            times.append(mm * 60000 + ss * 1000 + ms)
            last = m.end()
        content = raw[last:].strip()
        if times and content:
            entries.extend((t, content) for t in times)
    if not entries:
        return ""
    entries.sort(key=lambda x: x[0])

    def stamp(ms: int) -> str:
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        mm = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{mm:03d}"

    blocks: list[str] = []
    for i, (start, content) in enumerate(entries):
        end = (entries[i + 1][0] if i + 1 < len(entries) else start + 3000) - 1
        if end < start + 500:
            end = start + 500
        blocks.append(str(i + 1))
        blocks.append(f"{stamp(start)} --> {stamp(end)}")
        blocks.append(content)
        blocks.append("")
    return "\n".join(blocks)


def get_export_service(
    settings: AppSettings = Depends(get_settings), search_service: SearchService = Depends(get_search_service)
) -> ExportService:
    return ExportService(settings, search_service)
