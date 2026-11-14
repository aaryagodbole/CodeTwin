"""Run every CodeTwin feature on one sample project of examples/ and check the results.

Usage: python scripts/language_smoke.py examples/<language>

The sample is copied to a temporary git repository; then:
  init (language detected) -> record (every test file has coverage, none fails) -> a behaviour change:
  select (changed file reported, covering test selected), impact, graph, weakcheck, run, explain, learn ->
  a comment-only change: select reports a semantic no-op.
`example.json` in the sample says which file to edit and which test covers it; `setup` lists commands that
prepare the sample (install dependencies), run before the first commit.
Exits non-zero with a message on the first failed check. Used by the `languages` CI job.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def sh(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"FAILED: {' '.join(cmd)}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r


def codetwin(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return sh([sys.executable, "-m", "codetwin.cli", *args], cwd, check)


def expect(cond: bool, what: str, detail: object = "") -> None:
    if not cond:
        sys.exit(f"FAILED: {what}\n{json.dumps(detail, indent=1, default=str)[:4000] if detail != '' else ''}")
    print(f"  ok  {what}")


def edit(repo: Path, file: str, old: str, new: str) -> None:
    p = repo / file
    text = p.read_text()
    if old not in text:
        sys.exit(f"FAILED: example.json edit {old!r} not found in {file}")
    p.write_text(text.replace(old, new, 1))


def main(sample: Path) -> None:
    spec = json.loads((sample / "example.json").read_text())
    static_only = spec.get("static_only", False)
    print(f"== {sample.name} ({spec.get('language') or ' + '.join(spec['languages'])})")
    with tempfile.TemporaryDirectory(prefix="codetwin-smoke-") as tmp:
        repo = Path(tmp) / sample.name
        shutil.copytree(sample, repo, ignore=shutil.ignore_patterns("example.json", "node_modules", "target", "vendor"))
        setup = spec.get("setup", [])
        for cmd in ([setup] if setup and isinstance(setup[0], str) else setup):
            sh(cmd, repo)
        (repo / ".gitignore").write_text("node_modules/\nvendor/\ntarget/\nbin/\nobj/\n.codetwin/\n")
        env_git = ["-c", "user.email=ci@example.com", "-c", "user.name=ci"]
        sh(["git", "init", "-q"], repo)
        sh(["git", "add", "-A"], repo)
        sh(["git", *env_git, "commit", "-qm", "sample"], repo)

        if not spec.get("keep_config"):
            codetwin(repo, "init")
        cfg = (repo / ".codetwin.toml").read_text()
        if "languages" in spec:
            want = "languages = [" + ", ".join(f'"{x}"' for x in spec["languages"]) + "]"
            expect(want in cfg, f"init detects every language: {', '.join(spec['languages'])}", cfg)
        else:
            expect(f'language = "{spec["language"]}"' in cfg, f"init detects {spec['language']}", cfg)

        codetwin(repo, "record")
        from codetwin.engine import Engine
        with Engine(repo) as eng:
            run = eng.store.get_run(eng.store.latest_run_sha())
            tests = eng.tests_now()
        expect(len(tests) >= 2, "test files found", tests)
        expect(not run.failing, "no test fails on the recorded commit", run.failing)
        targets = [spec] + ([spec["also"]] if "also" in spec else [])
        if static_only:
            expect(not run.covered and run.returncode == "no-runner", "no runner: static evidence only, nothing run",
                   run.returncode)
        for tg in targets:
            if not static_only:
                expect(tg["covering_test"] in run.covered and tg["file"] in run.covered[tg["covering_test"]],
                       f"per-test coverage reaches {tg['file']}", run.covered)

        for tg in targets:
            edit(repo, tg["file"], *tg["edit"])
        d = json.loads(codetwin(repo, "select", "--json").stdout)
        expect(d["decision"] in ("proceed", "abstain"), "select decides", d)
        for tg in targets:
            expect(tg["file"] in d["extras"]["changed_files"]["files"], f"changed file reported: {tg['file']}",
                   d["extras"])
            expect(tg["covering_test"] in d["selected"], f"the covering test is selected: {tg['covering_test']}",
                   d["selected"])
        if static_only:
            expect(d["decision"] == "abstain" and any("no test runner" in r for r in d["reasons"]),
                   "without a runner the decision abstains and says why", d["reasons"])
        expect(d["extras"]["semantic_noop"]["kind"] == "semantic", "behaviour change is not a no-op", d["extras"])
        expect(not any("error" in v for v in d["extras"].values() if isinstance(v, dict)), "every report section works",
               d["extras"])

        for tg in targets:
            imp = json.loads(codetwin(repo, "impact", tg["file"], "--json").stdout)
            expect(tg["covering_test"] in imp["tests"], f"impact finds the covering test of {tg['file']}", imp)
            g = json.loads(codetwin(repo, "graph", tg["file"], "--json").stdout)
            expect(g["counts"]["tests"] >= 1 and len(g["nodes"]) >= 2, f"graph of {tg['file']} has users and tests", g)

        w = json.loads(codetwin(repo, "weakcheck", "--json").stdout)
        statuses = {f["status"] for f in w["functions"]}
        ok_status = {"checked", "unchecked", "untested", "error"} if static_only else {"checked", "unchecked"}
        expect(bool(w["functions"]) and statuses <= ok_status, f"weakcheck runs ({', '.join(sorted(statuses))})", w)

        expect("decision" in json.loads(codetwin(repo, "explain").stdout), "explain")
        if static_only:
            r = codetwin(repo, "run", spec["covering_test"], check=False)
            expect(r.returncode != 0 and "test_command" in r.stderr, "run explains that no runner is configured",
                   r.stderr)
            r = codetwin(repo, "learn", check=False)
            expect(r.returncode != 0 and "no test runner" in r.stderr, "learn refuses to guess without a runner",
                   r.stderr)
        else:
            for tg in targets:
                codetwin(repo, "run", tg["covering_test"])
            print("  ok  run executes tests with the project's runner")
            codetwin(repo, "learn")                   # full run, ground truth, calibration update
            print("  ok  learn labels the decision and updates the calibration")

        for tg in targets:
            sh(["git", "checkout", "-q", "--", tg["file"]], repo)
        edit(repo, spec["file"], *spec["noop"])
        d = json.loads(codetwin(repo, "select", "--json").stdout)
        expect(d["extras"]["semantic_noop"]["kind"] == "noop", "comment-only change is a semantic no-op",
               d["extras"]["semantic_noop"])
        if "annotation" in spec:
            sh(["git", "checkout", "-q", "--", spec["file"]], repo)
            edit(repo, spec["file"], *spec["annotation"])
            d = json.loads(codetwin(repo, "select", "--json").stdout)
            expect(d["extras"]["semantic_noop"]["kind"] == "annotation", "type-only change is annotation-only",
                   d["extras"]["semantic_noop"])
    print(f"== {sample.name}: all checks passed")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    main(Path(sys.argv[1]).resolve())
