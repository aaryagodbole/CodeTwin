"""Build the dashboard's demo data from a real CodeTwin run on `examples/python`.

The hosted dashboard (Vercel) has no `codetwin serve` behind it, so it shows a snapshot of the read-only API
instead. Every number in the snapshot comes from this script running the real engine; nothing is typed by hand.

    python scripts/demo_snapshot.py            # writes dashboard/public/demo/

What it does: copy the example project to a temporary git repository, `init` + `record`, then apply a series of
small edits; for each edit run `select` and `learn` (which labels the decision), and revert. Finally it calls the
API endpoints the dashboard uses and saves each answer as JSON, one file per request.

File names are produced by `snapshot_name()`; `dashboard/src/lib/api.ts` (`demoPath`) must produce the same name.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "python"
OUT = ROOT / "dashboard" / "public" / "demo"

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
GRAPH_FILES = ["src/shop/calc.py", "src/shop/cart.py"]


def snapshot_name(path: str, params: dict[str, str] | None = None) -> str:
    """`/decisions`, {"limit": "10"} -> `decisions__limit-10.json`. Must match `demoPath` in api.ts."""
    name = path.strip("/").replace("/", "_")
    for k in sorted(params or {}):
        name += f"__{k}-{params[k]}"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) + ".json"


def sh(cwd: Path, *cmd: str) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


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


def capture(repo: Path, out: Path) -> list[str]:
    from fastapi.testclient import TestClient

    from codetwin.server.app import create_app

    requests: list[tuple[str, dict[str, str] | None]] = [
        ("/health", None), ("/summary", None), ("/calibration", None), ("/map", None),
        ("/decisions", {"limit": "10"}), ("/decisions", {"limit": "500"}),
        *[("/graph", {"file": f}) for f in GRAPH_FILES],
    ]
    client = TestClient(create_app(repo))
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for path, params in requests:
        r = client.get(f"/api{path}", params=params)
        r.raise_for_status()
        data = r.json()
        if path == "/summary":
            data["root"] = "examples/python (demo)"      # never publish a local path
        text = json.dumps(data, indent=1, sort_keys=True)
        if str(repo) in text or tempfile.gettempdir() in text:
            raise SystemExit(f"refusing to publish a local path in {path}")
        name = snapshot_name(path, params)
        (out / "api").mkdir(exist_ok=True)
        (out / "api" / name).write_text(text + "\n")
        written.append(name)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT, help=f"output folder (default: {OUT.relative_to(ROOT)})")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="codetwin-demo-") as tmp:
        repo = build_repo(Path(tmp))
        run_history(repo)
        if (args.out / "api").exists():
            shutil.rmtree(args.out / "api")
        files = capture(repo, args.out)
    meta = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "project": "examples/python",
            "edits": len(EDITS), "files": sorted(files),
            "how": "python scripts/demo_snapshot.py (runs the real engine; see the script docstring)"}
    (args.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"demo snapshot: {len(files)} API answers from {len(EDITS)} labelled changes -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
