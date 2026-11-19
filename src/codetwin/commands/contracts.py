"""`codetwin contracts`: breaking OpenAPI / JSON-schema changes and the code and tests that rely on them."""
from ._util import engine, print_json

NAME, HELP, ORDER = "contracts", "breaking OpenAPI/JSON-schema changes linked to consumer code and tests", 56


def add_arguments(p) -> None:
    p.add_argument("--base", help="compare with this commit (default: the last recorded run, else HEAD)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--fail-on-breaking", action="store_true", help="exit with status 1 if a breaking change is found")


def run(args) -> int:
    from ..contracts import for_change
    with engine(args) as eng:
        out = for_change(eng.cfg, eng.lang, eng.change(args.base, require_run=False).base, eng.store)
    if args.json:
        print_json(out)
    else:
        print(out["summary"])
        for b in out["breaking"]:
            print(f"== BREAKING {b['location']} ({b['file']}): {b['detail']}")
            for c in b["consumers"]:
                print(f"  {c['repo']}: {c['file']}:{c['line']}  [{c['how']}]")
            for t, ev in b["tests"].items():
                print(f"  run  {t}  [{', '.join(ev)}]")
        for u in out["unknowns"]:
            print(f"UNKNOWN: {u}")
    return 1 if args.fail_on_breaking and out["breaking"] else 0
