from ._util import engine

NAME, HELP, ORDER = "record", "run the suite with per-test coverage on the current commit and store it", 20


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    with engine(args) as eng:
        r = eng.record()
    with_cov = sum(1 for files in r.covered.values() if files)
    print(f"recorded {r.sha[:10]}: {len(r.durations)} test files, {with_cov} with coverage, "
          f"{len(r.failing)} failing test cases, {r.wall:.1f}s")
    for n in r.notes:
        print(f"warning: {n}")
    return 0
