from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional

import requests

from .models import InputSongId, SearchSource, SearchType


SEARCH_SOURCE_KEYWORDS: Dict[SearchSource, str] = {
    SearchSource.NETEASE: "163.com",
    SearchSource.QQ: "qq.com",
}

SEARCH_TYPE_KEYWORDS: Dict[SearchSource, Dict[SearchType, str]] = {
    SearchSource.NETEASE: {
        SearchType.SONG: "song?id=",
        SearchType.ALBUM: "album?id=",
        SearchType.PLAYLIST: "playlist?id=",
    },
    SearchSource.QQ: {
        SearchType.SONG: "songDetail/",
        SearchType.ALBUM: "albumDetail/",
        SearchType.PLAYLIST: "playlist/",
    },
}

QQ_SHARE_PATTERNS = [
    (re.compile(r"playsong\.html\?songid=([^&]*)(?:&.*)?$"), SearchType.SONG),
    (re.compile(r"playsong\.html\?songmid=([^&]*)(?:&.*)?$"), SearchType.SONG),
    (re.compile(r"album\.html\?albummid=([^&]*)(?:&.*)?$"), SearchType.ALBUM),
    (re.compile(r"album\.html\?(?:.*&)?albumId=([^&]*)(?:&.*)?$"), SearchType.ALBUM),
    (re.compile(r"taoge\.html\?id=([^&]*)(?:&.*)?$"), SearchType.PLAYLIST),
]

TOKEN_SPLIT_RE = re.compile(r"[\s,;]+")
ALNUM_RE = re.compile(r"^[A-Za-z0-9]+$")
NUM_RE = re.compile(r"^\d+$")
FILL_LENGTH_RE = re.compile(r"\$fillLength\(([^)]*)\)")


class InputParseError(ValueError):
    pass


def tokenize_input(raw: str) -> List[str]:
    return [token for token in TOKEN_SPLIT_RE.split(raw.strip()) if token]


def convert_share_link(source: SearchSource, input_text: str) -> str:
    if source != SearchSource.QQ:
        return input_text

    for pattern, search_type in QQ_SHARE_PATTERNS:
        match = pattern.search(input_text)
        if match:
            keyword = SEARCH_TYPE_KEYWORDS[source][search_type]
            return keyword + match.group(1)

    return input_text


def resolve_short_link(input_text: str) -> Optional[str]:
    if "fcgi-bin/u" not in input_text:
        return None

    try:
        resp = requests.get(input_text, allow_redirects=True, timeout=10)
    except requests.RequestException:
        return None

    if resp.url and resp.url != input_text:
        return resp.url

    return None


def extract_id_from_keyword(input_text: str, keyword: str) -> Optional[str]:
    index = input_text.find(keyword)
    if index == -1:
        return None

    suffix = input_text[index + len(keyword) :]
    match = re.match(r"([A-Za-z0-9]+)", suffix)
    if not match:
        return None

    return match.group(1)


def parse_input_ids(
    raw: str, default_source: SearchSource, default_type: SearchType
) -> List[InputSongId]:
    tokens = tokenize_input(raw)
    if not tokens:
        raise InputParseError("Input is empty")

    results: List[InputSongId] = []
    for token in tokens:
        search_source = default_source
        for source, keyword in SEARCH_SOURCE_KEYWORDS.items():
            if keyword in token:
                search_source = source
                break

        token = convert_share_link(search_source, token)

        search_type = default_type
        type_keywords = SEARCH_TYPE_KEYWORDS[search_source]
        for search_type_candidate, keyword in type_keywords.items():
            if keyword in token:
                search_type = search_type_candidate
                break

        if search_source == SearchSource.NETEASE and NUM_RE.match(token):
            results.append(InputSongId(token, search_source, search_type))
            continue

        if search_source == SearchSource.QQ and ALNUM_RE.match(token):
            results.append(InputSongId(token, search_source, search_type))
            continue

        extracted = extract_id_from_keyword(token, type_keywords[search_type])
        if extracted:
            results.append(InputSongId(extracted, search_source, search_type))
            continue

        if search_source == SearchSource.QQ and "fcgi-bin/u" in token:
            redirect_url = resolve_short_link(token)
            if redirect_url:
                nested = parse_input_ids(redirect_url, search_source, search_type)
                results.extend(nested)
                continue

        raise InputParseError(f"Illegal input: {token}")

    return results


def batch(iterable: Iterable[str], size: int) -> Iterator[List[str]]:
    if size <= 0:
        raise ValueError("Batch size must be > 0")

    bucket: List[str] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = name.strip()
    return name or "lyrics"


def render_filename(template: str, tokens: Dict[str, str]) -> str:
    result = template
    for key, value in tokens.items():
        result = result.replace(f"${{{key}}}", value)

    for match in FILL_LENGTH_RE.finditer(result):
        raw = match.group(0)
        params = match.group(1).split(",")
        if len(params) != 3:
            continue
        content, symbol, length_str = [p.strip() for p in params]
        try:
            target_length = int(length_str)
        except ValueError:
            continue

        filled = content
        while len(filled) < target_length:
            diff = target_length - len(filled)
            filled = (symbol[:diff] if diff < len(symbol) else symbol) + filled

        result = result.replace(raw, filled)

    return safe_filename(result)


def format_duration(duration_ms: int) -> str:
    total_seconds = max(0, duration_ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"
