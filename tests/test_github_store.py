from __future__ import annotations

import base64
import json

import pytest
from src.storage.github_store import connect_from_env
from src.storage.r2_store import empty_state


class FakeResponse:
    def __init__(self, code, payload=None):
        self.status_code = code
        self._payload = payload or {}
        self.content = json.dumps(self._payload).encode()
        self.text = self.content.decode()
        self.ok = code < 400

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *, state_exists):
        self.headers = {}
        self.state_exists = state_exists
        self.writes = []
        self.branch_creations = []

    def get(self, url, **kwargs):
        if "/contents/state.json" in url:
            if not self.state_exists:
                return FakeResponse(404)
            encoded = base64.b64encode(json.dumps(empty_state()).encode()).decode()
            return FakeResponse(200, {"sha": "oldsha", "content": encoded})
        if "/git/ref/heads/" in url:
            return FakeResponse(404)
        raise AssertionError(url)

    def request(self, method, url, **kwargs):
        body = kwargs["json"]
        if method == "POST":
            self.branch_creations.append(body)
            return FakeResponse(201, {"ref": body["ref"]})
        if method == "PUT":
            self.writes.append(body)
            return FakeResponse(201, {"content": {"sha": f"newsha{len(self.writes)}"}})
        raise AssertionError(method)


def _env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "harvey-moeid/tvtm")
    monkeypatch.setenv("GITHUB_SHA", "abc123")


def test_read_existing_github_state_and_write_with_blob_sha(monkeypatch):
    import requests
    _env(monkeypatch)
    session = FakeSession(state_exists=True)
    monkeypatch.setattr(requests, "Session", lambda: session)
    store = connect_from_env()
    store.rows.append({"signal_key": "s1"})
    store.save()
    store.save()
    assert session.branch_creations == []
    assert session.writes[0]["branch"] == "tvtm-state"
    assert session.writes[0]["sha"] == "oldsha"
    assert session.writes[1]["sha"] == "newsha1"


def test_migrates_existing_legacy_state_without_reset(monkeypatch):
    import requests
    import src.storage.r2_store as legacy
    _env(monkeypatch)
    session = FakeSession(state_exists=False)
    monkeypatch.setattr(requests, "Session", lambda: session)
    historical = empty_state()
    historical["signals"].append({"signal_key": "historical", "notified": 1})
    class Existing:
        state = historical
    monkeypatch.setattr(legacy, "connect_from_env", lambda: Existing())
    store = connect_from_env()
    assert store.state == historical
    assert session.branch_creations[0]["ref"] == "refs/heads/tvtm-state"
    imported = json.loads(base64.b64decode(session.writes[0]["content"]))
    assert imported == historical
    store.save()
    assert session.writes[1]["sha"] == "newsha1"


def test_missing_state_fails_closed_when_legacy_unavailable(monkeypatch):
    import requests
    import src.storage.r2_store as legacy
    _env(monkeypatch)
    monkeypatch.setattr(requests, "Session", lambda: FakeSession(state_exists=False))
    def blocked():
        raise RuntimeError("R2 tidak tersedia")
    monkeypatch.setattr(legacy, "connect_from_env", blocked)
    with pytest.raises(RuntimeError, match="R2 tidak tersedia"):
        connect_from_env()
