from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

from .models import LyricType, OutputEncoding, OutputFormat, SearchSource, SearchType, ShowLrcType


CONFIG_DIR_NAME = "lyricbridge"
CONFIG_FILE_NAME = "config.json"


@dataclass
class AppConfig:
    search_source: str = SearchSource.NETEASE.value
    search_type: str = SearchType.SONG.value
    show_lrc_type: str = ShowLrcType.STAGGER.value
    lrc_merge_separator: str = " / "
    output_format: str = OutputFormat.LRC.value
    output_encoding: str = OutputEncoding.UTF_8.value
    output_filename_format: str = "${name} - ${singer}"
    output_lyric_types: List[str] = field(
        default_factory=lambda: [LyricType.ORIGINAL.value, LyricType.TRANSLATED.value]
    )
    singer_separator: str = ","
    ignore_empty_lines: bool = True
    prefer_verbatim: bool = False
    auto_translate_missing: bool = False
    translation_provider: str = "none"
    translation_target: str = "en"
    baidu_app_id: str = ""
    baidu_secret: str = ""
    caiyun_token: str = ""
    netease_cookie: str = ""
    qq_cookie: str = ""
    lrc_timestamp_format: str = "[mm:ss.SSS]"
    srt_timestamp_format: str = "HH:mm:ss,SSS"
    last_output_dir: str = ""


def config_path() -> Path:
    base_path = Path.home() / ".config"
    config_dir = base_path / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / CONFIG_FILE_NAME


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return AppConfig()

    default = AppConfig()
    data = asdict(default)
    for key, value in raw.items():
        if key in data:
            data[key] = value
    return AppConfig(**data)


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
