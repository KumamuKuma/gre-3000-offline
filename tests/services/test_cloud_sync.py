from __future__ import annotations

import io
import json
import socket
from urllib.error import URLError
from urllib.request import Request

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


def test_default_endpoint_uses_the_same_sync_api_as_github_pages():
    assert cloud_sync.DEFAULT_CLOUD_ENDPOINT == (
        "https://gre-sync-kumamukuma.pages.dev"
    )


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
    assert calls[0][0].headers["User-agent"] == "GRE-3000-Windows/1.0.1"
    assert calls[0][1] == 15


@pytest.mark.parametrize(
    ("method", "failure_stage", "use_backup_dns"),
    [
        ("PUT", "connect", True),
        ("PUT", "connect", False),
        ("GET", "response", False),
        ("PUT", "response", False),
        ("POST", "response", False),
    ],
)
def test_cloud_sync_retries_backup_addresses_only_when_safe(monkeypatch, method, failure_stage, use_backup_dns):
    addresses = ["1.1.1.1", "8.8.4.4"]
    dns_requests = []
    connections = []
    account_requests = []

    def fake_getaddrinfo(*_args, **_kwargs):
        if use_backup_dns:
            raise socket.gaierror(11002, "DNS lookup failed")
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 443)) for address in addresses]

    def fake_urlopen(request, timeout):
        dns_requests.append(request)
        return io.BytesIO(json.dumps({
            "Status": 0,
            "Answer": [{"type": 1, "data": address, "TTL": 60} for address in addresses],
        }).encode())

    class FakeConnection:
        def __init__(self, address):
            self.address = address

        def connect(self):
            connections.append(self.address)
            if self.address == addresses[0] and failure_stage == "connect":
                raise TimeoutError()

        def request(self, method, path, body, headers):
            account_requests.append((self.address, method, path, json.loads(body) if body else None,
                                     headers["Authorization"]))

        def getresponse(self):
            if self.address == addresses[0] and failure_stage == "response":
                raise TimeoutError()
            response = FakeResponse({"ok": True})
            response.status = 200
            return response

        def close(self):
            pass

    monkeypatch.setattr(cloud_sync, "urlopen", fake_urlopen)
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(cloud_sync, "getproxies", dict)
    monkeypatch.setattr(cloud_sync, "_DNS_CACHE", (0, ()))
    monkeypatch.setattr(cloud_sync, "_PREFERRED_ADDRESS", "")
    monkeypatch.setattr(cloud_sync, "_ResolvedHTTPSConnection", FakeConnection)

    path = "/api/sync-account?username=example"
    payload = {"vault": "example"} if method == "PUT" else None
    url = cloud_sync.DEFAULT_CLOUD_ENDPOINT + path
    if method != "GET" and failure_stage == "response":
        sent_to = addresses[:1]
        with pytest.raises(cloud_sync.CloudSyncError, match="暂时无法连接"):
            cloud_sync._request(method, url, "test-token", payload)
    else:
        sent_to = addresses if failure_stage == "response" else addresses[1:]
        assert cloud_sync._request(method, url, "test-token", payload) == {"ok": True}
        assert cloud_sync._PREFERRED_ADDRESS == addresses[-1]
    assert len(dns_requests) == int(use_backup_dns)
    if use_backup_dns:
        assert dns_requests[0].split("?")[1] == "name=gre-sync-kumamukuma.pages.dev&type=A"
    assert connections == (addresses if addresses[-1] in sent_to else addresses[:1])
    assert account_requests == [(address, method, path, payload, "Bearer test-token") for address in sent_to]


def test_backup_dns_does_not_override_a_custom_sync_endpoint(monkeypatch):
    def fake_urlopen(request, timeout):
        assert isinstance(request, Request)
        raise URLError(socket.gaierror(11002, "DNS lookup failed"))

    monkeypatch.setattr(cloud_sync, "urlopen", fake_urlopen)

    with pytest.raises(cloud_sync.CloudSyncError, match="暂时无法连接"):
        cloud_sync._request("GET", "https://example.com/api/sync-account", None)


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
    assert cloud_sync.download_progress_with_timestamp("https://example.com", code) == (
        progress, "2026-07-22T01:00:00Z",
    )
    assert "/api/code-progress?space=" in calls[0][0].full_url
    assert calls[0][0].headers["Authorization"].startswith("Bearer gsa_")


def test_accountless_sync_code_generation_and_validation():
    code = cloud_sync.create_sync_code()
    assert code.startswith("GRE1-")
    assert cloud_sync.normalize_sync_code(f"  {code}\n") == code
    with pytest.raises(cloud_sync.CloudSyncError, match="GRE1"):
        cloud_sync.normalize_sync_code("gre_bad")
