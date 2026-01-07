from __future__ import annotations

import json
import random
import re
import string
import zlib
from typing import Dict, List, Tuple

import requests

from ..models import Lyrics, SearchResultItem, SearchSource, SearchType, Song

try:
    from Crypto.Cipher import DES3
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise RuntimeError("pycryptodome is required for QQ lyric decryption") from exc


QQ_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"


class QQMusicProvider:
    def __init__(self, cookie: str = "") -> None:
        self._cookie = cookie
        self._session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"
            ),
            "Referer": "https://c.y.qq.com/",
            "Cookie": self._cookie,
        }

    def _post_json(self, url: str, data: Dict) -> Dict:
        resp = self._session.post(url, json=data, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _post_form(self, url: str, data: Dict[str, str]) -> str:
        resp = self._session.post(url, data=data, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.text

    def search(self, keyword: str, search_type: SearchType) -> List[SearchResultItem]:
        type_map = {SearchType.SONG: 0, SearchType.ALBUM: 2, SearchType.PLAYLIST: 3}
        data = {
            "req_1": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {
                    "num_per_page": "20",
                    "page_num": "1",
                    "query": keyword,
                    "search_type": type_map[search_type],
                },
            }
        }
        resp = self._post_json("https://u.y.qq.com/cgi-bin/musicu.fcg", data)
        body = resp.get("req_1", {}).get("data", {}).get("body", {})
        items: List[SearchResultItem] = []

        if search_type == SearchType.SONG:
            for song in body.get("song", {}).get("list", []):
                items.append(
                    SearchResultItem(
                        source=SearchSource.QQ,
                        search_type=search_type,
                        item_id=str(song.get("id") or ""),
                        name=song.get("title") or song.get("name", ""),
                        artists=[s.get("name", "") for s in song.get("singer", [])],
                        album=song.get("album", {}).get("name", ""),
                        extra={"mid": song.get("mid", "")},
                    )
                )
        elif search_type == SearchType.ALBUM:
            for album in body.get("album", {}).get("list", []):
                items.append(
                    SearchResultItem(
                        source=SearchSource.QQ,
                        search_type=search_type,
                        item_id=str(album.get("albumMID") or album.get("albumID") or ""),
                        name=album.get("albumName", ""),
                        artists=[s.get("name", "") for s in album.get("singer_list", [])],
                        album=album.get("albumName", ""),
                    )
                )
        elif search_type == SearchType.PLAYLIST:
            for playlist in body.get("songlist", {}).get("list", []):
                items.append(
                    SearchResultItem(
                        source=SearchSource.QQ,
                        search_type=search_type,
                        item_id=str(playlist.get("dissid", "")),
                        name=playlist.get("dissname", ""),
                        artists=[playlist.get("creator", {}).get("name", "")],
                        album=playlist.get("dissname", ""),
                        extra={"track_count": str(playlist.get("song_count", ""))},
                    )
                )

        return items

    def get_album(self, album_id: str) -> Tuple[str, List[Song]]:
        data = {"albumid" if album_id.isdigit() else "albummid": album_id}
        raw = self._post_form("https://c.y.qq.com/v8/fcg-bin/fcg_v8_album_info_cp.fcg", data)
        resp = json.loads(raw)
        album = resp.get("data", {})
        album_name = album.get("name", "")
        songs: List[Song] = []
        for song in album.get("list", []) or []:
            songs.append(self._song_from_album(song, album_name))
        return album_name, songs

    def get_playlist(self, playlist_id: str) -> Tuple[str, List[Song]]:
        data = {
            "disstid": playlist_id,
            "format": "json",
            "outCharset": "utf8",
            "type": "1",
            "json": "1",
            "utf8": "1",
            "onlysong": "0",
            "new_format": "1",
        }
        raw = self._post_form("https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg", data)
        resp = json.loads(raw)
        cdlist = resp.get("cdlist", [])
        if not cdlist:
            return "", []

        playlist = cdlist[0]
        playlist_name = playlist.get("dissname", "")
        songs: List[Song] = []
        for song in playlist.get("songlist", []) or []:
            songs.append(self._song_from_playlist(song))
        return playlist_name, songs

    def get_song(self, song_id: str) -> Song | None:
        call_back = "getOneSongInfoCallback"
        data = {
            "songid" if song_id.isdigit() else "songmid": song_id,
            "tpl": "yqq_song_detail",
            "format": "jsonp",
            "callback": call_back,
            "g_tk": "5381",
            "jsonpCallback": call_back,
            "loginUin": "0",
            "hostUin": "0",
            "outCharset": "utf8",
            "notice": "0",
            "platform": "yqq",
            "needNewCode": "0",
        }
        raw = self._post_form("https://c.y.qq.com/v8/fcg-bin/fcg_play_single_song.fcg", data)
        payload = self._strip_jsonp(raw, call_back)
        if not payload:
            return None

        resp = json.loads(payload)
        if resp.get("code") != 0 or not resp.get("data"):
            return None

        song = resp.get("data", [])[0]
        return self._song_from_song(song)

    def get_song_link(self, song_mid: str) -> str:
        guid = self._rand_guid()
        data = {
            "req": {
                "method": "GetCdnDispatch",
                "module": "CDN.SrfCdnDispatchServer",
                "param": {"guid": guid, "calltype": "0", "userip": ""},
            },
            "req_0": {
                "method": "CgiGetVkey",
                "module": "vkey.GetVkeyServer",
                "param": {
                    "guid": "8348972662",
                    "songmid": [song_mid],
                    "songtype": [1],
                    "uin": "0",
                    "loginflag": 1,
                    "platform": "20",
                },
            },
            "comm": {"uin": 0, "format": "json", "ct": 24, "cv": 0},
        }
        resp = self._post_json("https://u.y.qq.com/cgi-bin/musicu.fcg", data)
        sip = resp.get("req", {}).get("data", {}).get("sip", [])
        midinfo = resp.get("req_0", {}).get("data", {}).get("midurlinfo", [])
        if not sip or not midinfo:
            return ""
        purl = midinfo[0].get("purl", "")
        return f"{sip[0]}{purl}" if purl else ""

    def get_lyrics(self, song_id: str) -> Lyrics:
        data = {"version": "15", "miniversion": "82", "lrctype": "4", "musicid": song_id}
        raw = self._post_form("https://c.y.qq.com/qqmusic/fcgi-bin/lyric_download.fcg", data)
        raw = raw.replace("<!--", "").replace("-->", "")

        text_map = self._parse_lyric_xml(raw)
        lyrics = Lyrics(source=SearchSource.QQ)

        if "content" in text_map:
            lyrics.original = text_map["content"]
        if "contentts" in text_map:
            lyrics.translated = text_map["contentts"]
        if "contentroma" in text_map:
            lyrics.transliteration = text_map["contentroma"]
        if "lyric" in text_map and not lyrics.original:
            lyrics.original = text_map["lyric"]

        return lyrics

    @staticmethod
    def _strip_jsonp(raw: str, callback: str) -> str:
        if not raw.startswith(callback):
            return ""
        payload = raw.replace(f"{callback}(", "")
        if payload.endswith(")"):
            payload = payload[:-1]
        return payload

    @staticmethod
    def _rand_guid(length: int = 10) -> str:
        return "".join(random.choice(string.digits) for _ in range(length))

    @staticmethod
    def _song_from_song(song: Dict) -> Song:
        album = song.get("album", {}) or {}
        singers = [s.get("name", "") for s in song.get("singer", [])]
        mid = song.get("mid", "")
        return Song(
            source=SearchSource.QQ,
            song_id=str(song.get("id", "")),
            display_id=mid or str(song.get("id", "")),
            name=song.get("name", "") or song.get("title", ""),
            singers=singers,
            album=album.get("name", ""),
            duration_ms=int(song.get("interval", 0)) * 1000,
            pic_url=f"https://y.qq.com/music/photo_new/T002R800x800M000{album.get('pmid', '')}.jpg",
            extra={"mid": mid},
        )

    @staticmethod
    def _song_from_album(song: Dict, album_name: str) -> Song:
        singers = [s.get("name", "") for s in song.get("singer", [])]
        return Song(
            source=SearchSource.QQ,
            song_id=str(song.get("songid", "")),
            display_id=str(song.get("songmid", "")),
            name=song.get("songname", ""),
            singers=singers,
            album=album_name,
            duration_ms=0,
        )

    @staticmethod
    def _song_from_playlist(song: Dict) -> Song:
        singers = [s.get("name", "") for s in song.get("singer", [])]
        album = song.get("album", {}) or {}
        return Song(
            source=SearchSource.QQ,
            song_id=str(song.get("id", "")),
            display_id=str(song.get("mid", "")),
            name=song.get("name", ""),
            singers=singers,
            album=album.get("name", ""),
            duration_ms=int(song.get("interval", 0)) * 1000,
            pic_url=f"https://y.qq.com/music/photo_new/T002R800x800M000{album.get('pmid', '')}.jpg",
        )

    def _parse_lyric_xml(self, raw: str) -> Dict[str, str]:
        import xml.etree.ElementTree as ET

        text_map: Dict[str, str] = {}
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return text_map

        for tag in ("content", "contentts", "contentroma", "Lyric_1"):
            elem = root.find(f".//{tag}")
            if elem is None or not elem.text:
                continue
            decrypted = self._decrypt_lyric(elem.text)
            if not decrypted:
                continue
            parsed = self._extract_lyric_content(decrypted)
            key = "lyric" if tag == "Lyric_1" else tag
            text_map[key] = parsed

        return text_map

    @staticmethod
    def _decrypt_lyric(hex_text: str) -> str:
        raw = bytes.fromhex(hex_text)
        try:
            key = DES3.adjust_key_parity(QQ_KEY)
        except ValueError:
            key = QQ_KEY
        cipher = DES3.new(key, DES3.MODE_ECB)
        decrypted = bytearray()
        for i in range(0, len(raw), 8):
            decrypted.extend(cipher.decrypt(raw[i : i + 8]))

        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                data = zlib.decompress(bytes(decrypted), wbits)
                return data.decode("utf-8", errors="ignore")
            except zlib.error:
                continue

        return ""

    @staticmethod
    def _extract_lyric_content(text: str) -> str:
        if "<?xml" not in text:
            return text

        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return text

        lyric = root.find(".//Lyric_1")
        if lyric is not None and lyric.attrib.get("LyricContent"):
            return lyric.attrib["LyricContent"]

        return text
