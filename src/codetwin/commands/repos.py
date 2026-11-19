"""`codetwin repos`: the connected repositories ([[repos]]), where their files are, and syncing URL entries."""
from __future__ import annotations

import sys

from ._util import engine, print_json

NAME, HELP, ORDER = "repos", "list connected repositories ([[repos]]); --sync clones or updates those given by url", 54


def add_arguments(p) -> None:
    p.add_argument("--sync", action="store_true", help="clone or update every entry given by url into .codetwin/repos/")
    p.add_argument("--json", action="store_true")


def run(args) -> int:
    from ..crossrepo.sources import connected, sync
    with engine(args) as eng:
        synced = {s["name"]: s for s in sync(eng.cfg)} if args.sync else {}
        rows = [{"name": s.name, "url": s.url, "path": str(s.path) if s.path else None, "ref": s.ref,
                 "available": s.available, "error": s.error,
                 **({"sync": synced[s.name]["status"], "detail": synced[s.name]["detail"]} if s.name in synced else {})}
                for s in connected(eng.cfg)]
    if args.json:
        print_json(rows)
    elif not rows:
        print("no connected repositories ([[repos]] in .codetwin.toml, docs/crossrepo.md)")
    for r in rows if not args.json else []:
        where = r["url"] or r["path"]
        state = r["error"] or ("ready" if r["available"] else "not synced: run `codetwin repos --sync`")
        sync_note = f"  [{r['sync']}: {r['detail']}]" if "sync" in r else ""
        print(f"{r['name']:20} {where}  {state}{sync_note}")
    failed = [r for r in rows if r.get("sync") == "failed"]
    for r in failed:
        print(f"warning: could not sync {r['name']} ({r['url']}): {r['detail']}", file=sys.stderr)
    return 1 if failed else 0
