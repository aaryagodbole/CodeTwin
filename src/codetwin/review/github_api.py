"""Post a review to a GitHub pull request (REST API). Used by the GitHub Action; needs `pull-requests: write`.

* The summary is one issue comment, found again by `render.MARKER` and edited in place on every push.
* Inline comments go into one pull-request review per push; a comment whose finding fingerprint is already on
  the pull request is skipped, so the same finding is never posted twice.

The token comes only from the environment (GITHUB_TOKEN); it is never printed or returned.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model import Review
from .render import MARKER, github, markdown

API = "https://api.github.com"
_FP = re.compile(r"<!-- codetwin-fp:([0-9a-f]{16}) -->")


@dataclass
class Target:
    repo: str            # owner/name
    number: int          # pull request number

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Target:
        """GITHUB_REPOSITORY and the pull request number from the event file of a pull_request workflow."""
        env = dict(os.environ) if env is None else env
        repo = env.get("GITHUB_REPOSITORY", "")
        event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text()) if env.get("GITHUB_EVENT_PATH") else {}
        number = (event.get("pull_request") or {}).get("number") or event.get("number")
        if not repo or not number:
            raise RuntimeError("not in a pull_request workflow (GITHUB_REPOSITORY / pull request number missing)")
        return cls(repo, int(number))


@dataclass
class Poster:
    target: Target
    token: str
    transport: Any = None                     # tests inject httpx.MockTransport
    posted: dict[str, Any] = field(default_factory=dict)

    def _client(self):
        import httpx
        return httpx.Client(base_url=API, transport=self.transport, timeout=30, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"})

    def _all(self, http, url: str) -> list[dict]:
        out: list[dict] = []
        page = 1
        while True:
            r = http.get(url, params={"per_page": 100, "page": page})
            r.raise_for_status()
            items = r.json()
            out += items
            if len(items) < 100:
                return out
            page += 1

    def post(self, review: Review, in_diff) -> dict[str, Any]:
        t = self.target
        body = markdown(review)
        with self._client() as http:
            mine = [c for c in self._all(http, f"/repos/{t.repo}/issues/{t.number}/comments")
                    if MARKER in (c.get("body") or "")]
            if mine:
                r = http.patch(f"/repos/{t.repo}/issues/comments/{mine[0]['id']}", json={"body": body})
            else:
                r = http.post(f"/repos/{t.repo}/issues/{t.number}/comments", json={"body": body})
            r.raise_for_status()
            self.posted["summary"] = "updated" if mine else "created"

            existing = {m for c in self._all(http, f"/repos/{t.repo}/pulls/{t.number}/comments")
                        for m in _FP.findall(c.get("body") or "")}
            payload = github(review, in_diff)
            payload["comments"] = [c for c in payload["comments"] if not set(_FP.findall(c["body"])) & existing]
            self.posted["inline"] = len(payload["comments"])
            if payload["comments"]:
                r = http.post(f"/repos/{t.repo}/pulls/{t.number}/reviews", json=payload)
                r.raise_for_status()
        return self.posted


def post_from_env(review: Review, in_diff, env: dict[str, str] | None = None, transport: Any = None) -> dict:
    env = dict(os.environ) if env is None else env
    token = env.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set; pass it to the step as an environment variable")
    return Poster(Target.from_env(env), token, transport).post(review, in_diff)
