from __future__ import annotations

import base64
import json
import random
import string
from typing import Dict, List, Tuple

import requests

from ..models import Lyrics, SearchResultItem, SearchSource, SearchType, Song

try:
    from Crypto.Cipher import AES
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise RuntimeError("pycryptodome is required for NetEase encryption") from exc


MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725"
    "152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e031"
    "2ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b"
    "424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0"
    "a22b8e7"
)
NONCE = "0CoJUm6Qyw8W8jud"
PUBKEY = "010001"
VI = "0102030405060708"


class NetEaseProvider:
    def __init__(self, cookie: str = "") -> None:
        self._cookie = cookie
        self._session = requests.Session()
        self._secret_key = self._create_secret_key(16)
        self._enc_sec_key = self._rsa_encrypt(self._secret_key)

    def _headers(self) -> Dict[str, str]:
        cookie = self._cookie.strip() or f"NMTID={self._create_secret_key(10)}"
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"
            ),
            "Referer": "https://music.163.com/",
            "Cookie": cookie,
        }

    def _weapi_post(self, url: str, data: Dict[str, str]) -> Dict:
        payload = self._prepare(json.dumps(data))
        resp = self._session.post(url, data=payload, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return json.loads(resp.text)

    def search(self, keyword: str, search_type: SearchType) -> List[SearchResultItem]:
        type_map = {
            SearchType.SONG: "1",
            SearchType.ALBUM: "10",
            SearchType.PLAYLIST: "1000",
        }
        payload = {
            "csrf_token": "",
            "s": keyword,
            "type": type_map[search_type],
            "limit": "20",
            "offset": "0",
        }
        resp = self._weapi_post("https://music.163.com/weapi/cloudsearch/get/web", payload)
        if resp.get("code") != 200 or "result" not in resp:
            return []

        result = resp["result"]
        items: List[SearchResultItem] = []

        if search_type == SearchType.SONG:
            for song in result.get("songs", []):
                items.append(
                    SearchResultItem(
                        source=SearchSource.NETEASE,
                        search_type=search_type,
                        item_id=str(song.get("id")),
                        name=song.get("name", ""),
                        artists=[artist.get("name", "") for artist in song.get("ar", [])],
                        album=song.get("al", {}).get("name", ""),
                    )
                )
        elif search_type == SearchType.ALBUM:
            for album in result.get("albums", []):
                items.append(
                    SearchResultItem(
                        source=SearchSource.NETEASE,
                        search_type=search_type,
                        item_id=str(album.get("id")),
                        name=album.get("name", ""),
                        artists=[album.get("artist", {}).get("name", "")],
                        album=album.get("name", ""),
                    )
                )
        elif search_type == SearchType.PLAYLIST:
            for playlist in result.get("playlists", []):
                items.append(
                    SearchResultItem(
                        source=SearchSource.NETEASE,
                        search_type=search_type,
                        item_id=str(playlist.get("id")),
                        name=playlist.get("name", ""),
                        artists=[playlist.get("creator", {}).get("nickname", "")],
                        album=playlist.get("name", ""),
                        extra={"track_count": str(playlist.get("trackCount", ""))},
                    )
                )

        return items

    def get_songs(self, song_ids: List[str]) -> List[Song]:
        if not song_ids:
            return []

        payload = {
            "c": json.dumps([{"id": song_id} for song_id in song_ids]),
            "csrf_token": "",
        }
        resp = self._weapi_post("https://music.163.com/weapi/v3/song/detail?csrf_token=", payload)
        songs: List[Song] = []
        for song in resp.get("songs", []):
            songs.append(self._to_song(song, song_id=str(song.get("id"))))
        return songs

    def get_song(self, song_id: str) -> Song | None:
        songs = self.get_songs([song_id])
        return songs[0] if songs else None

    def get_album(self, album_id: str) -> Tuple[str, List[Song]]:
        payload = {"csrf_token": ""}
        resp = self._weapi_post(
            f"https://music.163.com/weapi/v1/album/{album_id}?csrf_token=", payload
        )
        album = resp.get("album", {})
        album_name = album.get("name", "")
        songs = [self._to_song(song, song_id=str(song.get("id"))) for song in resp.get("songs", [])]
        return album_name, songs

    def get_playlist(self, playlist_id: str) -> Tuple[str, List[Song]]:
        payload = {
            "csrf_token": "",
            "id": playlist_id,
            "offset": "0",
            "total": "true",
            "limit": "1000",
            "n": "1000",
        }
        resp = self._weapi_post("https://music.163.com/weapi/v6/playlist/detail?csrf_token=", payload)
        playlist = resp.get("playlist", {})
        playlist_name = playlist.get("name", "")
        track_ids = [str(item.get("id")) for item in playlist.get("trackIds", [])]
        songs = self.get_songs(track_ids)
        return playlist_name, songs

    def get_song_link(self, song_id: str) -> str:
        payload = {"ids": f"[{song_id}]", "br": "999000", "csrf_token": ""}
        resp = self._weapi_post(
            "https://music.163.com/weapi/song/enhance/player/url?csrf_token=", payload
        )
        for datum in resp.get("data", []):
            if str(datum.get("id")) == song_id:
                return datum.get("url", "") or ""
        return ""

    def get_lyrics(self, song_id: str, verbatim: bool = False) -> Lyrics:
        payload = {
            "id": song_id,
            "os": "pc",
            "lv": "-1",
            "kv": "-1",
            "tv": "-1",
            "rv": "-1",
            "yv": "-1",
            "ytv": "-1",
            "yrv": "-1",
            "csrf_token": "",
        }
        resp = self._weapi_post("https://music.163.com/weapi/song/lyric?csrf_token=", payload)
        lyrics = Lyrics(source=SearchSource.NETEASE)
        if resp.get("code") != 200:
            return lyrics

        if verbatim:
            yrc = resp.get("yrc")
            if yrc:
                lyrics.verbatim = yrc.get("lyric", "")
        else:
            lrc = resp.get("lrc")
            tlyric = resp.get("tlyric")
            romalrc = resp.get("romalrc")
            if lrc:
                lyrics.original = lrc.get("lyric", "")
            if tlyric:
                lyrics.translated = tlyric.get("lyric", "")
            if romalrc:
                lyrics.transliteration = romalrc.get("lyric", "")

        return lyrics

    def _to_song(self, raw: Dict, song_id: str) -> Song:
        artists = [artist.get("name", "") for artist in raw.get("ar", [])]
        album = raw.get("al", {})
        return Song(
            source=SearchSource.NETEASE,
            song_id=str(raw.get("id", song_id)),
            display_id=song_id,
            name=raw.get("name", ""),
            singers=artists,
            album=album.get("name", ""),
            duration_ms=int(raw.get("dt", 0)),
            pic_url=album.get("picUrl", ""),
        )

    @staticmethod
    def _aes_encrypt(text: str, key: str) -> str:
        pad = 16 - len(text) % 16
        text = text + chr(pad) * pad
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, VI.encode("utf-8"))
        encrypted = cipher.encrypt(text.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    def _prepare(self, raw: str) -> Dict[str, str]:
        params = self._aes_encrypt(raw, NONCE)
        params = self._aes_encrypt(params, self._secret_key)
        return {"params": params, "encSecKey": self._enc_sec_key}

    @staticmethod
    def _create_secret_key(length: int) -> str:
        return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

    @staticmethod
    def _rsa_encrypt(text: str) -> str:
        reversed_text = text[::-1]
        hex_text = reversed_text.encode("utf-8").hex()
        value = int(hex_text, 16)
        pubkey = int(PUBKEY, 16)
        modulus = int(MODULUS, 16)
        enc = pow(value, pubkey, modulus)
        return format(enc, "x").zfill(256)
