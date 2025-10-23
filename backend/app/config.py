from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(BaseSettings):
    netease_cookie: str = Field(default="", alias="NETEASE_COOKIE")
    qq_cookie: str = Field(default="", alias="QQ_COOKIE")

    baidu_app_id: str = Field(default="", alias="BAIDU_APP_ID")
    baidu_secret: str = Field(default="", alias="BAIDU_SECRET")
    baidu_qps_delay_ms: int = Field(default=1100, alias="BAIDU_QPS_DELAY_MS")

    caiyun_token: str = Field(default="", alias="CAIYUN_TOKEN")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppSettings(BaseSettings):
    version: str = "0.1.0"
    data_dir: Path = Field(default_factory=lambda: Path.cwd() / "runtime")
    cache_dir: Path | None = None
    artifacts_dir: Path | None = None
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "lyricbridge://app",  # new electron custom scheme
            "neo-musiclyric://app",  # legacy scheme for compatibility
            "null",  # allow Electron file:// origin (sent as 'Origin: null')
        ]
    )

    provider: ProviderConfig = Field(default_factory=ProviderConfig)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def ensure_runtime_dirs(self) -> dict[str, Path]:
        """
        Ensure directories that we rely on exist.
        """
        data_dir = self.data_dir
        cache_dir = self.cache_dir or data_dir / "cache"
        artifacts_dir = self.artifacts_dir or data_dir / "artifacts"

        for path in (data_dir, cache_dir, artifacts_dir):
            path.mkdir(parents=True, exist_ok=True)

        self.cache_dir = cache_dir
        self.artifacts_dir = artifacts_dir

        return {"data_dir": data_dir, "cache_dir": cache_dir, "artifacts_dir": artifacts_dir}


@lru_cache(1)
def get_settings() -> AppSettings:
    settings = AppSettings()
    settings.ensure_runtime_dirs()
    return settings


SettingsDependency = Annotated[AppSettings, Field(default_factory=get_settings)]
