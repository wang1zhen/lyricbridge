from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List

from ..config import AppConfig
from ..models import LyricType, OutputFormat, ShowLrcType, Song, Lyrics
from ..utils import format_duration, render_filename
from .lyrics import build_output, parse_lrc, format_timestamp
from .translators import get_translator


def export_songs(
    songs: Iterable[Song],
    lyrics_lookup: Callable[[Song], Lyrics | None],
    output_dir: Path,
    config: AppConfig,
    log: Callable[[str], None],
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: List[Path] = []
    translator = get_translator(config) if config.auto_translate_missing else None

    lyric_types = [LyricType(t) for t in config.output_lyric_types]
    output_format = OutputFormat(config.output_format)
    show_lrc_type = ShowLrcType(config.show_lrc_type)

    for index, song in enumerate(songs, start=1):
        lyrics = lyrics_lookup(song)
        if lyrics is None:
            log(f"Skip {song.name}: lyric fetch failed")
            continue

        if config.auto_translate_missing and translator:
            try:
                lyrics = _apply_translation(lyrics, config, translator)
            except Exception as exc:
                log(f"Translation failed for {song.name}: {exc}")

        outputs = build_output(
            lyrics,
            config,
            lyric_types,
            output_format,
            show_lrc_type,
            config.lrc_merge_separator,
        )

        tokens = {
            "index": str(index),
            "id": song.display_id,
            "name": song.name,
            "singer": config.singer_separator.join(song.singers),
            "album": song.album,
            "duration": format_duration(song.duration_ms),
        }
        base_name = render_filename(config.output_filename_format, tokens)

        for payload in outputs:
            suffix = f"_{payload.suffix}" if payload.suffix else ""
            filename = f"{base_name}{suffix}.{payload.extension}"
            path = output_dir / filename
            path.write_text(payload.content, encoding=payload.encoding)
            exported.append(path)

        log(f"Saved {song.name} ({song.display_id})")

    return exported


def _apply_translation(lyrics, config: AppConfig, translator) -> any:
    if lyrics.translated:
        return lyrics

    lines = parse_lrc(lyrics.original, config.ignore_empty_lines)
    if not lines:
        return lyrics

    translated = translator.translate([line.text for line in lines], config.translation_target)
    lrc_lines = []
    for line, text in zip(lines, translated):
        timestamp = format_timestamp(line.timestamp_ms, config.lrc_timestamp_format)
        lrc_lines.append(f"{timestamp}{text}")
    lyrics.translated = "\n".join(lrc_lines)
    return lyrics
