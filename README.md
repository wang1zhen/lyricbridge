# lyricbridge

lyricbridge is a Python + Flet reimplementation inspired by the 163MusicLyrics app.
It reuses the original app icon from `163MusicLyrics` and focuses on the same workflows:
search, preview, and export lyrics from NetEase Cloud Music and QQ Music.

## Features

- NetEase Cloud Music and QQ Music providers
- Exact search by ID or URL, fuzzy search by keyword
- Song / Album / Playlist queries
- Batch input and directory scan (filename to keyword)
- LRC and SRT export
- Output format, encoding, and filename templates
- Optional auto-translate (Baidu or Caiyun) when keys are provided
- Optional pinyin output when `pypinyin` is installed

## Setup (uv)

```bash
uv venv
uv sync
```

## Run

```bash
uv run app.py
```

## Notes

- NetEase and QQ endpoints may require cookies for some content. Add cookies in the Settings tab.
- Auto-translation requires API keys or tokens.
- Some providers may throttle or return empty results for copyrighted tracks.

## Icons

The app icon files are copied from:
`163MusicLyrics/cross-platform/MusicLyricApp/Resources/`.
