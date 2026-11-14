"""Runs INSIDE a Multi-SWE-bench container: records one pull request as a CodeTwin study change.

The image holds the repository at the PR's base commit in /home/<repo>, the fix in /home/fix.patch and the
tests of the PR in /home/test.patch. We record, in the layout of the Python study (pilot/collect.py):

  snap/<base>.json   static facts + per-test-file coverage run of the base commit
  snap/<new>.json    the same for base + test.patch + fix.patch, committed locally
  commits/<i>_<new>.json
      diff (changed lines per file), the test files that the PR adds or changes, which of them fail on the
      base commit with only the test patch applied (fail-on-base) and pass after the fix (f2p), timings.

Static facts and test runs come from CodeTwin's language adapters (codetwin.lang), so the same code serves
Go, JavaScript/TypeScript, Rust, Java and any other language with a runner preset. The test universe is
capped at --max-tests files (deterministic sample by PR number, always including the PR's own test files)
because every test file runs on its own with coverage, twice.

Usage (inside the container, after `pip install codetwin*.whl --no-deps` + tree-sitter):
    python3 mswe_inside.py --repo /home/cli --out /home/out --pr 1234 --index 7 --max-tests 80
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path


def sh(cmd, cwd, timeout=1800, check=False):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} -> {r.returncode}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def git(repo, *args, **kw):
    return sh(["git", "-c", "user.name=study", "-c", "user.email=study@example.com", *args], repo, **kw)


def patched_test_files(patch_text: str, adapter) -> list[str]:
    files = []
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            f = line[6:].strip()
            if adapter.is_test(f):
                files.append(f)
    return sorted(set(files))


def run_to_dict(run) -> dict:
    failing_files = {x.split("::", 1)[0] for x in run.failing}
    return {"returncode": str(run.returncode), "wall": str(run.wall), "durations": run.durations,
            "outcomes": {t: t not in failing_files for t in run.durations}, "failing": list(run.failing),
            "covered": run.covered, "import_lines": run.import_lines, "tail": ""}


def facts_to_dict(facts) -> dict:
    return {f: {"imports": v.imports, "dynamic": v.dynamic, "defs": v.defs, "dyn_lines": v.dyn_lines,
                "mod_lines": v.mod_lines, "deps": v.deps} for f, v in facts.items()}


def loc_of(repo: Path, files) -> dict:
    out = {}
    for f in files:
        try:
            out[f] = sum(1 for _ in (repo / f).open("rb"))
        except OSError:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--max-tests", type=int, default=80)
    ap.add_argument("--timeout", type=int, default=300, help="seconds per test file")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--language", default="auto")
    ap.add_argument("--runner", default="", help="JSON for the [runner] table (test_command etc.)")
    ap.add_argument("--patches", default="/home", help="folder with test.patch and fix.patch")
    args = ap.parse_args()

    from codetwin import lang
    from codetwin.config import Config
    from codetwin.evidence.diff import changed_lines

    repo, out = Path(args.repo).resolve(), Path(args.out)
    (out / "snap").mkdir(parents=True, exist_ok=True)
    (out / "commits").mkdir(parents=True, exist_ok=True)
    log = {"pr": args.pr, "steps": {}}
    t_all = time.time()

    git(repo, "reset", "--hard", "-q")
    git(repo, "clean", "-fdq", "-e", "node_modules", "-e", "target", "-e", "vendor")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    runner = json.loads(args.runner) if args.runner else {}
    runner.setdefault("workers", args.workers)
    runner.setdefault("timeout", args.timeout)
    cfg = Config(root=repo, language=args.language, source_dirs=["."], tests_dir=".", raw={"runner": runner})
    adapter = lang.get(cfg)
    log["language"] = adapter.describe()
    print(f"[inside] pr {args.pr}: {adapter.describe()}, base {base[:10]}", flush=True)

    # -------- test universe: deterministic sample + the PR's own test files
    test_patch = (Path(args.patches) / "test.patch").read_text(encoding="utf-8", errors="replace")
    fix_patch = (Path(args.patches) / "fix.patch").read_text(encoding="utf-8", errors="replace")
    pr_tests = patched_test_files(test_patch, adapter)
    all_tests = adapter.list_tests()
    rnd = random.Random(args.pr)
    pool = [t for t in all_tests if t not in pr_tests]
    rnd.shuffle(pool)
    universe = sorted(set(pool[: max(0, args.max_tests - len(pr_tests))]) | (set(pr_tests) & set(all_tests)))
    log["tests_total"], log["tests_used"], log["pr_tests"] = len(all_tests), len(universe), pr_tests
    print(f"[inside] {len(all_tests)} test files, using {len(universe)}; PR touches {len(pr_tests)}", flush=True)

    # -------- base snapshot
    t0 = time.time()
    facts_b = adapter.facts()
    run_b = adapter.run_suite(base, universe, timeout=args.timeout * len(universe) + 600)
    log["steps"]["base_run"] = round(time.time() - t0, 1)
    n_fail = len({x.split('::')[0] for x in run_b.failing})
    n_cov = sum(1 for t in run_b.covered.values() if t)
    print(f"[inside] base: {n_cov} files with coverage, {n_fail} failing, {log['steps']['base_run']}s", flush=True)
    (out / "snap" / f"{base}.json").write_text(json.dumps({
        "sha": base, "date": git(repo, "log", "-1", "--format=%cI").stdout.strip(), "subject": "base",
        "tests_present": all_tests, "static": facts_to_dict(facts_b), "loc": loc_of(repo, facts_b), "run": run_to_dict(run_b)}))

    # -------- fail-on-base: the PR's test files on the base code
    t0 = time.time()
    r = git(repo, "apply", "--whitespace=nowarn", str(Path(args.patches) / "test.patch"))
    fail_on_base: dict = {}
    if r.returncode == 0:
        new_pr_tests = patched_test_files(test_patch, adapter)
        res = adapter.run_tests(repo, new_pr_tests, args.timeout) if new_pr_tests else {}
        fail_on_base = {t: (None if v is None else (not v)) for t, v in res.items()}
    else:
        log["test_patch_error"] = r.stderr[-500:]
    log["steps"]["fail_on_base"] = round(time.time() - t0, 1)

    # -------- new version: base + test patch + fix patch, committed
    r2 = git(repo, "apply", "--whitespace=nowarn", str(Path(args.patches) / "fix.patch"))
    if r2.returncode != 0:
        log["fix_patch_error"] = r2.stderr[-500:]
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", f"PR {args.pr}: tests + fix")
    new = git(repo, "rev-parse", "HEAD").stdout.strip()
    diff = changed_lines(repo, base, new, adapter.extensions)
    t0 = time.time()
    facts_n = adapter.facts()
    new_tests = adapter.list_tests()
    universe_n = sorted(set(universe) | ({t for t in fail_on_base} & set(new_tests)))
    run_n = adapter.run_suite(new, universe_n, timeout=args.timeout * len(universe_n) + 600)
    log["steps"]["new_run"] = round(time.time() - t0, 1)
    print(f"[inside] new: {len({x.split('::')[0] for x in run_n.failing})} failing, {log['steps']['new_run']}s", flush=True)
    (out / "snap" / f"{new}.json").write_text(json.dumps({
        "sha": new, "date": git(repo, "log", "-1", "--format=%cI").stdout.strip(), "subject": f"PR {args.pr}",
        "tests_present": new_tests, "static": facts_to_dict(facts_n), "loc": loc_of(repo, facts_n), "run": run_to_dict(run_n)}))

    failing_new = {x.split("::", 1)[0] for x in run_n.failing}
    f2p = sorted(t for t, fob in fail_on_base.items() if fob is True and t not in failing_new)
    rec = {"index": args.index, "sha": new, "parent": base, "pr": args.pr,
           "date": git(repo, "log", "-1", "--format=%cI").stdout.strip(), "subject": f"PR {args.pr}",
           "diff": {f: asdict(d) for f, d in diff.items()},
           "pr_tests": sorted(fail_on_base), "fail_on_base": fail_on_base, "f2p": f2p,
           "namerts_gt": None, "mutants": [], "log": log}
    log["total"] = round(time.time() - t_all, 1)
    (out / "commits" / f"{args.index:03d}_{new[:10]}.json").write_text(json.dumps(rec))
    print(f"[inside] done in {log['total']}s; f2p files: {f2p}", flush=True)


if __name__ == "__main__":
    main()
