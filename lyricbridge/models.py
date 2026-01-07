from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SearchSource(str, Enum):
    NETEASE = "netease"
    QQ = "qq"


class SearchType(str, Enum):
    SONG = "song"
    ALBUM = "album"
    PLAYLIST = "playlist"


class ShowLrcType(str, Enum):
    STAGGER = "stagger"
    MERGE = "merge"
    ISOLATED = "isolated"


class OutputFormat(str, Enum):
    LRC = "lrc"
    SRT = "srt"


class OutputEncoding(str, Enum):
    UTF_8 = "utf-8"
    UTF_8_BOM = "utf-8-sig"
    UTF_16 = "utf-16"
    UTF_32 = "utf-32"


class LyricType(str, Enum):
    ORIGINAL = "original"
    TRANSLATED = "translated"
    TRANSLITERATION = "transliteration"
    PINYIN = "pinyin"


@dataclass
class Song:
    source: SearchSource
    song_id: str
    display_id: str
    name: str
    singers: List[str]
    album: str
    duration_ms: int
    pic_url: str = ""
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class Lyrics:
    source: SearchSource
    original: str = ""
    translated: str = ""
    transliteration: str = ""
    verbatim: str = ""
    pinyin: str = ""


@dataclass
class SearchResultItem:
    source: SearchSource
    search_type: SearchType
    item_id: str
    name: str
    artists: List[str] = field(default_factory=list)
    album: str = ""
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class InputSongId:
    song_id: str
    source: SearchSource
    search_type: SearchType


@dataclass
class LyricLine:
    timestamp_ms: int
    text: str


@dataclass
class OutputPayload:
    content: str
    extension: str
    encoding: str
    suffix: Optional[str] = None
