"""Build the dashboard's demo data from a real CodeTwin run on `examples/python`.

The hosted dashboard (Vercel) has no `codetwin serve` behind it, so it shows a snapshot of the read-only API
instead. Every number in the snapshot comes from this script running the real engine; nothing is typed by hand.

    python scripts/demo_snapshot.py            # writes dashboard/public/demo/

What it does: copy the example project to a temporary git repository, `init` + `record`, then apply a series of
small edits; for each edit run `select` and `learn` (which labels the decision), and revert. Finally it calls the
API endpoints the dashboard uses and saves each answer as JSON, one file per request.

The snapshot is reproducible: commits get fixed dates and run times are normalised (`normalise()`), so running
the script twice gives the same `api/` files and CI can tell a stale snapshot from a fresh one.

Which requests are captured, and the file name of each, are shared with the dashboard through
`dashboard/src/lib/demo-contract.json`; `dashboard/src/lib/demo-path.mjs` (`demoName`) must name files like
`snapshot_name()` here.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "python"
OUT = ROOT / "dashboard" / "public" / "demo"
CONTRACT = json.loads((ROOT / "dashboard" / "src" / "lib" / "demo-contract.json").read_text(encoding="utf-8"))
# Fixed commit dates and a fixed clock origin, so the snapshot does not change from one run to the next.
GIT_DATE = "2026-01-01T00:00:00+00:00"
EPOCH = 1767225600.0  # 2026-01-01T00:00:00Z

# (file, old text, new text): small realistic edits; some change behaviour, some are no-ops, one adds code.
EDITS: list[tuple[str, str, str]] = [
    ("src/shop/calc.py", "return a * b", "return a * b * 1"),
    ("src/shop/calc.py", "return a + b", "return b + a"),
    ("src/shop/calc.py", "return a * b", "return a * b  # product"),
    ("src/shop/cart.py", "return mul(price, qty)", "return mul(qty, price)"),
    ("src/shop/calc.py", "return a + b", "return a + b + 0"),
    ("src/shop/cart.py", "return mul(price, qty)", "return mul(price, qty) if qty else 0"),
    ("src/shop/calc.py", "def mul(a, b):\n    return a * b",
     "def mul(a, b):\n    return a * b\n\n\ndef discount(p, pct):\n    return p * (1 - pct)"),
    ("src/shop/calc.py", "return a + b", "return sum((a, b))"),
    ("src/shop/cart.py", "from shop.calc import mul", "from shop.calc import mul  # used by total"),
    ("src/shop/calc.py", "return a * b", "return b * a"),
]


def snapshot_name(path: str, params: dict[str, str] | None = None) -> str:
    """`/decisions`, {"limit": "10"} -> `decisions__limit-10.json`. Must match `demoPath` in api.ts."""
    name = path.strip("/").replace("/", "_")
    params = params or {}
    for k in sorted(params):
        name += f"__{k}-{params[k]}"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) + ".json"


def sh(cwd: Path, *cmd: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_DATE": GIT_DATE, "GIT_COMMITTER_DATE": GIT_DATE}
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, env=env)


def build_repo(work: Path) -> Path:
    repo = work / "shop"
    shutil.copytree(EXAMPLE, repo, ignore=shutil.ignore_patterns(".codetwin", "__pycache__", "*.pyc"))
    sh(repo, "git", "init", "-q", "-b", "main")
    sh(repo, "git", "-c", "user.email=demo@codetwin.invalid", "-c", "user.name=CodeTwin demo", "add", "-A")
    sh(repo, "git", "-c", "user.email=demo@codetwin.invalid", "-c", "user.name=CodeTwin demo",
       "commit", "-q", "-m", "example project")
    return repo


def run_history(repo: Path) -> None:
    from codetwin.cli import main
    from codetwin.engine import Engine

    if main(["-C", str(repo), "init"]) != 0:
        raise SystemExit("codetwin init failed")
    with Engine(repo) as eng:
        eng.record()
        for file, old, new in EDITS:
            p = repo / file
            text = p.read_text()
            if old not in text:
                raise SystemExit(f"demo edit no longer applies to {file}: {old!r}")
            p.write_text(text.replace(old, new, 1))
            eng.select()
            eng.learn()
            sh(repo, "git", "checkout", "-q", "--", file)


def graph_files(graph: dict) -> list[str]:
    """Files a graph view links to (each node opens its own graph); "?" stands for unresolved code."""
    return [n["id"] for n in graph.get("nodes", []) if n.get("id") and n["id"] != "?"]


def normalise(answers: dict[str, object]) -> None:
    """Make run-dependent values stable: timestamps keep their order but start at EPOCH, one minute apart."""
    stamps: set[float] = set()

    def walk(x: object, fn) -> object:
        if isinstance(x, dict):
            return {k: (fn(k, v) if not isinstance(v, (dict, list)) else walk(v, fn)) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v, fn) for v in x]
        return x

    def collect(k: str, v: object) -> object:
        if k == "recorded" and isinstance(v, (int, float)):
            stamps.add(v)
        return v

    for a in answers.values():
        walk(a, collect)
    order = {t: EPOCH + 60.0 * i for i, t in enumerate(sorted(stamps))}

    def fix(k: str, v: object) -> object:
        if k == "recorded" and isinstance(v, (int, float)):
            return order[v]
        if k == "suite_seconds" and isinstance(v, (int, float)):
            return max(1.0, float(round(v)))
        return v

    for name in answers:
        answers[name] = walk(answers[name], fix)


def capture(repo: Path, out: Path) -> list[str]:
    """Call every API endpoint the dashboard uses and write one JSON file per request into `out/api`."""
    from fastapi.testclient import TestClient

    from codetwin.server.app import create_app

    client = TestClient(create_app(repo))
    answers: dict[str, object] = {}

    def fetch(path: str, params: dict[str, str]) -> Any:
        name = snapshot_name(path, params)
        if name not in answers:
            r = client.get(f"/api{path}", params=params or None)
            r.raise_for_status()
            data = r.json()
            if path == "/summary":
                data["root"] = "examples/python (demo)"      # never publish a local path
            answers[name] = data
        return answers[name]

    for path, params in CONTRACT["requests"]:
        fetch(path, params)
    # Every file the map or a graph links to gets its own graph, so no click in the demo ends in "not in the data".
    todo = graph_files(fetch("/map", {}))
    seen: set[str] = set()
    while todo:
        f = todo.pop()
        if f not in seen:
            seen.add(f)
            todo += graph_files(fetch("/graph", {"file": f}))

    normalise(answers)
    (out / "api").mkdir(parents=True, exist_ok=True)
    for name, data in answers.items():
        text = json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False)
        if str(repo) in text or tempfile.gettempdir() in text:
            raise SystemExit(f"refusing to publish a local path in {name}")
        (out / "api" / name).write_text(text + "\n", encoding="utf-8")
    return sorted(answers)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT, help=f"output folder (default: {OUT.relative_to(ROOT)})")
    args = ap.parse_args()
    out: Path = args.out
    with tempfile.TemporaryDirectory(prefix="codetwin-demo-") as tmp:
        repo = build_repo(Path(tmp))
        run_history(repo)
        # Write the new snapshot next to the old one and swap only when it is complete: a failure part way never
        # leaves a half-written folder whose meta.json lists files that are gone.
        out.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".demo-new-", dir=out))
        try:
            files = capture(repo, staging)
            meta = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "project": "examples/python",
                    "edits": len(EDITS), "files": files,
                    "how": "python scripts/demo_snapshot.py (runs the real engine; see the script docstring)"}
            (staging / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
            if (out / "api").exists():
                shutil.rmtree(out / "api")
            (staging / "api").replace(out / "api")
            (staging / "meta.json").replace(out / "meta.json")
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    print(f"demo snapshot: {len(files)} API answers from {len(EDITS)} labelled changes -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
