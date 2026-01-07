from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple

from ..config import AppConfig
from ..models import LyricLine, LyricType, Lyrics, OutputFormat, OutputPayload, ShowLrcType

try:
    from pypinyin import lazy_pinyin  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    lazy_pinyin = None


TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?\]")


def parse_lrc(text: str, ignore_empty: bool = True) -> List[LyricLine]:
    lines: List[LyricLine] = []
    if not text:
        return lines

    for raw_line in text.splitlines():
        matches = list(TIMESTAMP_RE.finditer(raw_line))
        if not matches:
            continue
        content = TIMESTAMP_RE.sub("", raw_line).strip()
        if ignore_empty and not content:
            continue

        for match in matches:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            ms_raw = match.group(3) or "0"
            ms = int(ms_raw.ljust(3, "0")[:3])
            timestamp_ms = (minutes * 60 + seconds) * 1000 + ms
            lines.append(LyricLine(timestamp_ms=timestamp_ms, text=content))

    return sorted(lines, key=lambda item: item.timestamp_ms)


def format_timestamp(timestamp_ms: int, fmt: str) -> str:
    total_seconds = max(0, timestamp_ms // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    ms = timestamp_ms % 1000

    values = {
        "HH": f"{hours:02d}",
        "mm": f"{minutes:02d}",
        "ss": f"{seconds:02d}",
        "SSS": f"{ms:03d}",
        "SS": f"{ms // 10:02d}",
        "S": f"{ms // 100:d}",
    }

    for token in ("HH", "mm", "ss", "SSS", "SS", "S"):
        fmt = fmt.replace(token, values[token])
    return fmt


def _lines_to_map(lines: Iterable[LyricLine]) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for line in lines:
        mapping[line.timestamp_ms] = line.text
    return mapping


def _collect_timestamps(maps: Iterable[Dict[int, str]]) -> List[int]:
    ts = set()
    for mapping in maps:
        ts.update(mapping.keys())
    return sorted(ts)


def _build_pinyin_lines(lines: List[LyricLine]) -> List[LyricLine]:
    if not lazy_pinyin:
        return []

    converted: List[LyricLine] = []
    for line in lines:
        if not line.text.strip():
            converted.append(LyricLine(line.timestamp_ms, ""))
            continue
        converted.append(LyricLine(line.timestamp_ms, " ".join(lazy_pinyin(line.text))))
    return converted


def build_output(
    lyrics: Lyrics,
    config: AppConfig,
    lyric_types: List[LyricType],
    output_format: OutputFormat,
    show_lrc_type: ShowLrcType,
    merge_separator: str,
) -> List[OutputPayload]:
    if not lyric_types:
        lyric_types = [LyricType.ORIGINAL]

    raw_original = lyrics.verbatim if config.prefer_verbatim and lyrics.verbatim else lyrics.original

    original_lines = parse_lrc(raw_original, config.ignore_empty_lines)
    if not original_lines and raw_original != lyrics.original:
        original_lines = parse_lrc(lyrics.original, config.ignore_empty_lines)
    translated_lines = parse_lrc(lyrics.translated, config.ignore_empty_lines)
    transliteration_lines = parse_lrc(lyrics.transliteration, config.ignore_empty_lines)
    pinyin_lines = _build_pinyin_lines(original_lines)

    line_maps: Dict[LyricType, Dict[int, str]] = {
        LyricType.ORIGINAL: _lines_to_map(original_lines),
        LyricType.TRANSLATED: _lines_to_map(translated_lines),
        LyricType.TRANSLITERATION: _lines_to_map(transliteration_lines),
        LyricType.PINYIN: _lines_to_map(pinyin_lines),
    }

    outputs: List[OutputPayload] = []
    if show_lrc_type == ShowLrcType.ISOLATED:
        for lyric_type in lyric_types:
            payload = _render_output(
                line_maps[lyric_type],
                output_format,
                config,
                merge_separator,
                show_lrc_type,
                [lyric_type],
            )
            payload.suffix = lyric_type.value
            outputs.append(payload)
        return outputs

    payload = _render_output(
        line_maps,
        output_format,
        config,
        merge_separator,
        show_lrc_type,
        lyric_types,
    )
    outputs.append(payload)
    return outputs


def _render_output(
    maps: Dict[int, str] | Dict[LyricType, Dict[int, str]],
    output_format: OutputFormat,
    config: AppConfig,
    merge_separator: str,
    show_lrc_type: ShowLrcType,
    lyric_types: List[LyricType],
) -> OutputPayload:
    if isinstance(maps, dict) and lyric_types and (not maps or isinstance(next(iter(maps.values())), str)):
        type_maps = {lyric_types[0]: maps}  # isolated mode
    else:
        type_maps = maps  # type: ignore[assignment]

    timestamps = _collect_timestamps(type_maps.values())

    if output_format == OutputFormat.SRT:
        text = _render_srt(type_maps, timestamps, config, merge_separator, show_lrc_type, lyric_types)
        return OutputPayload(content=text, extension="srt", encoding=config.output_encoding)

    text = _render_lrc(type_maps, timestamps, config, merge_separator, show_lrc_type, lyric_types)
    return OutputPayload(content=text, extension="lrc", encoding=config.output_encoding)


def _render_lrc(
    type_maps: Dict[LyricType, Dict[int, str]],
    timestamps: List[int],
    config: AppConfig,
    merge_separator: str,
    show_lrc_type: ShowLrcType,
    lyric_types: List[LyricType],
) -> str:
    lines: List[str] = []
    for ts in timestamps:
        if show_lrc_type == ShowLrcType.MERGE:
            merged = _merge_texts(type_maps, lyric_types, ts, merge_separator, config.ignore_empty_lines)
            if not merged:
                continue
            lines.append(f"{format_timestamp(ts, config.lrc_timestamp_format)}{merged}")
        else:
            for lyric_type in lyric_types:
                text = type_maps.get(lyric_type, {}).get(ts, "")
                if config.ignore_empty_lines and not text:
                    continue
                lines.append(f"{format_timestamp(ts, config.lrc_timestamp_format)}{text}")

    return "\n".join(lines)


def _render_srt(
    type_maps: Dict[LyricType, Dict[int, str]],
    timestamps: List[int],
    config: AppConfig,
    merge_separator: str,
    show_lrc_type: ShowLrcType,
    lyric_types: List[LyricType],
) -> str:
    segments: List[str] = []
    segment_index = 1
    for idx, ts in enumerate(timestamps):
        end_ts = timestamps[idx + 1] if idx + 1 < len(timestamps) else ts + 2000

        if show_lrc_type == ShowLrcType.MERGE:
            text = _merge_texts(type_maps, lyric_types, ts, merge_separator, config.ignore_empty_lines)
            if not text:
                continue
            content = text
        else:
            texts: List[str] = []
            for lyric_type in lyric_types:
                text = type_maps.get(lyric_type, {}).get(ts, "")
                if config.ignore_empty_lines and not text:
                    continue
                texts.append(text)
            if not texts:
                continue
            content = "\n".join(texts)

        segments.append(
            "\n".join(
                [
                    str(segment_index),
                    f"{format_timestamp(ts, config.srt_timestamp_format)} --> "
                    f"{format_timestamp(end_ts, config.srt_timestamp_format)}",
                    content,
                    "",
                ]
            )
        )
        segment_index += 1

    return "\n".join(segments).strip()


def _merge_texts(
    type_maps: Dict[LyricType, Dict[int, str]],
    lyric_types: List[LyricType],
    ts: int,
    separator: str,
    ignore_empty: bool,
) -> str:
    parts: List[str] = []
    for lyric_type in lyric_types:
        text = type_maps.get(lyric_type, {}).get(ts, "")
        if ignore_empty and not text:
            continue
        parts.append(text)
    return separator.join(parts).strip()
