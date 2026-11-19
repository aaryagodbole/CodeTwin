"""`codetwin crossrepo`: files and tests in connected repositories that the current change may affect."""
import sys

from ._util import engine, print_json

NAME, HELP, ORDER = "crossrepo", "files and tests in connected repositories ([[repos]]) affected by the change", 55


def add_arguments(p) -> None:
    p.add_argument("--base", help="compare with this commit (default: the last recorded run, else HEAD)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--sync", action="store_true",
                   help="first clone or update every [[repos]] entry given by url (into .codetwin/repos/), then analyse")


def run(args) -> int:
    from ..crossrepo.analysis import for_change
    with engine(args) as eng:
        if args.sync:
            from ..crossrepo.sources import sync
            for st in sync(eng.cfg):      # on stderr, so --json output stays one JSON document
                print(f"sync {st['name']}: {st['status']} ({st['detail']})", file=sys.stderr)
        ch = eng.change(args.base, require_run=False)
        out = for_change(eng.cfg, ch.facts_now, ch.diff, ch.is_source, eng.store, ch.base)
    if args.json:
        print_json(out)
        return 0
    print(out["summary"])
    for r in out["repos"]:
        print(f"== {r['summary']}")
        for c in r["consumers"]:
            what = f"uses {', '.join(c['symbols'])} (lines {', '.join(map(str, c['lines'][:8]))})" \
                if c["symbols"] else f"imports {', '.join(c['imports'])}"
            print(f"  {'test' if c['is_test'] else 'file'}  {c['file']}  {what}")
        for t, ev in r["tests"].items():
            print(f"  run   {t}  [{', '.join(ev)}]")
        for u in r["unknowns"]:
            print(f"  UNKNOWN: {u}")
    return 0
