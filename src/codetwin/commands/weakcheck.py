from ..evidence.weakcheck import changed_functions, run_checks
from ._util import engine, print_json

NAME, HELP, ORDER = "weakcheck", "find changed functions that tests execute but do not check (extreme mutation)", 35


def add_arguments(p) -> None:
    p.add_argument("--base", help="recorded commit to compare with (default: latest recorded)")
    p.add_argument("--timeout", type=int, default=300, help="seconds per test run")
    p.add_argument("--json", action="store_true", help="machine-readable output")


def run(args) -> int:
    with engine(args) as eng:
        try:
            ch = eng.change(args.base)
        except RuntimeError as e:
            raise SystemExit(str(e)) from None
        checks = changed_functions(ch.diff, ch.prev, ch.static_base, ch.facts_now, ch.is_source)
        run_checks(eng.root, eng.cfg.src_root, checks, ch.facts_now, args.timeout, eng.lang)
    res = [{"file": c.file, "line": c.start, "status": c.status, "tests": c.tests, "killers": c.killers,
            "baseline_failures": c.baseline_failures} for c in checks]
    if args.json:
        print_json({"functions": res, "unchecked": sum(c.status == "unchecked" for c in checks)})
        return 0
    if not checks:
        print("no changed functions")
    for c in checks:
        print(f"{c.status:9} {c.file}:{c.start}  ({len(c.tests)} test files execute it)")
        if c.baseline_failures:
            print(f"          ignored {len(c.baseline_failures)} test file(s) that already fail without the mutation")
    n = sum(c.status == "unchecked" for c in checks)
    if n:
        print(f"{n} changed function(s) are executed but not checked by any test: coverage overstates safety here")
    return 0
