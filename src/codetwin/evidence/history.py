"""Co-change history: which files changed together in earlier commits.

One reader for the engine (co-change features) and the knowledge graph (co-change edges), so both see the same
commits and the same paths.
"""
from __future__ import annotations

from pathlib import Path

from .diff import git


def commits_until(root: str | Path, rev: str, limit: int) -> list[list[str]]:
    """Files of the last `limit` first-parent commits up to and including `rev`, oldest first.

    Raises RuntimeError when git cannot read the history (unknown revision, not a repository); the caller decides
    whether that is an error or a note."""
    # -z: NUL-separated, unquoted paths (spaces, quotes and non-ASCII names stay intact); %x1e frames each commit.
    out = git(Path(root), "log", "--first-parent", "--name-only", "-z", "--format=%x1e", "-n", str(limit), rev, "--")
    commits = [[p.strip("\n") for p in c.split("\0") if p.strip("\n")] for c in out.split("\x1e")]
    return [c for c in commits if c][::-1]
