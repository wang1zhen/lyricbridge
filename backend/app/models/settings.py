from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, validator

from .enums import (
    ChineseProcessRuleEnum,
    DotTypeEnum,
    LyricsTypeEnum,
    OutputEncodingEnum,
    OutputFormatEnum,
    SearchSourceEnum,
    SearchTypeEnum,
    ShowLrcTypeEnum,
    ThemeModeEnum,
    TransLyricLostRuleEnum,
    VerbatimLyricModeEnum,
)


class TransConfigModel(BaseModel):
    lost_rule: TransLyricLostRuleEnum = TransLyricLostRuleEnum.IGNORE
    match_precision_deviation: int = 0
    baidu_app_id: str = ""
    baidu_secret: str = ""
    caiyun_token: str = ""


class ConfigModel(BaseModel):
    lrc_timestamp_format: str = "[mm:ss.SSS]"
    srt_timestamp_format: str = "HH:mm:ss,SSS"
    verbatim_lyric_mode: VerbatimLyricModeEnum = VerbatimLyricModeEnum.DISABLE
    ignore_empty_lyric: bool = True
    dot_type: DotTypeEnum = DotTypeEnum.DOWN
    chinese_process_rule: ChineseProcessRuleEnum = ChineseProcessRuleEnum.IGNORE
    theme_mode: ThemeModeEnum = ThemeModeEnum.FOLLOW_SYSTEM
    singer_separator: str = ","
    aggregated_blur_search: bool = False
    auto_read_clipboard: bool = False
    auto_check_update: bool = True
    ignore_pure_music_in_save: bool = True
    separate_file_for_isolated: bool = False
    output_file_name_format: str = "${name} - ${singer}"
    output_lyric_types: list[LyricsTypeEnum] = Field(
        default_factory=lambda: [LyricsTypeEnum.ORIGIN, LyricsTypeEnum.ORIGIN_TRANS]
    )
    qq_music_cookie: str = ""
    netease_cookie: str = ""
    trans_config: TransConfigModel = Field(default_factory=TransConfigModel)


class PersistParamModel(BaseModel):
    search_source: SearchSourceEnum = SearchSourceEnum.NET_EASE
    search_type: SearchTypeEnum = SearchTypeEnum.SONG
    show_lrc_type: ShowLrcTypeEnum = ShowLrcTypeEnum.STAGGER
    lrc_merge_separator: str = ""
    output_file_format: OutputFormatEnum = OutputFormatEnum.LRC
    encoding: OutputEncodingEnum = OutputEncodingEnum.UTF_8


class SettingsState(BaseModel):
    config: ConfigModel = Field(default_factory=ConfigModel)
    param: PersistParamModel = Field(default_factory=PersistParamModel)


class SettingsPayload(SettingsState):
    storage_root: Annotated[Path | None, Field(description="Optional override for storage root directory")] = None


class SettingsResponse(SettingsState):
    storage_root: Path

    @validator("storage_root", pre=True, always=True)
    def _ensure_path(cls, value) -> Path:
        if isinstance(value, Path):
            return value
        if value is None:
            return Path.cwd()
        return Path(value)
