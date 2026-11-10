from ._util import engine

NAME, HELP, ORDER = "record", "run the suite with per-test coverage on the current commit and store it", 20


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    r = engine(args).record()
    print(f"recorded {r.sha[:10]}: {len(r.durations)} test files, {len(r.covered)} with coverage, "
          f"{len(r.failing)} failing test cases, {r.wall:.1f}s")
    return 0
