"""Section: how many commits old the recorded evidence is (freshness).

CodeTwin compares a code change with a test run recorded earlier by `codetwin record`.
If many commits have been made since that recording, the recorded evidence is out of date
and test selection is less trustworthy. This report section counts every commit reachable
from HEAD but not from the recorded commit, including commits brought in by merges, and
alerts the user when the evidence is stale.

Merged commits count on purpose (no `--first-parent`): evidence goes stale because the code
changed since the recording, and commits brought in by a merge change the code just as local
commits do. Teams that merge often can raise `[freshness] stale_after`.

Error handling: only "the recorded commit is not in this checkout" is an expected result
(`commits_behind = None`). Git missing from PATH, a root that is not a repository and
unparsable git output are real failures and are not caught here, so `report.build()` shows
them as a broken section.
"""
from __future__ import annotations

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


def get_stale_after(cfg: Any) -> int:
    """Read the freshness limit `stale_after` from [freshness] in .codetwin.toml.

    Looks for `[freshness] stale_after = <int>`. If missing, not an integer,
    or negative, falls back to the default of 20. A limit of 0 is valid (stale after 1 commit).
    """
    # Read the [freshness] section (Config.section always returns dict or list)
    sec = cfg.section("freshness")
    if not isinstance(sec, dict):
        return DEFAULT_STALE_AFTER

    val = sec.get("stale_after")

    # In Python, bool is a subclass of int (isinstance(True, int) is True).
    # We must explicitly verify that val is an int and NOT a bool, and is >= 0.
    if isinstance(val, int) and not isinstance(val, bool) and val >= 0:
        return val

    # Fall back to default if missing, invalid type, or negative
    return DEFAULT_STALE_AFTER


def contribute(ctx: Context) -> dict[str, Any]:
    """Contribute the freshness report section to the current decision.

    Counts commits between the recorded commit (ctx.base) and HEAD using symmetric difference.
    Returns a dictionary with:
      - commits_behind: number of commits between recorded commit and HEAD (None if unknown)
      - stale: True if commits_behind > stale_after, otherwise False
      - stale_after: the configured threshold (default 20)
      - summary: a human-readable one-line description
    """
    # 1. Read the stale_after threshold from project configuration
    stale_after = get_stale_after(ctx.cfg)

    # 2. Check if the recorded base commit exists
    if not ctx.base:
        return {
            "commits_behind": None,
            "stale": False,
            "stale_after": stale_after,
            "summary": "recorded commit not found; age is unknown",
        }

    # Determine repository path directly from config
    repo = Path(ctx.cfg.root)

    # 3. Make sure git works and the root is a repository. Not caught on purpose:
    # a missing git binary or a non-repository root is a real failure and must reach
    # report.build() as a visible error, not become an "unknown age".
    git(repo, "rev-parse", "--git-dir")

    # The only expected failure: the recorded commit is not in this checkout
    # (deleted, squashed, or absent from a shallow clone).
    try:
        git(repo, "rev-parse", "--verify", "--quiet", f"{ctx.base}^{{commit}}")
    except RuntimeError:
        return {
            "commits_behind": None,
            "stale": False,
            "stale_after": stale_after,
            "summary": "recorded commit is not in this checkout; age is unknown",
        }

    # Count commits with `git rev-list --left-right --count <base>...HEAD`.
    # left = commits only in base; right = commits only in HEAD.
    # Not caught: the commit exists, so a failure here is a real error.
    out = git(repo, "rev-list", "--left-right", "--count", f"{ctx.base}...HEAD")
    left, right = (int(x) for x in out.split())

    # 4. If left > 0, base is not an ancestor of HEAD (e.g. HEAD is older, on a different branch, or disconnected)
    if left > 0:
        return {
            "commits_behind": None,
            "stale": False,
            "stale_after": stale_after,
            "summary": "current checkout is not based on the recorded commit; age is unknown",
        }

    # 5. Base equals HEAD: evidence was recorded at the current commit
    if right == 0:
        return {
            "commits_behind": 0,
            "stale": False,
            "stale_after": stale_after,
            "summary": "evidence was recorded at the current commit",
        }

    # 6. Base is an ancestor of HEAD (left == 0 and right > 0).
    # Check if the repository is shallow and whether shallow boundary commits truncate the counted range.
    # Errors here are not caught: they are real failures, not an unknown age.
    is_shallow = git(repo, "rev-parse", "--is-shallow-repository").strip().lower() == "true"
    if is_shallow:
        shallow_rel = git(repo, "rev-parse", "--git-path", "shallow").strip()
        shallow_file = (repo / shallow_rel).resolve()
        if shallow_file.is_file():
            shallow_roots = {
                line.strip() for line in shallow_file.read_text(encoding="utf-8").splitlines() if line.strip()
            }
            if shallow_roots:
                # If any shallow boundary commit lies inside the counted range <base>..HEAD, count may be incomplete
                range_commits = set(git(repo, "rev-list", f"{ctx.base}..HEAD").splitlines())
                if shallow_roots & range_commits:
                    return {
                        "commits_behind": None,
                        "stale": False,
                        "stale_after": stale_after,
                        "summary": "history is incomplete in a shallow clone; age is unknown",
                    }

    # 7. Complete range: commits_behind is right
    commits_behind = right
    stale = commits_behind > stale_after

    commits_word = "1 commit" if commits_behind == 1 else f"{commits_behind} commits"
    if not stale:
        summary = f"recorded evidence is {commits_word} old (not stale)"
    else:
        summary = f"recorded evidence is {commits_word} old (stale, limit {stale_after}); run `codetwin record`"

    return {
        "commits_behind": commits_behind,
        "stale": stale,
        "stale_after": stale_after,
        "summary": summary,
    }
