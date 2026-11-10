from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import cloud_sync as cloud


def valid_username(username: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,31}", username))


def connect_account(username: str, password: str, register: bool, existing_code: str) -> tuple[str, str]:
    username = username.strip().lower()
    if not valid_username(username):
        raise cloud.CloudSyncError("用户名为 3–32 位字母、数字、下划线或短横线，以字母或数字开头。")
    if not password:
        raise cloud.CloudSyncError("请输入密码。")
    if len(password) > 128:
        raise cloud.CloudSyncError("密码最多 128 个字符。")
    url = f"{cloud.DEFAULT_CLOUD_ENDPOINT}/api/sync-account?{urlencode({'username': username})}"
    associated_data = f"gre-account-v1:{username}".encode()
    try:
        if register:
            salt = secrets.token_bytes(16)
        else:
            salt = cloud._base64url_decode(cloud._request("GET", url, None).get("salt", ""))
            if len(salt) != 16:
                raise cloud.CloudSyncError("账号同步数据无效。")
        bits = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000, dklen=64)
        token = f"gua_{cloud._base64url_encode(bits[:32])}"
        cipher = AESGCM(bits[32:])
        if register:
            code = cloud.normalize_sync_code(existing_code) if existing_code else cloud.create_sync_code()
            nonce = secrets.token_bytes(12)
            cloud._request("PUT", url, token, {
                "salt": cloud._base64url_encode(salt),
                "nonce": cloud._base64url_encode(nonce),
                "wrappedCode": cloud._base64url_encode(cipher.encrypt(nonce, code.encode(), associated_data)),
            })
            return username, code
        wrapped = cloud._request("POST", url, token)
        code = cipher.decrypt(cloud._base64url_decode(wrapped["nonce"]),
                              cloud._base64url_decode(wrapped["wrappedCode"]), associated_data).decode()
        return username, cloud.normalize_sync_code(code)
    except cloud.CloudSyncHTTPError as error:
        messages = {401: "用户名或密码不正确。", 409: "用户名已被使用，请登录或换一个名字。", 429: "尝试太频繁，请稍后再试。"}
        raise cloud.CloudSyncError(messages.get(error.status, str(error))) from error
    except (InvalidTag, KeyError, TypeError, ValueError) as error:
        raise cloud.CloudSyncError("无法解密账号中的同步码。") from error


def progress_signature(progress: dict) -> str:
    content = {key: value for key, value in progress.items() if key != "exported_at"}
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def has_learning(progress: dict) -> bool:
    return bool(progress["stars"] or progress["notes"] or progress["marks"] or progress["recent_marks"]
                or any(item["completed_count"] or item["current_word_id"] for item in progress["lists"].values())
                or any(key in progress["settings"] for key in (
                    "study_star_current_word_id", "study_machine7_current_word_id", "study_marks_current_word_id")))


@dataclass(frozen=True)
class SyncResult:
    status: str
    nonce: str | None = None
    progress: object = None


def synchronize_account(code: str, local: dict, baseline: dict, choice: str = "") -> SyncResult:
    url, token, key = cloud._code_credentials(cloud.DEFAULT_CLOUD_ENDPOINT, code)
    result = cloud._request("GET", url + "&protocol=2", token)
    if result.get("conditional_write") is not True:
        raise cloud.CloudSyncError("云同步服务暂时不支持安全写入。")
    encrypted = result.get("progress")
    remote = cloud._decrypt_payload(key, encrypted) if encrypted is not None else None
    if remote is not None and not isinstance(remote, dict):
        raise cloud.CloudSyncError("云端进度格式无效。")
    nonce = encrypted["nonce"] if encrypted is not None else None
    signature = progress_signature(local)
    if choice == "download":
        return SyncResult("download" if remote is not None else "empty", nonce, remote)
    if choice != "upload":
        if remote is not None and (signature == progress_signature(remote) or
                                    (baseline.get("nonce") == nonce and baseline.get("signature") == signature)):
            return SyncResult("match", nonce)
        if remote is not None and (baseline.get("signature") == signature or (not baseline and not has_learning(local))):
            return SyncResult("download", nonce, remote)
        if baseline.get("nonce") != nonce:
            return SyncResult("conflict", nonce)
        if remote is None and not has_learning(local):
            return SyncResult("empty")
    payload = cloud._encrypt_payload(key, local)
    try:
        cloud._request("PUT", url, token, {**payload, "expected_nonce": nonce})
    except cloud.CloudSyncHTTPError as error:
        if error.status == 409:
            return SyncResult("conflict", nonce)
        raise
    return SyncResult("upload", payload["nonce"])
