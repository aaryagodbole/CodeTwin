"""Run the test suite once with per-test coverage (coverage.py dynamic contexts)."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path

from .model import TestRun


def _junit_file(tc, repo: Path) -> str:
    f = tc.get("file")
    if not f:
        parts = tc.get("classname", "").split(".")
        f = "/".join(parts)
        for k in range(len(parts), 0, -1):
            cand = "/".join(parts[:k]) + ".py"
            if (repo / cand).exists():
                f = cand
                break
    return f.replace(os.sep, "/")


def run_suite(repo: str | Path, sha: str, tests_dir: str, packages: list[str], src_root: str = ".",
              tests: list[str] | None = None, timeout: int = 3600, rootdir: bool = False) -> TestRun:
    """Run pytest on `tests` (default: the whole tests_dir) and record per-test-file coverage."""
    repo = Path(repo).resolve()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        junit, rc_file = tmp / "junit.xml", tmp / "coveragerc"
        rc_file.write_text("[run]\nbranch = False\n")
        env = dict(os.environ, COVERAGE_CORE="ctrace", COVERAGE_FILE=str(tmp / ".coverage"))
        # src_root may list several import roots (os.pathsep-separated) for Python inside a larger repository
        roots = os.pathsep.join(str(repo / s) for s in src_root.split(os.pathsep))
        env["PYTHONPATH"] = roots + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        cmd = [sys.executable, "-m", "pytest", *(tests or [tests_dir]), "-q", "-p", "no:cacheprovider",
               "-o", "junit_family=xunit1", f"--cov-config={rc_file}", "--cov-context=test", "--cov-report=",
               f"--junitxml={junit}", *[f"--cov={p}" for p in packages or [str(repo / s) for s in src_root.split(os.pathsep)]],
               # Python inside a larger repository: test ids relative to the repository root, not to the
               # nearest pyproject.toml of the Python part
               *([f"--rootdir={repo}"] if rootdir else [])]
        t0 = time.time()
        rc: int | str
        try:
            rc = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True, timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
        if rc in (2, 3, 4):              # pytest: interrupted (e.g. a collection error), internal error, usage error
            rc = f"interrupted:{rc}"
        run = TestRun(sha=sha, returncode=rc)
        if junit.exists():
            # junit.xml is written by our own pytest run in a private temp dir, not external input
            for tc in ET.parse(junit).getroot().iter("testcase"):  # noqa: S314
                f = _junit_file(tc, repo)
                run.durations[f] = run.durations.get(f, 0.0) + float(tc.get("time", 0) or 0)
                if any(ch.tag in ("failure", "error") for ch in tc):
                    run.failing.append(f"{f}::{tc.get('classname', '')}::{tc.get('name', '')}")
        covfile = tmp / ".coverage"
        if covfile.exists():
            from coverage.numbits import numbits_to_nums
            imports: dict[str, set[int]] = {}
            covered: dict[str, dict[str, set[int]]] = {}
            with closing(sqlite3.connect(covfile)) as con:
                ctx = dict(con.execute("select id, context from context"))
                files = dict(con.execute("select id, path from file"))
                for fid, cid, bits in con.execute("select file_id, context_id, numbits from line_bits"):
                    src = os.path.relpath(files[fid], repo).replace(os.sep, "/")
                    c = ctx.get(cid, "")
                    lines = numbits_to_nums(bits)
                    if "::" not in c:          # executed outside any test: import time
                        imports.setdefault(src, set()).update(lines)
                        continue
                    test = c.split("::")[0].replace(os.sep, "/")
                    covered.setdefault(test, {}).setdefault(src, set()).update(lines)
            run.import_lines = {f: sorted(v) for f, v in imports.items()}
            run.covered = {t: {f: sorted(v) for f, v in fs.items()} for t, fs in covered.items()}
        run.wall = time.time() - t0
        return run
