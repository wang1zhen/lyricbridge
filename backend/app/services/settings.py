from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import Depends

from app.config import AppSettings, get_settings
from app.models.settings import SettingsPayload, SettingsResponse, SettingsState


class SettingsService:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._settings.ensure_runtime_dirs()
        self._settings_path = self._settings.data_dir / "settings.json"

    async def read_settings(self) -> SettingsResponse:
        if not self._settings_path.exists():
            state = SettingsState()
        else:
            state = await asyncio.to_thread(self._load_state)

        storage_root = self._settings.data_dir
        return SettingsResponse(**state.dict(), storage_root=storage_root)

    async def write_settings(self, payload: SettingsPayload) -> SettingsResponse:
        state = SettingsState(
            config=payload.config,
            param=payload.param,
        )

        storage_root = payload.storage_root or self._settings.data_dir

        await asyncio.to_thread(self._dump_state, state, storage_root)

        return SettingsResponse(**state.dict(), storage_root=storage_root)

    def _load_state(self) -> SettingsState:
        with self._settings_path.open("r", encoding="utf-8") as fp:
            raw = json.load(fp)
        return SettingsState(**raw)

    def _dump_state(self, state: SettingsState, storage_root: Path) -> None:
        storage_root.mkdir(parents=True, exist_ok=True)
        tmp_path = self._settings_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fp:
            json.dump(state.model_dump(mode="json"), fp, ensure_ascii=False, indent=2)
        tmp_path.replace(self._settings_path)


def get_settings_service(settings: AppSettings = Depends(get_settings)) -> SettingsService:
    return SettingsService(settings)
