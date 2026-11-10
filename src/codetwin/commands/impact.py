from ._util import engine, print_json

NAME, HELP, ORDER = "impact", "tests and unknowns reached by files", 50


def add_arguments(p) -> None:
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true")


def run(args) -> int:
    imp = engine(args).impact(args.files)
    if args.json:
        print_json({"tests": {t: sorted(v) for t, v in imp.tests.items()}, "unknowns": imp.unknowns})
        return 0
    for t, types in sorted(imp.tests.items()):
        print(f"{t}  [{', '.join(sorted(types))}]")
    for u in imp.unknowns:
        print(f"UNKNOWN: {u}")
    return 0
