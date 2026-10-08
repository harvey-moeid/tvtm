"""GitHub repository JSON state, stored in a separate branch (no R2 at runtime).

The only state writer is the serialized GitHub Actions signal workflow.
Every save uses the GitHub Contents API SHA precondition; conflicts fail closed.
If the state branch is absent, the FIRST run migrates the existing R2 state,
rather than silently starting an empty database and losing open trades.
"""
from __future__ import annotations

import base64
import json
import logging
import os

import requests

from src.config_loader import require_env
from src.storage.r2_store import JSONStore

log = logging.getLogger(__name__)
STATE_BRANCH = "tvtm-state"
STATE_PATH = "state.json"
TIMEOUT = 20


def connect_from_env() -> JSONStore:
    token = require_env("GITHUB_TOKEN")
    repository = require_env("GITHUB_REPOSITORY")
    branch = os.getenv("TVTM_STATE_BRANCH", STATE_BRANCH)
    if not branch or "/" in branch or branch.startswith("."):
        raise RuntimeError("TVTM_STATE_BRANCH tidak valid")

    client = requests.Session()
    client.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    root = f"https://api.github.com/repos/{repository}"
    file_url = f"{root}/contents/{STATE_PATH}"

    def api(method, url, **kwargs):
        response = client.request(method, url, timeout=TIMEOUT, **kwargs)
        if not response.ok:
            raise RuntimeError(f"GitHub state {method} failed HTTP {response.status_code}: {response.text[:300]}")
        return response.json() if response.content else {}

    response = client.get(file_url, params={"ref": branch}, timeout=TIMEOUT)
    if response.status_code == 200:
        payload = response.json()
        if not payload.get("content"):
            raise RuntimeError("GitHub state.json terlalu besar/format tidak didukung")
        state = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
        blob_sha = payload["sha"]
    elif response.status_code == 404:
        # The branch/file might be absent after cutover. Do NOT initialize
        # an empty state: existing R2 state contains historical/live trades.
        from src.storage.r2_store import connect_from_env as read_legacy_r2
        log.warning("GitHub state missing: importing legacy R2 data exactly once")
        state = read_legacy_r2().state

        ref_response = client.get(f"{root}/git/ref/heads/{branch}", timeout=TIMEOUT)
        if ref_response.status_code == 404:
            sha = require_env("GITHUB_SHA")
            api("POST", f"{root}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha})
        elif not ref_response.ok:
            raise RuntimeError(f"Cannot verify GitHub state branch: HTTP {ref_response.status_code}")

        created = api("PUT", file_url, json={
            "message": "data: migrate original R2 state into GitHub JSON",
            "content": base64.b64encode(json.dumps(state, ensure_ascii=False).encode()).decode(),
            "branch": branch,
        })
        blob_sha = created["content"]["sha"]
        log.warning("Legacy state migration succeeded; GitHub is now source of truth")
    else:
        raise RuntimeError(f"GitHub state read HTTP {response.status_code}: {response.text[:300]}")

    sha_box = [blob_sha]

    def save(new_state):
        body = json.dumps(new_state, ensure_ascii=False, separators=(",", ":"))
        result = api("PUT", file_url, json={
            "message": "data: update trading signals and virtual positions",
            "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
            "sha": sha_box[0],
            "branch": branch,
        })
        sha_box[0] = result["content"]["sha"]

    return JSONStore(state, save_callback=save)
