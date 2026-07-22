from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_CLOUD_ENDPOINT = "https://gre-3000-offline.cbg206.chatgpt.site"


class CloudSyncError(RuntimeError):
    """Raised when the optional progress cloud cannot be used safely."""


def _validate(endpoint: str, token: str) -> tuple[str, str]:
    endpoint = str(endpoint).strip().rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CloudSyncError("云同步网址尚未配置。")
    token = str(token).strip()
    if not token.startswith("gre_") or len(token) < 30:
        raise CloudSyncError("Windows 设备令牌无效。")
    return f"{endpoint}/api/device-progress", token


def _request(
    method: str,
    endpoint: str,
    token: str,
    payload: object | None = None,
) -> dict[str, Any]:
    url, token = _validate(endpoint, token)
    data = None
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "user-agent": "GRE-3000-Windows/0.2",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json; charset=utf-8"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise CloudSyncError("设备令牌已失效，请在网页版重新生成。") from error
        raise CloudSyncError(f"云端返回错误：HTTP {error.code}") from error
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CloudSyncError("暂时无法连接云同步服务。") from error
    if not isinstance(decoded, dict):
        raise CloudSyncError("云端返回了无效数据。")
    return decoded


def upload_progress(endpoint: str, token: str, payload: object) -> str:
    result = _request("PUT", endpoint, token, payload)
    updated_at = result.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        raise CloudSyncError("云端没有确认保存时间。")
    return updated_at


def download_progress(endpoint: str, token: str) -> object | None:
    return _request("GET", endpoint, token).get("progress")
