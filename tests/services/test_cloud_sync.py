from __future__ import annotations

import json

import pytest

from gre_vocab_app.services import cloud_sync


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


def test_cloud_sync_validates_endpoint_and_token():
    with pytest.raises(cloud_sync.CloudSyncError, match="网址"):
        cloud_sync.download_progress("", "gre_" + "x" * 40)
    with pytest.raises(cloud_sync.CloudSyncError, match="令牌"):
        cloud_sync.download_progress("https://example.com", "bad")


def test_cloud_sync_uploads_and_downloads_progress(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        if request.method == "PUT":
            return FakeResponse({"updated_at": "2026-07-22T00:00:00Z"})
        return FakeResponse({"progress": {"schema": "gre-vocab-progress"}})

    monkeypatch.setattr(cloud_sync, "urlopen", fake_urlopen)
    token = "gre_" + "x" * 40
    assert cloud_sync.upload_progress(
        "https://example.com", token, {"schema": "gre-vocab-progress"}
    ) == "2026-07-22T00:00:00Z"
    assert cloud_sync.download_progress("https://example.com", token) == {
        "schema": "gre-vocab-progress"
    }
    assert calls[0][0].headers["Authorization"] == f"Bearer {token}"
    assert calls[0][1] == 15


def test_accountless_sync_code_encrypts_progress_before_upload(monkeypatch):
    stored = None
    calls = []

    def fake_urlopen(request, timeout):
        nonlocal stored
        calls.append((request, timeout))
        if request.method == "PUT":
            stored = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"updated_at": "2026-07-22T01:00:00Z"})
        return FakeResponse({"progress": stored, "updated_at": "2026-07-22T01:00:00Z"})

    monkeypatch.setattr(cloud_sync, "urlopen", fake_urlopen)
    code = "GRE1-" + cloud_sync._base64url_encode(bytes(range(32)))
    progress = {"schema": "gre-vocab-progress", "version": 1, "private": "仅设备可见"}

    assert cloud_sync.upload_progress("https://example.com", code, progress) == "2026-07-22T01:00:00Z"
    assert stored["algorithm"] == "AES-256-GCM"
    assert "仅设备可见" not in calls[0][0].data.decode("utf-8")
    assert cloud_sync.download_progress("https://example.com", code) == progress
    assert "/api/code-progress?space=" in calls[0][0].full_url
    assert calls[0][0].headers["Authorization"].startswith("Bearer gsa_")


def test_accountless_sync_code_generation_and_validation():
    code = cloud_sync.create_sync_code()
    assert code.startswith("GRE1-")
    assert cloud_sync.normalize_sync_code(f"  {code}\n") == code
    with pytest.raises(cloud_sync.CloudSyncError, match="GRE1"):
        cloud_sync.normalize_sync_code("gre_bad")
