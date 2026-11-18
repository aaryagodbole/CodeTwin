"""`codetwin review`: evidence-based pull-request review (summary comment, inline comments, SARIF).

Reuses a decision from `codetwin select --json` when given `--decision`, so CI does not select twice and the
learning history gets one decision per change. Without it, it selects first (same as `codetwin select`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ._util import engine, print_json

if TYPE_CHECKING:
    from ..engine import Engine

NAME, HELP, ORDER = "review", "review the change like a reviewer: findings at file/line, PR comment, SARIF", 32
FORMATS = ("markdown", "json", "sarif", "github")


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--base", help="recorded commit to compare with (default: latest recorded)")
    p.add_argument("--decision", help="JSON from `codetwin select --json` to review (default: select now)")
    p.add_argument("--format", choices=FORMATS, default="markdown", help="output format (default: markdown)")
    p.add_argument("-o", "--output", help="write to this file instead of standard output")
    p.add_argument("--llm", action="store_true", help="add advisory comments from a language model ([llm] settings)")
    p.add_argument("--only", help="comma-separated analyzers to run (default: all evidence analyzers)")
    p.add_argument("--skip", help="comma-separated analyzers to skip")
    p.add_argument("--post-github", action="store_true",
                   help="post the summary and inline comments to the pull request (GitHub Actions; needs GITHUB_TOKEN)")
    p.add_argument("--fail-on-blocking", action="store_true",
                   help="exit 1 when the review is blocking (abstention or a high/critical evidence finding)")


def _split(s: str | None) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


def load_decision(path: str) -> dict:
    """A decision from `codetwin select --json`, checked before it is trusted (it is a file from outside)."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"--decision {path}: cannot read JSON ({e})") from None
    problems = []
    if not isinstance(d, dict):
        raise SystemExit(f"--decision {path}: expected a JSON object from `codetwin select --json`")
    if d.get("decision") not in ("proceed", "abstain"):
        problems.append("'decision' must be \"proceed\" or \"abstain\"")
    rr = d.get("residual_risk")
    if isinstance(rr, bool) or not isinstance(rr, (int, float)) or not 0 <= rr <= 1:
        problems.append("'residual_risk' must be a number between 0 and 1")
    if not isinstance(d.get("selected"), list) or not all(isinstance(t, str) for t in d["selected"]):
        problems.append("'selected' must be a list of test names")
    if not isinstance(d.get("reasons", []), list) or not isinstance(d.get("extras", {}), dict):
        problems.append("'reasons' must be a list and 'extras' an object")
    if problems:
        raise SystemExit(f"--decision {path} is not a `codetwin select --json` output: " + "; ".join(problems))
    return d


def check_decision_base(decision: dict, base: str | None, user: str) -> dict:
    """Refuse a decision computed against another recorded commit; return its saved `changed_files` extras."""
    saved = (decision.get("extras") or {}).get("changed_files")
    saved = saved if isinstance(saved, dict) else {}
    made_for = saved.get("base")
    if isinstance(made_for, str) and made_for and base and made_for != base:
        raise SystemExit(f"--decision was computed against {made_for[:12]}, but {user} is {base[:12]}; "
                         f"run `codetwin select --json` again or pass --base {made_for}")
    return saved


def check_decision_files(eng: Engine, saved: dict, diff: dict) -> None:
    """Refuse a decision whose changed source files differ from `diff`, the change against its base now."""
    if isinstance(saved.get("files"), dict):
        now = {f: len(d.new) for f, d in diff.items() if eng.is_source(f)}
        if now != saved["files"]:
            raise SystemExit("--decision does not describe the current change (the changed source files differ "
                             "since it was computed); run `codetwin select --json` again")


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_ESC = {"a": "\a", "b": "\b", "t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r", '"': '"', "\\": "\\"}


def git_path(raw: str) -> str:
    """A path as git prints it in a diff header: plain, or C-quoted with octal UTF-8 escapes."""
    if not (raw.startswith('"') and raw.endswith('"')):
        return raw
    body, out, i = raw[1:-1], bytearray(), 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            octal = body[i + 1:i + 4]
            if len(octal) == 3 and all(c in "01234567" for c in octal):
                out.append(int(octal, 8))
                i += 4
                continue
            out += _ESC.get(nxt, nxt).encode()
            i += 2
            continue
        out += ch.encode()
        i += 1
    return out.decode("utf-8", errors="replace")


def commentable(patch: str) -> dict[str, set[int]]:
    """New-file lines that GitHub accepts an inline comment on: every line inside a hunk of the diff.

    File headers are read only between `diff --git` and the first hunk, so an added line whose text starts
    with `++` (shown as `+++ ...`) is never taken for a header."""
    out: dict[str, set[int]] = {}
    path: str | None = None
    in_header = False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            in_header, path = True, None
        elif in_header and line.startswith("+++ "):
            target = git_path(line[4:])
            path = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
        elif m := _HUNK.match(line):
            in_header = False
            if path:
                start, count = int(m[1]), int(m[2]) if m[2] is not None else 1
                out.setdefault(path, set()).update(range(start, start + count))
    return out


