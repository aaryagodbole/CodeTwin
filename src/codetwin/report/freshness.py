"""Section: how many commits old the recorded evidence is (freshness).

CodeTwin compares a code change with a test run recorded earlier by `codetwin record`.
If many commits have been made since that recording, the recorded evidence is out of date
and test selection is less trustworthy. This section counts the commits reachable from HEAD
but not from the recorded commit (`git rev-list --left-right --count <base>...HEAD`, right
side), including commits brought in by merges, and flags the evidence as stale.

Merged commits count on purpose (no `--first-parent`): evidence goes stale because the code
changed since the recording, and commits brought in by a merge change the code just as local
commits do. Teams that merge often can raise `[freshness] stale_after`.

Output shape:
    "freshness": {
      "commits_behind": 3,
      "stale": false,
      "stale_after": 20,
      "summary": "recorded evidence is 3 commits old (not stale)"
    }

- `commits_behind`: commits since the recorded commit, or null when the exact age cannot be
  established: no recorded commit, the recorded commit is gone from this history, HEAD is not
  based on it (older checkout, other branch, rebase), or a shallow clone cuts the history.
- `stale`: true when `commits_behind > stale_after`. Also true when the exact count is unknown
  but the evidence is certainly out of date: the recorded commit is gone from a complete
  (not shallow) history, or a shallow clone already shows more than `stale_after` commits.
- `stale_after`: `[freshness] stale_after` in .codetwin.toml (default 20; 0 means stale after
  one commit).
- `summary`: one line for people. Consumers show it instead of `commits_behind` when that is
  null, and never print "null commits" or test `commits_behind > 0`.

Error handling: only "the recorded commit is not in this checkout" is an expected result.
Git missing from PATH, a root that is not a repository, any other git failure and unparsable
git output are real failures and are not caught here, so `report.build()` shows them as a
broken section.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..evidence.diff import git

if TYPE_CHECKING:
    from . import Context

# Section name under "extras" in `codetwin select --json`
NAME = "freshness"

# Opt-in to reports sent to CodeTwin Cloud (only numbers and summaries, no source code)
PUBLISH = True

# Default commit threshold after which recorded evidence is considered stale
DEFAULT_STALE_AFTER = 20

_RECORD = "run `codetwin record`"


def get_stale_after(cfg: Any) -> int:
    """Read the freshness limit `stale_after` from [freshness] in .codetwin.toml.

    Looks for `[freshness] stale_after = <int>`. If missing, not an integer,
    or negative, falls back to the default of 20. A limit of 0 is valid (stale after 1 commit).
    """
    # Config.section returns a dict, or a list for an array of tables ([[freshness]])
    sec = cfg.section("freshness")
    if not isinstance(sec, dict):
        return DEFAULT_STALE_AFTER
    val = sec.get("stale_after")
    # bool is a subclass of int, so `true` must be rejected explicitly
    if isinstance(val, int) and not isinstance(val, bool) and val >= 0:
        return val
    return DEFAULT_STALE_AFTER


def _commit_exists(repo: Path, rev: str) -> bool:
    """True if `rev` names a commit here. Any git failure other than "no such commit" raises.

    `rev-parse --verify --quiet` exits 1 without output for an unknown revision; a corrupt
    object database, a lock or permission problem exits otherwise (usually 128) with a message.
    """
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"],
                       cwd=repo, capture_output=True, text=True, check=False)
    if r.returncode == 0:
        return True
    if r.returncode == 1 and not r.stderr.strip():
        return False
    raise RuntimeError(f"git rev-parse --verify {rev} failed: {r.stderr.strip()}")


def _shallow_roots(repo: Path, shallow_path: str) -> set[str]:
    f = (repo / shallow_path).resolve()
    if not f.is_file():
        return set()
    return {line.strip() for line in f.read_text(encoding="utf-8").splitlines() if line.strip()}


def _result(commits_behind: int | None, stale: bool, stale_after: int, summary: str) -> dict[str, Any]:
    return {"commits_behind": commits_behind, "stale": stale, "stale_after": stale_after, "summary": summary}


def _commits(n: int) -> str:
    return "1 commit" if n == 1 else f"{n} commits"


def contribute(ctx: Context) -> dict[str, Any]:
    """The freshness section for this decision (shape in the module docstring)."""
    stale_after = get_stale_after(ctx.cfg)
    if not ctx.base:
        return _result(None, False, stale_after, "recorded commit not found; age is unknown")

    repo = Path(ctx.cfg.root)
    # One probe: fails (not caught) when git is missing or the root is not a repository.
    is_shallow, shallow_path = git(repo, "rev-parse", "--is-shallow-repository", "--git-path", "shallow").split("\n")[:2]
    shallow = is_shallow.strip().lower() == "true"
    incomplete = "history is incomplete in a shallow clone; age is unknown"

    if not _commit_exists(repo, ctx.base):
        if shallow:          # may just be older than the fetched depth
            return _result(None, False, stale_after, incomplete)
        # A complete history without the recorded commit: it was squashed, amended or deleted
        # away, so none of the evidence matches the current history.
        return _result(None, True, stale_after,
                       f"recorded commit is no longer in this history (rewritten or deleted); {_RECORD}")

    left, right = (int(x) for x in git(repo, "rev-list", "--left-right", "--count", f"{ctx.base}...HEAD").split())

    if left > 0:
        # In a shallow clone the recorded commit and HEAD may only look unrelated because the
        # history between them was not fetched.
        if shallow:
            return _result(None, False, stale_after, incomplete)
        return _result(None, False, stale_after,
                       "current checkout is not based on the recorded commit; age is unknown")

    if right == 0:
        return _result(0, False, stale_after, "evidence was recorded at the current commit")

    if shallow:
        roots = _shallow_roots(repo, shallow_path.strip())
        # A shallow boundary inside <base>..HEAD may hide commits; then `right` is a lower bound.
        # Shallow clones are depth-limited, so this range is small.
        if roots and roots & set(git(repo, "rev-list", f"{ctx.base}..HEAD").split()):
            if right > stale_after:
                return _result(None, True, stale_after,
                               f"recorded evidence is at least {_commits(right)} old "
                               f"(stale, limit {stale_after}; shallow clone); {_RECORD}")
            return _result(None, False, stale_after, incomplete)

    if right > stale_after:
        return _result(right, True, stale_after,
                       f"recorded evidence is {_commits(right)} old (stale, limit {stale_after}); {_RECORD}")
    return _result(right, False, stale_after, f"recorded evidence is {_commits(right)} old (not stale)")
