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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model import Review
from .render import MARKER, github, markdown

API = "https://api.github.com"
_FP = re.compile(r"<!-- codetwin-fp:([0-9a-f]{16}) -->")
InDiff = Callable[[str | None, int | None], bool]


class PostError(RuntimeError):
    """GitHub refused or answered unexpectedly. The message has the HTTP status, never the token."""


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

    def _client(self) -> Any:
        import httpx
        return httpx.Client(base_url=API, transport=self.transport, timeout=30, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"})

    @staticmethod
    def _check(r: Any, what: str) -> Any:
        if r.status_code >= 400:
            hint = " (read-only token: fork or Dependabot pull request, or missing `pull-requests: write`)" \
                if r.status_code in (401, 403, 404) else ""
            raise PostError(f"GitHub returned {r.status_code} while {what}{hint}")
        return r

    def _all(self, http: Any, url: str) -> list[dict]:
        out: list[dict] = []
        page = 1
        while True:
            items = self._check(http.get(url, params={"per_page": 100, "page": page}), "listing comments").json()
            if not isinstance(items, list):
                raise PostError(f"unexpected answer from GitHub for {url}: not a list")
            out += [c for c in items if isinstance(c, dict) and isinstance(c.get("body") or "", str)]
            if len(items) < 100:
                return out
            page += 1

    @staticmethod
    def _is_summary(c: dict) -> bool:
        """Our summary comment: written by a bot (the Actions token posts as github-actions[bot]) and starting
        with the marker. A person quoting the marker in a comment is never edited."""
        u = c.get("user")
        user: dict = u if isinstance(u, dict) else {}
        return user.get("type") == "Bot" and (c.get("body") or "").startswith(MARKER) and isinstance(c.get("id"), int)

    def post(self, review: Review, in_diff: InDiff) -> dict[str, Any]:
        import httpx
        try:
            return self._post(review, in_diff)
        except httpx.HTTPError as e:      # timeouts, connection errors: never the token, only the error type
            raise PostError(f"could not reach GitHub ({type(e).__name__})") from None

    def _post(self, review: Review, in_diff: InDiff) -> dict[str, Any]:
        t = self.target
        body = markdown(review)
        with self._client() as http:
            mine = [c for c in self._all(http, f"/repos/{t.repo}/issues/{t.number}/comments") if self._is_summary(c)]
            if mine:
                self._check(http.patch(f"/repos/{t.repo}/issues/comments/{mine[0]['id']}", json={"body": body}),
                            "updating the summary comment")
            else:
                self._check(http.post(f"/repos/{t.repo}/issues/{t.number}/comments", json={"body": body}),
                            "posting the summary comment")
            self.posted["summary"] = "updated" if mine else "created"

            existing = {m for c in self._all(http, f"/repos/{t.repo}/pulls/{t.number}/comments")
                        for m in _FP.findall(c.get("body") or "")}
            payload = github(review, in_diff)
            payload["comments"] = [c for c in payload["comments"] if not set(_FP.findall(c["body"])) & existing]
            self.posted["inline"] = len(payload["comments"])
            if payload["comments"]:
                self._check(http.post(f"/repos/{t.repo}/pulls/{t.number}/reviews", json=payload),
                            "posting inline comments")
        return self.posted


def post_from_env(review: Review, in_diff: InDiff, env: dict[str, str] | None = None,
                  transport: Any = None) -> dict:
    env = dict(os.environ) if env is None else env
    token = env.get("GITHUB_TOKEN")
    if not token:
        raise PostError("GITHUB_TOKEN is not set; pass it to the step as an environment variable")
    return Poster(Target.from_env(env), token, transport).post(review, in_diff)
