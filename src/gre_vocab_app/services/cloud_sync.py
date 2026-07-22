from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DEFAULT_CLOUD_ENDPOINT = "https://gre-3000-offline.cbg206.chatgpt.site"
SYNC_CODE_PREFIX = "GRE1-"
_SPACE_CONTEXT = b"gre-sync-space-v1:"
_AUTH_CONTEXT = b"gre-sync-auth-v1:"
_KEY_CONTEXT = b"gre-sync-encryption-v1:"


class CloudSyncError(RuntimeError):
    """Raised when the optional progress cloud cannot be used safely."""


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, base64.binascii.Error) as error:
        raise CloudSyncError("同步码格式不正确。") from error


def create_sync_code() -> str:
    """Create a high-entropy recovery code that never needs an account."""

    return f"{SYNC_CODE_PREFIX}{_base64url_encode(secrets.token_bytes(32))}"


def normalize_sync_code(code: str) -> str:
    normalized = "".join(str(code).split())
    if not normalized.startswith(SYNC_CODE_PREFIX):
        raise CloudSyncError("同步码应以 GRE1- 开头。")
    if len(_base64url_decode(normalized.removeprefix(SYNC_CODE_PREFIX))) != 32:
        raise CloudSyncError("同步码格式不正确。")
    return normalized


def _endpoint_root(endpoint: str) -> str:
    root = str(endpoint).strip().rstrip("/")
    parsed = urlparse(root)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CloudSyncError("云同步网址尚未配置。")
    return root


def _sync_credentials(code: str) -> tuple[str, str, bytes]:
    normalized = normalize_sync_code(code)
    secret = _base64url_decode(normalized.removeprefix(SYNC_CODE_PREFIX))
    space_id = hashlib.sha256(_SPACE_CONTEXT + secret).hexdigest()
    auth_token = f"gsa_{_base64url_encode(hashlib.sha256(_AUTH_CONTEXT + secret).digest())}"
    encryption_key = hashlib.sha256(_KEY_CONTEXT + secret).digest()
    return space_id, auth_token, encryption_key


def _request(
    method: str,
    url: str,
    token: str,
    payload: object | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
        "user-agent": "GRE-3000-Windows/0.3",
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
            raise CloudSyncError("同步码无效或与云端空间不匹配。") from error
        raise CloudSyncError(f"云端返回错误：HTTP {error.code}") from error
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CloudSyncError("暂时无法连接云同步服务。") from error
    if not isinstance(decoded, dict):
        raise CloudSyncError("云端返回了无效数据。")
    return decoded


def _device_credentials(endpoint: str, token: str) -> tuple[str, str]:
    token = str(token).strip()
    if not token.startswith("gre_") or len(token) < 30:
        raise CloudSyncError("设备令牌无效。")
    return f"{_endpoint_root(endpoint)}/api/device-progress", token


def _code_credentials(endpoint: str, code: str) -> tuple[str, str, bytes]:
    space_id, auth_token, key = _sync_credentials(code)
    query = urlencode({"space": space_id})
    return f"{_endpoint_root(endpoint)}/api/code-progress?{query}", auth_token, key


def _encrypt_payload(key: bytes, payload: object) -> dict[str, object]:
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return {
        "version": 1,
        "algorithm": "AES-256-GCM",
        "ciphertext": _base64url_encode(ciphertext),
        "nonce": _base64url_encode(nonce),
    }


def _decrypt_payload(key: bytes, payload: object) -> object:
    if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("algorithm") != "AES-256-GCM":
        raise CloudSyncError("云端数据版本不受支持。")
    ciphertext = payload.get("ciphertext")
    nonce = payload.get("nonce")
    if not isinstance(ciphertext, str) or not isinstance(nonce, str):
        raise CloudSyncError("云端返回了无效的加密数据。")
    try:
        plaintext = AESGCM(key).decrypt(
            _base64url_decode(nonce),
            _base64url_decode(ciphertext),
            None,
        )
        return json.loads(plaintext.decode("utf-8"))
    except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CloudSyncError("同步码不匹配或云端数据已损坏。") from error


def upload_progress(endpoint: str, token_or_code: str, payload: object) -> str:
    if str(token_or_code).strip().startswith(SYNC_CODE_PREFIX):
        url, token, key = _code_credentials(endpoint, token_or_code)
        body = _encrypt_payload(key, payload)
    else:
        url, token = _device_credentials(endpoint, token_or_code)
        body = payload
    result = _request("PUT", url, token, body)
    updated_at = result.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        raise CloudSyncError("云端没有确认保存时间。")
    return updated_at


def download_progress(endpoint: str, token_or_code: str) -> object | None:
    if str(token_or_code).strip().startswith(SYNC_CODE_PREFIX):
        url, token, key = _code_credentials(endpoint, token_or_code)
        encrypted = _request("GET", url, token).get("progress")
        return None if encrypted is None else _decrypt_payload(key, encrypted)
    url, token = _device_credentials(endpoint, token_or_code)
    return _request("GET", url, token).get("progress")
