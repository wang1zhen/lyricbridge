from __future__ import annotations

from app.config import AppSettings
from app.models.enums import SearchSourceEnum

from .providers.base import MusicProvider
from .providers.netease import NetEaseMusicProvider
from .providers.qq import QQMusicProvider

def _build_registry(settings: AppSettings) -> dict[SearchSourceEnum, MusicProvider]:
    # Do not lru_cache on AppSettings (unhashable). Build a small mapping on demand.
    return {
        SearchSourceEnum.NET_EASE: NetEaseMusicProvider(lambda: settings.provider.netease_cookie),
        SearchSourceEnum.QQ: QQMusicProvider(lambda: settings.provider.qq_cookie),
    }


def get_provider(source: SearchSourceEnum, settings: AppSettings) -> MusicProvider:
    registry = _build_registry(settings)
    try:
        return registry[source]
    except KeyError as exc:
        raise KeyError(f"Unsupported search source: {source}") from exc
