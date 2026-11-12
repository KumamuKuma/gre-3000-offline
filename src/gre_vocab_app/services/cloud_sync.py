from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import secrets
import socket
import ssl
from collections.abc import Iterator
from http.client import HTTPSConnection, HTTPException
from time import monotonic
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, getproxies, proxy_bypass, urlopen

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_SYNC_HOST = "gre-sync-kumamukuma.pages.dev"
DEFAULT_CLOUD_ENDPOINT = f"https://{_SYNC_HOST}"
_DNS_RESOLVERS = ("https://223.5.5.5/resolve", "https://8.8.8.8/resolve")
_DNS_CACHE: tuple[float, tuple[str, ...]] = (0, ())
_PREFERRED_ADDRESS = ""
SYNC_CODE_PREFIX = "GRE1-"
_SPACE_CONTEXT = b"gre-sync-space-v1:"
_AUTH_CONTEXT = b"gre-sync-auth-v1:"
_KEY_CONTEXT = b"gre-sync-encryption-v1:"


class CloudSyncError(RuntimeError):
    """Raised when the optional progress cloud cannot be used safely."""


class CloudSyncHTTPError(CloudSyncError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


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
    secret = _base64url_decode(normalized.removeprefix(SYNC_CODE_PREFIX))
    if len(secret) != 32:
        raise CloudSyncError("同步码格式不正确。")
    return SYNC_CODE_PREFIX + _base64url_encode(secret)


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


def _resolve_sync_host() -> tuple[str, ...]:
    global _DNS_CACHE
    expires, addresses = _DNS_CACHE
    if monotonic() < expires:
        return addresses
    query = urlencode({"name": _SYNC_HOST, "type": "A"})
    for resolver in _DNS_RESOLVERS:
        try:
            with urlopen(f"{resolver}?{query}", timeout=5) as response:
                result = json.loads(response.read(16_384))
            if result.get("Status") != 0:
                continue
            answers = {}
            for answer in result.get("Answer", []):
                if answer.get("type") != 1:
                    continue
                address = ipaddress.IPv4Address(answer["data"])
                if address.is_global:
                    answers[str(address)] = int(answer.get("TTL", 0))
            if answers:
                addresses = tuple(answers)[:3]
                ttl = min(300, max(0, min(answers[address] for address in addresses)))
                _DNS_CACHE = (monotonic() + ttl, addresses)
                return addresses
        except (OSError, HTTPException, ValueError, TypeError, AttributeError, KeyError):
            continue
    raise CloudSyncError("无法解析云同步服务的域名，请稍后重试。")


class _ResolvedHTTPSConnection(HTTPSConnection):
    def __init__(self, address: str):
        self._resolved_address = address
        self._tls = ssl.create_default_context()
        self._tls.set_alpn_protocols(["http/1.1"])
        super().__init__(_SYNC_HOST, timeout=6, context=self._tls)

    def connect(self) -> None:
        raw_socket = socket.create_connection((self._resolved_address, self.port), self.timeout)
        try:
            # Keep TLS and HTTP verification tied to the service hostname.
            self.sock = self._tls.wrap_socket(raw_socket, server_hostname=self.host)
            self.sock.settimeout(15)
        except OSError:
            raw_socket.close()
            raise


def _sync_addresses() -> Iterator[str]:
    try:
        entries = socket.getaddrinfo(_SYNC_HOST, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        entries = []
    addresses = dict.fromkeys(entry[4][0] for entry in entries)
    preferred = _PREFERRED_ADDRESS
    if preferred in addresses:
        yield preferred
    for address in addresses:
        if address != preferred:
            yield address

    try:
        backup = _resolve_sync_host()
    except CloudSyncError:
        if not addresses:
            raise
        return
    for address in backup:
        if address not in addresses:
            yield address


def _read_sync_response(request: Request) -> bytes:
    global _PREFERRED_ADDRESS
    uses_proxy = getproxies().get("https") and not proxy_bypass(_SYNC_HOST)
    if request.type != "https" or request.host != _SYNC_HOST or uses_proxy:
        with urlopen(request, timeout=15) as response:
            return response.read()

    method = request.get_method()
    for address in _sync_addresses():
        connection = _ResolvedHTTPSConnection(address)
        try:
            connection.connect()
        except OSError:
            connection.close()
            continue
        try:
            connection.request(method, request.selector, request.data, dict(request.header_items()))
            with connection.getresponse() as response:
                if not 200 <= response.status < 300:
                    raise HTTPError(request.full_url, response.status, response.reason, response.headers, None)
                body = response.read()
                _PREFERRED_ADDRESS = address
                return body
        except HTTPError:
            raise
        except (OSError, HTTPException):
            # A read can safely use the next address; a submitted write may already have succeeded.
            if method != "GET":
                raise
        finally:
            connection.close()
    raise CloudSyncError("已解析同步域名，但暂时无法连接云同步服务。")


def _request(
    method: str,
    url: str,
    token: str | None,
    payload: object | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "accept": "application/json",
        "user-agent": "GRE-3000-Windows/1.0.1",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json; charset=utf-8"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        decoded = json.loads(_read_sync_response(request).decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise CloudSyncHTTPError(401, "同步码无效或与云端空间不匹配。") from error
        raise CloudSyncHTTPError(error.code, f"云端返回错误：HTTP {error.code}") from error
    except (OSError, HTTPException, UnicodeDecodeError, json.JSONDecodeError) as error:
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
    progress, _ = download_progress_with_timestamp(endpoint, token_or_code)
    return progress


def download_progress_with_timestamp(endpoint: str, token_or_code: str) -> tuple[object | None, str | None]:
    if str(token_or_code).strip().startswith(SYNC_CODE_PREFIX):
        url, token, key = _code_credentials(endpoint, token_or_code)
        result = _request("GET", url, token)
        encrypted = result.get("progress")
        progress = None if encrypted is None else _decrypt_payload(key, encrypted)
    else:
        url, token = _device_credentials(endpoint, token_or_code)
        result = _request("GET", url, token)
        progress = result.get("progress")
    return progress, result.get("updated_at")