def _pull_request_base(root: Path) -> str | None:
    """The base commit of the pull request in a GitHub `pull_request` workflow, if it is in the local history."""
    import os

    from ..evidence.diff import git

    path = os.environ.get("GITHUB_EVENT_PATH")
    try:
        event = json.loads(Path(path).read_text(encoding="utf-8")) if path else None
    except (OSError, ValueError):
        return None
    pr = event.get("pull_request") if isinstance(event, dict) else None
    base = pr.get("base") if isinstance(pr, dict) else None
    sha = base.get("sha") if isinstance(base, dict) else None
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):   # SHA-1 or SHA-256
        return None
    # The commit must be here and share history with HEAD (a shallow checkout may have one without the other).
    try:
        git(root, "merge-base", sha, "HEAD")
    except RuntimeError:
        return None
    return sha


def run(args: argparse.Namespace) -> int:
    from ..evidence.diff import git
    from ..kg import from_engine
    from ..review import ReviewContext, select_analyzers
    from ..review import run as run_review
    from ..review.render import github, markdown, sarif

    with engine(args) as eng:
        sec = eng.cfg.section("review")
        sec = sec if isinstance(sec, dict) else {}
        given = args.decision is not None
        decision = load_decision(args.decision) if given else eng.select(args.base).to_dict()
        base = args.base or eng.store.latest_run_sha()
        saved = check_decision_base(decision, base, "the commit this review compares with")
        diff = eng.changed(base) if base else {}
        if given:
            check_decision_files(eng, saved, diff)
        changed = {f: sorted(d.new) for f, d in diff.items() if d.status != "D"}
        changed_old = {d.old_path or f: sorted(d.old) for f, d in diff.items()}
        try:
            kg = from_engine(eng, base)
        except RuntimeError:
            kg = None
        covering: dict[str, list[str]] = {}
        if kg is not None:
            from ..kg.schema import EdgeKind, NodeKind, node_id
            for f in changed:
                tests = kg.neighbours(node_id(NodeKind.FILE, f), EdgeKind.COVERS, incoming=True)
                covering[f] = [kg.g.nodes[t]["key"] for t in tests]
        llm = None
        only = _split(args.only) or sec.get("analyzers") or None
        skip = _split(args.skip) or list(sec.get("skip", []))
        if args.llm:
            from ..llm import client_from_config
            llm = client_from_config(eng.cfg)
            only = sorted({*(only or [m.NAME for m in select_analyzers()]), "llm_review"})
        patch = git(eng.root, "diff", "--unified=3", base, "--") if base else ""
        # GitHub accepts inline comments only on lines of the pull request's own diff. The recorded base can be an
        # older commit than the PR's base, so use the PR's base commit when the workflow event provides it.
        in_pr = patch
        if args.post_github or args.format == "github":     # only inline comments need the pull request's diff
            pr_base = _pull_request_base(eng.root)
            if pr_base and pr_base != base:
                try:
                    in_pr = git(eng.root, "diff", "--unified=3", f"{pr_base}...HEAD", "--")
                except RuntimeError:
                    in_pr = patch                           # keep the review working on the recorded diff
        ctx = ReviewContext(root=eng.root, decision=decision, changed=changed, cfg=eng.cfg, graph=kg, llm=llm,
                            options={"patch": patch if llm else "", "changed_old": changed_old, "covering": covering},
                            commentable=commentable(in_pr))
        review = run_review(ctx, select_analyzers(only, skip))

    if args.format == "json":
        out: object = review.to_dict()
    elif args.format == "sarif":
        out = sarif(review)
    elif args.format == "github":
        out = github(review, ctx.in_diff)
    else:
        out = markdown(review)
    if args.output:
        Path(args.output).write_text(out if isinstance(out, str) else json.dumps(out, indent=1))
    elif isinstance(out, str):
        sys.stdout.write(out + "\n")
    else:
        print_json(out)
    if args.post_github:
        from ..review.github_api import PostError, post_from_env
        try:
            res = post_from_env(review, ctx.in_diff)
            print(f"posted to the pull request: summary {res['summary']}, {res['inline']} new inline comments",
                  file=sys.stderr)
        except (PostError, RuntimeError) as e:
            # e.g. a fork or Dependabot pull request, where the token is read-only. The review output (SARIF,
            # JSON, Markdown) is already written; a failed post must not stop the selected tests from running.
            print(f"::warning::CodeTwin could not post the review to the pull request: {e}", file=sys.stderr)
    return 1 if args.fail_on_blocking and review.blocking else 0
