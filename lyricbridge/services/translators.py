from __future__ import annotations

import hashlib
import random
from typing import List, Optional

import requests

from ..config import AppConfig


class TranslatorError(RuntimeError):
    pass


class BaseTranslator:
    def translate(self, lines: List[str], target_lang: str) -> List[str]:
        raise NotImplementedError


class BaiduTranslator(BaseTranslator):
    def __init__(self, app_id: str, secret: str) -> None:
        self._app_id = app_id
        self._secret = secret

    def translate(self, lines: List[str], target_lang: str) -> List[str]:
        results: List[str] = []
        for line in lines:
            if not line.strip():
                results.append("")
                continue

            salt = str(random.randint(10000, 99999))
            sign_raw = f"{self._app_id}{line}{salt}{self._secret}"
            sign = hashlib.md5(sign_raw.encode("utf-8")).hexdigest()
            params = {
                "q": line,
                "from": "auto",
                "to": target_lang,
                "appid": self._app_id,
                "salt": salt,
                "sign": sign,
            }
            try:
                resp = requests.get(
                    "https://fanyi-api.baidu.com/api/trans/vip/translate",
                    params=params,
                    timeout=15,
                )
                data = resp.json()
            except requests.RequestException as exc:
                raise TranslatorError("Baidu translate request failed") from exc

            if "trans_result" not in data:
                raise TranslatorError(data.get("error_msg", "Baidu translate failed"))
            results.append(data["trans_result"][0].get("dst", ""))

        return results


class CaiyunTranslator(BaseTranslator):
    def __init__(self, token: str) -> None:
        self._token = token

    def translate(self, lines: List[str], target_lang: str) -> List[str]:
        if not lines:
            return []

        payload = {
            "source": lines,
            "trans_type": f"auto2{target_lang}",
            "request_id": "lyricbridge",
            "detect": True,
        }
        headers = {
            "X-Authorization": f"token {self._token}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                "https://api.interpreter.caiyunai.com/v1/translator",
                json=payload,
                headers=headers,
                timeout=15,
            )
            data = resp.json()
        except requests.RequestException as exc:
            raise TranslatorError("Caiyun translate request failed") from exc

        if "target" not in data:
            raise TranslatorError("Caiyun translate failed")
        return [str(item) for item in data["target"]]


def get_translator(config: AppConfig) -> Optional[BaseTranslator]:
    if config.translation_provider == "baidu" and config.baidu_app_id and config.baidu_secret:
        return BaiduTranslator(config.baidu_app_id, config.baidu_secret)
    if config.translation_provider == "caiyun" and config.caiyun_token:
        return CaiyunTranslator(config.caiyun_token)
    return None
