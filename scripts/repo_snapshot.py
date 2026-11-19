"""Snapshot the dependency graph of a real repository for the hosted dashboard.

The hosted dashboard reads decisions, summary and calibration from CodeTwin Cloud (real uploads from CI). The cloud
never receives code-level data (ADR 0003), so the dependency graph and the per-file impact views come from this
snapshot instead: the answers of `/api/map` and `/api/graph` for one commit of a real repository, as JSON. They hold
file paths, link types and test ids only, never source text.

    python scripts/repo_snapshot.py                     # this repository at HEAD -> dashboard/public/snapshot/
    python scripts/repo_snapshot.py --repo ../web       # another repository
    python scripts/repo_snapshot.py --no-record         # static links only (does not run the test suite)

It clones the repository at HEAD into a temporary folder (the working copy is never touched), runs `codetwin
record` there (the full test suite with coverage, so runtime links are real) unless `--no-record`, then saves the
map and the graph of every file it links to. File names follow `demoName` in dashboard/src/lib/demo-path.mjs.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from demo_snapshot import graph_files, snapshot_name  # noqa: E402  (shared naming with the demo snapshot)

OUT = ROOT / "dashboard" / "public" / "snapshot"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _project(repo: Path) -> str:
    """owner/name from the origin remote (for the banner), else the folder name."""
    try:
        url = _git(repo, "remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        return repo.name
    tail = url.rstrip("/").removesuffix(".git").replace(":", "/").split("/")
    return "/".join(tail[-2:])


def capture(repo: Path, out: Path) -> list[str]:
    from fastapi.testclient import TestClient

    from codetwin.server.app import create_app

    client = TestClient(create_app(repo))
    answers: dict[str, Any] = {}

    def fetch(path: str, params: dict[str, str]) -> Any:
        name = snapshot_name(path, params)
        if name not in answers:
            r = client.get(f"/api{path}", params=params or None)
            r.raise_for_status()
            answers[name] = r.json()
        return answers[name]

    fetch("/health", {})
    todo = graph_files(fetch("/map", {}))
    seen: set[str] = set()
    while todo:
        f = todo.pop()
        if f not in seen:
            seen.add(f)
            todo += graph_files(fetch("/graph", {"file": f}))
    (out / "api").mkdir(parents=True, exist_ok=True)
    for name, data in answers.items():
        # one line per file: generated data, not for reading in a diff (.gitattributes marks it generated)
        text = json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        if str(repo) in text or tempfile.gettempdir() in text:
            raise SystemExit(f"refusing to publish a local path in {name}")
        (out / "api" / name).write_text(text + "\n", encoding="utf-8")
    return sorted(answers)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", type=Path, default=ROOT, help="git repository to snapshot (default: this one)")
    ap.add_argument("--out", type=Path, default=OUT, help=f"output folder (default: {OUT.relative_to(ROOT)})")
    ap.add_argument("--no-record", action="store_true", help="static links only: do not run the test suite")
    args = ap.parse_args()
    src = args.repo.resolve()
    sha = _git(src, "rev-parse", "HEAD")
    with tempfile.TemporaryDirectory(prefix="codetwin-snapshot-") as tmp:
        repo = Path(tmp) / src.name
        _git(Path(tmp), "clone", "--quiet", "--no-local", str(src), str(repo))
        _git(repo, "checkout", "--quiet", "--detach", sha)
        from codetwin.cli import main as cli
        if not (repo / ".codetwin.toml").exists() and cli(["-C", str(repo), "init"]) != 0:
            raise SystemExit("codetwin init failed")
        if not args.no_record:
            from codetwin.engine import Engine
            with Engine(repo) as eng:
                run = eng.record()
            if getattr(run, "incomplete", False):       # TestRun.incomplete exists from #100 on
                print(f"warning: the test run did not complete ({run.returncode}); runtime links are partial",
                      file=sys.stderr)
        out: Path = args.out
        out.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".snapshot-new-", dir=out))
        try:
            files = capture(repo, staging)
            meta = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "project": _project(src),
                    "commit": sha, "recorded": not args.no_record, "files": files,
                    "how": "python scripts/repo_snapshot.py (see the script docstring)"}
            (staging / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
            if (out / "api").exists():
                shutil.rmtree(out / "api")
            (staging / "api").replace(out / "api")
            (staging / "meta.json").replace(out / "meta.json")
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    print(f"snapshot of {meta['project']} at {sha[:10]}: {len(files)} API answers -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
