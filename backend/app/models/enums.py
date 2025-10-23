from __future__ import annotations

from enum import Enum


class SearchSourceEnum(str, Enum):
    NET_EASE = "netease"
    QQ = "qq"


class SearchTypeEnum(str, Enum):
    SONG = "song"
    ALBUM = "album"
    PLAYLIST = "playlist"


class ShowLrcTypeEnum(str, Enum):
    STAGGER = "stagger"
    ISOLATED = "isolated"
    MERGE = "merge"


class VerbatimLyricModeEnum(str, Enum):
    DISABLE = "disable"
    STANDARD = "standard"
    A2 = "a2"


class DotTypeEnum(str, Enum):
    DOWN = "down"
    HALF_UP = "half_up"


class OutputEncodingEnum(str, Enum):
    UTF_8 = "utf-8"
    UTF_8_BOM = "utf-8-sig"
    UTF_32 = "utf-32"
    UNICODE = "utf-16-le"


class OutputFormatEnum(str, Enum):
    LRC = "lrc"
    SRT = "srt"


class TransLyricLostRuleEnum(str, Enum):
    IGNORE = "ignore"
    EMPTY_LINE = "empty_line"
    FILL_ORIGIN = "fill_origin"


class ChineseProcessRuleEnum(str, Enum):
    IGNORE = "ignore"
    SIMPLIFIED = "simplified"
    TRADITIONAL = "traditional"


class LyricsTypeEnum(str, Enum):
    ORIGIN = "origin"
    ORIGIN_TRANS = "origin_trans"
    CHINESE = "chinese"
    ENGLISH = "english"
    TRANSLITERATION = "transliteration"
    PINYIN = "pinyin"


class ThemeModeEnum(str, Enum):
    FOLLOW_SYSTEM = "follow_system"
    LIGHT = "light"
    DARK = "dark"


class LanguageEnum(str, Enum):
    OTHER = "other"
    ENGLISH = "english"
    JAPANESE = "japanese"
    KOREAN = "korean"
    RUSSIAN = "russian"
    FRENCH = "french"
    ITALIAN = "italian"
    CHINESE = "chinese"
