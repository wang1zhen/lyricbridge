from __future__ import annotations

import asyncio
import inspect
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, List

import flet as ft

from lyricbridge.config import load_config, save_config
from lyricbridge.models import LyricType, OutputFormat, SearchSource, SearchType, ShowLrcType, Song
from lyricbridge.providers import NetEaseProvider, QQMusicProvider
from lyricbridge.services.exporter import export_songs
from lyricbridge.services.lyrics import build_output
from lyricbridge.utils import InputParseError, format_duration, parse_input_ids, render_filename


def main(page: ft.Page) -> None:
    page.title = "lyricbridge"
    page.window_width = 980
    page.window_height = 760
    page.window_min_width = 900
    page.window_min_height = 680
    icon_path = "assets/app-logo.ico" if sys.platform.startswith("win") else "assets/app-logo.png"
    page.window.icon = icon_path
    page.padding = ft.padding.symmetric(horizontal=16, vertical=12)

    config = load_config()

    providers: Dict[SearchSource, object] = {}
    lyrics_cache: Dict[str, object] = {}
    current_songs: List[Song] = []

    def refresh_providers() -> None:
        providers[SearchSource.NETEASE] = NetEaseProvider(config.netease_cookie)
        providers[SearchSource.QQ] = QQMusicProvider(config.qq_cookie)

    def get_provider(source: SearchSource):
        if source not in providers:
            refresh_providers()
        return providers[source]

    refresh_providers()

    def cache_key(song: Song) -> str:
        return f"{song.source.value}:{song.song_id}:{config.prefer_verbatim}"

    def persist_config() -> None:
        save_config(config)

    def update_song_info(song: Song | None) -> None:
        if song is None:
            singer_field.value = ""
            song_field.value = ""
            album_field.value = ""
        else:
            singer_field.value = ", ".join(song.singers)
            song_field.value = song.name
            album_field.value = song.album
        singer_field.update()
        song_field.update()
        album_field.update()

    def show_message(message: str) -> None:
        update_song_info(None)
        preview.value = message
        preview.update()

    def show_dialog(title: str, message: str) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda e: page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def fetch_lyrics(song: Song):
        key = cache_key(song)
        if key in lyrics_cache:
            return lyrics_cache[key]

        provider = get_provider(song.source)
        try:
            if song.source == SearchSource.QQ:
                lyric = provider.get_lyrics(song.song_id)
            else:
                lyric = provider.get_lyrics(song.display_id, config.prefer_verbatim)
        except Exception:
            return None

        lyrics_cache[key] = lyric
        return lyric

    def update_preview(song: Song | None) -> None:
        if song is None:
            preview.value = ""
            preview.update()
            return

        lyrics = fetch_lyrics(song)
        if not lyrics:
            preview.value = ""
            preview.update()
            return

        lyric_types = [LyricType(t) for t in config.output_lyric_types]
        output_format = OutputFormat(config.output_format)
        show_lrc_type = ShowLrcType(config.show_lrc_type)
        outputs = build_output(
            lyrics,
            config,
            lyric_types,
            output_format,
            show_lrc_type,
            config.lrc_merge_separator,
        )
        preview.value = outputs[0].content if outputs else ""
        preview.update()

    def refresh_preview() -> None:
        if not current_songs:
            update_preview(None)
            return
        update_preview(current_songs[0])

    def bind_dropdown(control: ft.Dropdown, handler) -> None:
        if hasattr(control, "on_change"):
            control.on_change = handler
        else:
            control.on_select = handler

    def default_output_dir() -> Path:
        if config.last_output_dir:
            return Path(config.last_output_dir)
        return Path.home() / "Downloads"

    def pick_save_path(initial_dir: Path, default_name: str) -> Path | None:
        if sys.platform.startswith("win"):
            return _pick_save_path_windows(initial_dir, default_name)
        if sys.platform == "darwin":
            return _pick_save_path_macos(initial_dir, default_name)
        return _pick_save_path_linux(initial_dir, default_name)

    def pick_output_dir(initial_dir: Path) -> Path | None:
        if sys.platform.startswith("win"):
            return _pick_output_dir_windows(initial_dir)
        if sys.platform == "darwin":
            return _pick_output_dir_macos(initial_dir)
        return _pick_output_dir_linux(initial_dir)

    def _pick_save_path_linux(initial_dir: Path, default_name: str) -> Path | None:
        commands: List[List[str]] = []
        default_base = initial_dir if initial_dir.exists() else Path.home()
        default_path = default_base / default_name
        if shutil.which("zenity"):
            cmd = [
                "zenity",
                "--file-selection",
                "--save",
                "--confirm-overwrite",
                "--title=Save lyrics",
                "--filename",
                str(default_path),
            ]
            commands.append(cmd)
        if shutil.which("kdialog"):
            cmd = ["kdialog", "--getsavefilename", str(default_path)]
            commands.append(cmd)

        if not commands:
            raise RuntimeError("No file picker available. Install zenity or kdialog.")

        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            except FileNotFoundError:
                continue
            if result.returncode == 0:
                path = result.stdout.strip()
                return Path(path) if path else None
            if result.returncode == 1:
                return None

        raise RuntimeError("Failed to open save dialog.")

    def _pick_save_path_macos(initial_dir: Path, default_name: str) -> Path | None:
        script = 'choose file name with prompt "Save lyrics"'
        if initial_dir.exists():
            safe_dir = str(initial_dir).replace('"', '\\"')
            script += f' default location POSIX file "{safe_dir}"'
        if default_name:
            safe_name = default_name.replace('"', '\\"')
            script += f' default name "{safe_name}"'
        script = f"POSIX path of ({script})"
        try:
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, check=False
            )
        except FileNotFoundError as exc:
            raise RuntimeError("osascript not available to pick a file.") from exc
        if result.returncode == 0:
            path = result.stdout.strip()
            return Path(path) if path else None
        if result.returncode == 1:
            return None
        raise RuntimeError("Failed to open save dialog.")

    def _pick_save_path_windows(initial_dir: Path, default_name: str) -> Path | None:
        initial = str(initial_dir).replace("'", "''") if initial_dir.exists() else ""
        safe_name = default_name.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$f = New-Object System.Windows.Forms.SaveFileDialog;"
            "$f.Title = 'Save lyrics';"
            f"$f.InitialDirectory = '{initial}';"
            f"$f.FileName = '{safe_name}';"
            "if ($f.ShowDialog() -eq 'OK') { $f.FileName }"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("PowerShell is required to pick a file.") from exc
        if result.returncode == 0:
            path = result.stdout.strip()
            return Path(path) if path else None
        if result.returncode == 1:
            return None
        raise RuntimeError("Failed to open save dialog.")

    def _pick_output_dir_linux(initial_dir: Path) -> Path | None:
        commands: List[List[str]] = []
        if shutil.which("zenity"):
            cmd = ["zenity", "--file-selection", "--directory", "--title=Select output folder"]
            if initial_dir.exists():
                cmd += ["--filename", f"{initial_dir}{os.sep}"]
            commands.append(cmd)
        if shutil.which("kdialog"):
            cmd = ["kdialog", "--getexistingdirectory"]
            if initial_dir.exists():
                cmd.append(str(initial_dir))
            commands.append(cmd)

        if not commands:
            raise RuntimeError("No folder picker available. Install zenity or kdialog.")

        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            except FileNotFoundError:
                continue
            if result.returncode == 0:
                path = result.stdout.strip()
                return Path(path) if path else None
            if result.returncode == 1:
                return None

        raise RuntimeError("Failed to open folder picker.")

    def _pick_output_dir_macos(initial_dir: Path) -> Path | None:
        script = 'POSIX path of (choose folder with prompt "Select output folder")'
        if initial_dir.exists():
            safe_dir = str(initial_dir).replace('"', '\\"')
            script = (
                'POSIX path of (choose folder with prompt "Select output folder" '
                f'default location POSIX file "{safe_dir}")'
            )
        try:
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, check=False
            )
        except FileNotFoundError as exc:
            raise RuntimeError("osascript not available to pick a folder.") from exc
        if result.returncode == 0:
            path = result.stdout.strip()
            return Path(path) if path else None
        if result.returncode == 1:
            return None
        raise RuntimeError("Failed to open folder picker.")

    def _pick_output_dir_windows(initial_dir: Path) -> Path | None:
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$f.Description = 'Select output folder';"
            "if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath }"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("PowerShell is required to pick a folder.") from exc
        if result.returncode == 0:
            path = result.stdout.strip()
            return Path(path) if path else None
        if result.returncode == 1:
            return None
        raise RuntimeError("Failed to open folder picker.")

    def run_exact_search(_: ft.ControlEvent | None = None) -> None:
        search_text = search_input.value.strip()
        if not search_text:
            show_message("Search input is empty.")
            return

        lyrics_cache.clear()
        current_songs.clear()

        try:
            ids = parse_input_ids(
                search_text,
                SearchSource(source_selector.value),
                SearchType(type_selector.value),
            )
        except InputParseError as exc:
            show_message(str(exc))
            return

        for item in ids:
            provider = get_provider(item.source)
            try:
                if item.search_type == SearchType.SONG:
                    song = provider.get_song(item.song_id)
                    if song:
                        current_songs.append(song)
                elif item.search_type == SearchType.ALBUM:
                    _, songs = provider.get_album(item.song_id)
                    current_songs.extend(songs)
                elif item.search_type == SearchType.PLAYLIST:
                    _, songs = provider.get_playlist(item.song_id)
                    current_songs.extend(songs)
            except Exception as exc:
                show_message(f"Search failed: {exc}")
                return

        if not current_songs:
            show_message("No songs found.")
            return

        update_song_info(current_songs[0])
        update_preview(current_songs[0])

    async def run_save(_: ft.ControlEvent) -> None:
        if not current_songs:
            show_message("No songs to export.")
            return
        initial_dir = default_output_dir()
        output_dir: Path
        output_config = config
        if len(current_songs) == 1:
            song = current_songs[0]
            tokens = {
                "index": "1",
                "id": song.display_id,
                "name": song.name,
                "singer": config.singer_separator.join(song.singers),
                "album": song.album,
                "duration": format_duration(song.duration_ms),
            }
            base_name = render_filename(config.output_filename_format, tokens)
            extension = OutputFormat(config.output_format).value
            default_name = f"{base_name}.{extension}"
            try:
                selected_path = await asyncio.to_thread(
                    pick_save_path, initial_dir, default_name
                )
            except RuntimeError as exc:
                show_dialog("Save failed", str(exc))
                return

            if not selected_path:
                return

            output_dir = selected_path.parent
            output_config = replace(config, output_filename_format=selected_path.stem)
        else:
            try:
                selected_dir = await asyncio.to_thread(pick_output_dir, initial_dir)
            except RuntimeError as exc:
                show_dialog("Save failed", str(exc))
                return

            if not selected_dir:
                return

            output_dir = selected_dir

        config.last_output_dir = str(output_dir)
        persist_config()
        exported = export_songs(current_songs, fetch_lyrics, output_dir, output_config, lambda _: None)
        if not exported:
            show_dialog("Save failed", "No files were exported.")
        else:
            show_dialog("Saved", f"Saved {len(exported)} file(s) to:\n{output_dir}")

    source_selector = ft.Dropdown(
        label="Source",
        value=config.search_source,
        options=[
            ft.dropdown.Option(key=SearchSource.NETEASE.value, text="NetEase"),
            ft.dropdown.Option(key=SearchSource.QQ.value, text="QQ Music"),
        ],
        height=44,
    )
    bind_dropdown(
        source_selector,
        lambda e: setattr(config, "search_source", e.control.value) or persist_config(),
    )

    lrc_selector = ft.Dropdown(
        label="Lyric Format",
        value=config.show_lrc_type,
        options=[
            ft.dropdown.Option(key=ShowLrcType.STAGGER.value, text="Stagger"),
            ft.dropdown.Option(key=ShowLrcType.MERGE.value, text="Merge"),
            ft.dropdown.Option(key=ShowLrcType.ISOLATED.value, text="Isolated"),
        ],
        height=44,
    )
    bind_dropdown(
        lrc_selector,
        lambda e: setattr(config, "show_lrc_type", e.control.value)
        or persist_config()
        or refresh_preview(),
    )

    type_selector = ft.Dropdown(
        label="Search Type",
        value=config.search_type,
        options=[
            ft.dropdown.Option(key=SearchType.SONG.value, text="Song"),
            ft.dropdown.Option(key=SearchType.ALBUM.value, text="Album"),
            ft.dropdown.Option(key=SearchType.PLAYLIST.value, text="Playlist"),
        ],
        height=44,
    )
    bind_dropdown(
        type_selector,
        lambda e: setattr(config, "search_type", e.control.value) or persist_config(),
    )

    search_input = ft.TextField(label="URL", min_lines=1, max_lines=1, height=44)
    search_button = ft.ElevatedButton("Search", on_click=run_exact_search, width=120, height=44)

    singer_field = ft.TextField(label="Singer", read_only=True, height=44)
    song_field = ft.TextField(label="Song", read_only=True, height=44)
    album_field = ft.TextField(label="Album", read_only=True, height=44)

    lyrics_label = ft.Text("Lyrics")
    preview = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=12,
        max_lines=18,
        height=320,
        text_align=ft.TextAlign.LEFT,
    )

    format_selector = ft.Dropdown(
        label="Output Format",
        value=config.output_format,
        options=[
            ft.dropdown.Option(key=OutputFormat.LRC.value, text="LRC"),
            ft.dropdown.Option(key=OutputFormat.SRT.value, text="SRT"),
        ],
        height=44,
    )
    bind_dropdown(
        format_selector,
        lambda e: setattr(config, "output_format", e.control.value)
        or persist_config()
        or refresh_preview(),
    )

    encoding_selector = ft.Dropdown(
        label="Encoding",
        value=config.output_encoding,
        options=[
            ft.dropdown.Option(key="utf-8", text="UTF-8"),
            ft.dropdown.Option(key="utf-8-sig", text="UTF-8 BOM"),
            ft.dropdown.Option(key="utf-16", text="UTF-16"),
            ft.dropdown.Option(key="utf-32", text="UTF-32"),
        ],
        height=44,
    )
    bind_dropdown(
        encoding_selector,
        lambda e: setattr(config, "output_encoding", e.control.value) or persist_config(),
    )

    save_button = ft.ElevatedButton("Save", on_click=run_save, height=44, width=120)

    row_spacing = 12
    row_props = dict(
        wrap=False,
        spacing=row_spacing,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    lyrics_section = ft.Column(
        controls=[lyrics_label, preview],
        spacing=6,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    content = ft.Column(
        expand=True,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Row([source_selector, lrc_selector, type_selector], **row_props),
            ft.Row([search_input, search_button], **row_props),
            ft.Row([singer_field, song_field, album_field], **row_props),
            lyrics_section,
            ft.Row([format_selector, encoding_selector, save_button], **row_props),
        ],
    )
    page.add(content)

    def sync_layout() -> None:
        page_width = page.width or page.window.width or page.window_width
        if not page_width:
            return
        content_width = max(360, page_width - 32)
        col_width = (content_width - row_spacing * 2) / 3

        for control in (
            source_selector,
            lrc_selector,
            type_selector,
            singer_field,
            song_field,
            album_field,
            format_selector,
            encoding_selector,
        ):
            control.width = col_width

        search_button.width = col_width
        save_button.width = col_width
        search_input.width = col_width * 2 + row_spacing
        lyrics_label.width = content_width
        preview.width = content_width
        page.update()

    page.on_resize = lambda _: sync_layout()
    sync_layout()


def run_app() -> None:
    if hasattr(ft, "run"):
        params = inspect.signature(ft.run).parameters
        kwargs = {}
        if "assets_dir" in params:
            kwargs["assets_dir"] = "assets"
        if "main" in params:
            ft.run(main, **kwargs)
        elif "target" in params:
            ft.run(target=main, **kwargs)
        elif "app" in params:
            ft.run(app=main, **kwargs)
        else:
            ft.run(main, **kwargs)
    else:
        ft.app(target=main, assets_dir="assets")


if __name__ == "__main__":
    run_app()
