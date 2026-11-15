"""`codetwin why TEST`: when a test started failing, which commits are suspects, and the likely cause."""
from ._util import engine, print_json

NAME, HELP, ORDER = "why", "why a test fails: timeline, suspect commits, likely cause (regression, flaky, ...)", 57


def add_arguments(p) -> None:
    p.add_argument("test", help="test file (as in `codetwin select` output)")
    p.add_argument("--rerun", type=int, default=0, metavar="N", help="also run the test N times now (flakiness check)")
    p.add_argument("--json", action="store_true")


def run(args) -> int:
    from ..store.db import outcomes_of
    from ..triage import triage
    with engine(args) as eng:
        reruns: list[bool] = []
        for _ in range(max(0, args.rerun)):
            r = eng.lang.run_suite("working-tree", [args.test])
            o = outcomes_of(r).get(args.test)
            reruns.append(o is not None and not o and r.returncode in (0, "0"))
            eng.store.add_outcomes("working-tree", {args.test: o if o is not None else [f"{args.test}::<no result>"]},
                                   "rerun")
        out = triage(eng.root, eng.store, eng.facts_now(), args.test, reruns or None)
    if args.json:
        print_json(out)
        return 0
    print(out["summary"])
    for h in out["timeline"][-12:]:
        print(f"  {'PASS' if h['passed'] else 'FAIL'}  {h['sha'][:10]:<12} {h['source']}"
              + (f"  {', '.join(h['failing_cases'][:3])}" if h["failing_cases"] else ""))
    for s in out["suspects"]:
        print(f"  suspect {s['score']:>4.1f}  {s['title'] or s['commit'][:10]}: {'; '.join(s['reasons'][:2])}")
    print(f"likely cause: {out['hypothesis']}" + (f" ({'; '.join(out['evidence'])})" if out["evidence"] else ""))
    for u in out["unknowns"]:
        print(f"UNKNOWN: {u}")
    return 0
