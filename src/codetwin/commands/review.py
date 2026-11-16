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

from ._util import engine, print_json

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
        d = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
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


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def commentable(patch: str) -> dict[str, set[int]]:
    """New-file lines that GitHub accepts an inline comment on: every line inside a hunk of the diff."""
    out: dict[str, set[int]] = {}
    path = None
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = None if line[4:] == "/dev/null" else line[6:] if line.startswith("+++ b/") else line[4:]
        elif path and (m := _HUNK.match(line)):
            start, count = int(m[1]), int(m[2]) if m[2] is not None else 1
            out.setdefault(path, set()).update(range(start, start + count))
    return out


def run(args: argparse.Namespace) -> int:
    from ..evidence.diff import git
    from ..kg import from_engine
    from ..review import ReviewContext, select_analyzers
    from ..review import run as run_review
    from ..review.render import github, markdown, sarif

    with engine(args) as eng:
        sec = eng.cfg.section("review")
        sec = sec if isinstance(sec, dict) else {}
        decision = load_decision(args.decision) if args.decision else eng.select(args.base).to_dict()
        base = args.base or eng.store.latest_run_sha()
        made_for = ((decision.get("extras") or {}).get("changed_files") or {}).get("base")
        if made_for and base and made_for != base:
            raise SystemExit(f"--decision was computed against {made_for[:12]}, but this review compares with "
                             f"{base[:12]}; run `codetwin select --json` again or pass --base {made_for[:12]}")
        diff = eng.changed(base) if base else {}
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
        ctx = ReviewContext(root=eng.root, decision=decision, changed=changed, cfg=eng.cfg, graph=kg, llm=llm,
                            options={"patch": patch if llm else "", "changed_old": changed_old, "covering": covering},
                            commentable=commentable(patch))
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
