"""`codetwin review` chooses the commit it diffs against once (#92)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from codetwin.commands.review import review_base


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo: Path, text: str) -> str:
    (repo / "a.py").write_text(text)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "c")
    return _git(repo, "rev-parse", "HEAD")


def test_a_pull_request_diffs_against_where_it_left_its_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A recorded base older than the PR's base must not bring in lines the PR did not change."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    recorded = _commit(repo, "x = 1\ny = 2\nz = 3\n")
    pr_base = _commit(repo, "x = 10\ny = 2\nz = 3\n")         # merged into the base branch after the recording
    _commit(repo, "x = 10\ny = 2\nz = 30\n")                  # the pull request's own change
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 1, "base": {"sha": pr_base}}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    assert review_base(repo, recorded) == pr_base
    assert "+x = 10" not in _git(repo, "diff", review_base(repo, recorded) or "", "--")     # not changed by the PR
    monkeypatch.delenv("GITHUB_EVENT_PATH")
    assert review_base(repo, recorded) == recorded            # outside a pull request: the recorded base
