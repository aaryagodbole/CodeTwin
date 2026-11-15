"""Failure triage for one test file (see the package docstring)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..evidence import diff as diffmod
from ..graph.impact import file_deps

WORKING_TREE = "working-tree"


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return r.stdout if r.returncode == 0 else ""


def _resolve(root: Path, sha: str) -> str | None:
    if sha == WORKING_TREE:
        return None
    out = _git(root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}").strip()
    return out or None


def _window(root: Path, good: str | None, bad: str | None) -> list[str]:
    """Commits after `good` up to and including `bad` (oldest first). A working-tree failure ends at HEAD."""
    head = bad or _git(root, "rev-parse", "HEAD").strip()
    if not head:
        return []
    rng = f"{good}..{head}" if good else head
    commits = _git(root, "rev-list", "--reverse", "--max-count=200", rng).split()
    return commits


def _suspects(root: Path, commits: list[str], test: str, covered: dict[str, list[int]], deps: set[str]) -> list[dict]:
    out: list[dict] = []
    for c in commits:
        parent = _git(root, "rev-parse", "--verify", "--quiet", f"{c}^").strip()
        if not parent:
            continue
        changed = diffmod.changed_lines(root, parent, c, ("",))
        score: float = 0.0
        why: list[str] = []
        for f, d in changed.items():
            lines = set(covered.get(f, []))
            if f == test:
                score += 3
                why.append(f"changes the test file {f}")
            elif lines and lines & set(d.old):
                score += 5
                why.append(f"changes {len(lines & set(d.old))} lines of {f} that the test executed")
            elif f in covered:
                score += 2
                why.append(f"changes {f}, which the test executed")
            elif f in deps:
                score += 1
                why.append(f"changes {f}, which the test imports")
        subject = _git(root, "log", "-1", "--format=%h %s", c).strip()
        author_date = _git(root, "log", "-1", "--format=%cI", c).strip()
        out.append({"commit": c, "title": subject, "date": author_date, "score": score,
                    "reasons": why or [f"changes {len(changed)} files, none of which the test executed or imports"],
                    "files": sorted(changed)})
    out.sort(key=lambda s: (-float(s["score"]), str(s["date"])))
    return out


def triage(root: Path, store, facts: dict, test: str, rerun: list[bool] | None = None) -> dict:
    """Triage of `test` from the stored outcomes; `rerun` is the pass/fail list of fresh reruns, if any."""
    every = store.outcomes(test)
    unknowns: list[str] = []
    timeline = [{"sha": h["sha"], "recorded": h["recorded"], "passed": h["passed"], "source": h["source"],
                 "failing_cases": h["failing_cases"]} for h in every]
    # the status and the failure window come from recorded runs and CI; reruns (`why --rerun`) are evidence of
    # flakiness, passed in `rerun`, and must not replace the failure being explained
    hist = [h for h in every if h["source"] != "rerun"] or every
    if not hist:
        return {"test": test, "status": "unknown", "timeline": [], "window": [], "suspects": [],
                "hypothesis": "unknown", "evidence": [],
                "unknowns": [f"no recorded outcome of {test}: run `codetwin record`, or import CI reports with "
                             "`codetwin outcomes import`"], "summary": f"{test}: no outcomes recorded"}
    last = hist[-1]
    status = "passing" if last["passed"] else "failing"
    evidence: list[str] = []

    # flakiness: different outcomes on the same commit, or mixed reruns
    by_sha: dict[str, set[bool]] = {}
    for h in hist:
        by_sha.setdefault(h["sha"], set()).add(h["passed"])
    flaky_shas = [s for s, v in by_sha.items() if len(v) > 1 and s != WORKING_TREE]
    if flaky_shas:
        evidence.append(f"different outcomes on the same commit ({', '.join(s[:10] for s in flaky_shas[:3])})")
    if rerun:
        p = sum(rerun)
        evidence.append(f"reran {len(rerun)} times: {p} passed, {len(rerun) - p} failed")
    flips = sum(1 for a, b in zip(hist, hist[1:], strict=False) if a["passed"] != b["passed"])

    # current failure: first failing outcome after the last pass
    window: list[str] = []
    suspects: list[dict] = []
    first_bad = good = None
    if status == "failing":
        i = len(hist) - 1
        while i > 0 and not hist[i - 1]["passed"]:
            i -= 1
        first_bad = hist[i]
        good = hist[i - 1] if i > 0 else None
        gsha = _resolve(root, good["sha"]) if good else None
        bsha = _resolve(root, first_bad["sha"])
        if good is None:
            unknowns.append(f"{test} has failed since its first recorded outcome: no passing run to compare with")
        window = _window(root, gsha, bsha) if (gsha or good is None) else []
        if good and not gsha:
            unknowns.append(f"last passing run was on {good['sha']}, which is not a commit; window starts at HEAD")
        if bsha is None:
            window = window + [WORKING_TREE]
        run = store.get_run(gsha) if gsha else None
        covered = (run.covered.get(test, {}) if run else {})
        if run is None:
            unknowns.append("no recorded coverage of the last passing commit: suspects ranked by files only")
        deps = set(file_deps(facts).get(test, []))
        dyn = sorted(f for f in {test, *deps} if f in facts and facts[f].dynamic)
        if dyn:
            unknowns.append(f"{', '.join(dyn[:3])} use dynamic imports or calls (or could not be parsed): commits "
                            "changing code the test reaches that way are ranked by files only")
        suspects = _suspects(root, [c for c in window if c != WORKING_TREE], test, covered, deps)
        if WORKING_TREE in window:
            changed = diffmod.changed_lines(root, "HEAD", None, ("",))
            if changed:
                hits = [f for f in changed if f in covered or f == test or f in deps]
                suspects.insert(0, {"commit": WORKING_TREE, "title": "uncommitted changes", "date": "",
                                    "score": 5 if hits else 0, "reasons": [f"changes {f}" for f in hits] or
                                    ["uncommitted changes outside what the test exercises"], "files": sorted(changed)})
                suspects.sort(key=lambda s: -s["score"])

    # hypothesis
    if rerun and 0 < sum(rerun) < len(rerun) or flaky_shas:
        hypothesis = "flaky"
    elif status == "passing":
        hypothesis = "passing"
        if flips >= 2:
            evidence.append(f"outcome changed {flips} times in {len(hist)} recorded runs")
    elif suspects and any("test file" in r for r in suspects[0]["reasons"]) and suspects[0]["score"] >= 3 \
            and not any("lines of" in r for s in suspects for r in s["reasons"]):
        hypothesis = "test-changed"
        evidence.append(f"{suspects[0]['title']} changed the test itself")
    elif suspects and suspects[0]["score"] >= 2:
        hypothesis = "regression"
        evidence.append(f"top suspect {suspects[0]['title'] or suspects[0]['commit']}: {suspects[0]['reasons'][0]}")
    else:
        hypothesis = "environment-or-unknown"
        evidence.append("no commit in the window changed code the test executed, imports or is")
    if rerun and sum(rerun) == len(rerun) and status == "failing":
        evidence.append("every rerun passed now: the failure did not reproduce")
        hypothesis = "flaky" if hypothesis != "regression" else "regression-not-reproduced"

    summary = f"{test}: {status}"
    if status == "failing":
        summary += (f" since {first_bad['sha'][:10]}" if first_bad else "") + \
            f"; {len(suspects)} suspect commits; likely cause: {hypothesis}"
    return {"test": test, "status": status, "timeline": timeline,
            "first_failing": first_bad["sha"] if first_bad else None, "last_passing": good["sha"] if good else None,
            "window": window, "suspects": suspects[:10], "hypothesis": hypothesis, "evidence": evidence,
            "unknowns": unknowns, "summary": summary}
