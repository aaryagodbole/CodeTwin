"""Section: how many commits old the recorded evidence is (freshness).

CodeTwin compares a code change with a test run recorded earlier by `codetwin record`.
If many commits have been made since that recording, the recorded evidence is out of date
and test selection is less trustworthy. This report section counts how many commits have
been made between the recorded commit and HEAD, and alerts the user when the evidence is stale.
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
    """Read the freshness limit `stale_after` from .codetwin.toml.

    Looks for `[freshness] stale_after = <int>`. If the setting is missing,
    not an integer, or negative, falls back to the default of 20.
    """
    # If no configuration object is available, return the default
    if cfg is None:
        return DEFAULT_STALE_AFTER

    # Read the [freshness] table from .codetwin.toml (empty dict if section is missing)
    sec = cfg.section("freshness") if hasattr(cfg, "section") else {}
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

    Counts commits between the recorded commit (ctx.base) and HEAD.
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

    # Determine repository path
    repo = Path(ctx.cfg.root) if (ctx.cfg and getattr(ctx.cfg, "root", None)) else Path(".")

    # 3. Count commits between ctx.base and HEAD using `git rev-list --count <base>..HEAD`
    try:
        out = git(repo, "rev-list", "--count", f"{ctx.base}..HEAD")
        commits_behind = int(out.strip())
    except Exception:
        # If git fails (e.g. the commit was deleted, squashed, or does not exist),
        # return a sensible result without crashing
        return {
            "commits_behind": None,
            "stale": False,
            "stale_after": stale_after,
            "summary": "recorded commit not found; age is unknown",
        }

    # 4. A recording is stale when the commit count is greater than the limit
    stale = commits_behind > stale_after

    # 5. Formulate a one-line summary for the three cases
    if commits_behind == 0:
        summary = "evidence was recorded at the current commit"
    elif not stale:
        commits_word = "1 commit" if commits_behind == 1 else f"{commits_behind} commits"
        summary = f"recorded evidence is {commits_word} old (not stale)"
    else:
        commits_word = "1 commit" if commits_behind == 1 else f"{commits_behind} commits"
        summary = f"recorded evidence is {commits_word} old (stale, limit {stale_after}); run `codetwin record`"

    # 6. Return JSON-serializable dictionary
    return {
        "commits_behind": commits_behind,
        "stale": stale,
        "stale_after": stale_after,
        "summary": summary,
    }
