from __future__ import annotations

import html
import json
import urllib.parse
import urllib.request
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)


TRANSLATE_ENDPOINT = "https://api.mymemory.translated.net/get"
MAX_TRANSLATION_CHARS = 500


def _translation_from_payload(payload: dict[str, object]) -> str:
    status = payload.get("responseStatus")
    if status is not None and int(status) != 200:
        raise RuntimeError(str(payload.get("responseDetails") or "翻译服务返回错误"))
    response_data = payload.get("responseData")
    if not isinstance(response_data, dict):
        raise RuntimeError("翻译服务返回格式无效")
    translated = html.unescape(
        str(response_data.get("translatedText", "")).strip()
    )
    if not translated:
        raise RuntimeError("翻译服务没有返回结果")
    return translated


def translate_english_to_chinese(
    text: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> str:
    query = " ".join(text.split()).strip()
    if not query:
        raise ValueError("没有可翻译的文字")
    if len(query) > MAX_TRANSLATION_CHARS:
        raise ValueError(f"选中文字不能超过 {MAX_TRANSLATION_CHARS} 个字符")
    url = f"{TRANSLATE_ENDPOINT}?{urllib.parse.urlencode({'q': query, 'langpair': 'en|zh-CN'})}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GRE3000Offline/0.6"},
    )
    with opener(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _translation_from_payload(payload)


class TranslationService(QObject):
    translationReady = Signal(int, str)
    translationFailed = Signal(int, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._next_request_id = 0
        self._manager = QNetworkAccessManager(self)
        self._replies: dict[int, QNetworkReply] = {}

    def translate(self, text: str) -> int:
        query = " ".join(text.split()).strip()
        if not query:
            raise ValueError("没有可翻译的文字")
        if len(query) > MAX_TRANSLATION_CHARS:
            raise ValueError(
                f"选中文字不能超过 {MAX_TRANSLATION_CHARS} 个字符"
            )
        self._next_request_id += 1
        request_id = self._next_request_id
        url = QUrl(TRANSLATE_ENDPOINT)
        url_query = QUrlQuery()
        url_query.addQueryItem("q", query)
        url_query.addQueryItem("langpair", "en|zh-CN")
        url.setQuery(url_query)
        request = QNetworkRequest(url)
        request.setRawHeader(b"User-Agent", b"GRE3000Offline/0.6")
        reply = self._manager.get(request)
        self._replies[request_id] = reply
        timer = QTimer(reply)
        timer.setSingleShot(True)
        timer.timeout.connect(reply.abort)
        timer.start(12_000)
        reply.finished.connect(
            lambda resolved_id=request_id: self._finish(resolved_id)
        )
        return request_id

    def _finish(self, request_id: int) -> None:
        reply = self._replies.pop(request_id, None)
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                message = (
                    "翻译请求超时，请检查网络后重试"
                    if reply.error()
                    == QNetworkReply.NetworkError.OperationCanceledError
                    else reply.errorString()
                )
                self.translationFailed.emit(request_id, message)
                return
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            self.translationReady.emit(
                request_id, _translation_from_payload(payload)
            )
        except Exception as error:
            self.translationFailed.emit(request_id, str(error))
        finally:
            reply.deleteLater()

    def shutdown(self) -> None:
        for reply in tuple(self._replies.values()):
            reply.abort()
            reply.deleteLater()
        self._replies.clear()
