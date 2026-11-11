from ._util import engine, print_json

NAME, HELP, ORDER = "select", "select tests for the changes since the recorded commit", 30


def add_arguments(p) -> None:
    p.add_argument("--base", help="recorded commit to compare with (default: latest recorded)")
    p.add_argument("--alpha", type=float, help="target miss rate (default from config)")
    p.add_argument("--budget", type=float, help="budget mode: share of full-suite time, e.g. 0.25")
    p.add_argument("--json", action="store_true", help="machine-readable output (see docs/output.md)")


def run(args) -> int:
    with engine(args) as eng:
        d = eng.select(args.base, args.alpha, args.budget)
    if args.json:
        print_json(d.to_dict())
        return 0
    print(f"decision: {d.decision.upper()}   estimated residual risk: {d.residual_risk:.1%}   mode: {d.mode}")
    for r in d.reasons:
        print(f"  - {r}")
    print(f"selected {len(d.selected)} test files:")
    for t in sorted(d.selected):
        print(f"  {t}")
    for name, section in d.extras.items():
        summary = section.get("summary") if isinstance(section, dict) else None
        if summary:
            print(f"{name}: {summary}")
    return 0
