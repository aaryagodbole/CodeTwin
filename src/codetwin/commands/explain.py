from ._util import engine, print_json

NAME, HELP, ORDER = "explain", "evidence behind the last decision", 60


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    with engine(args) as eng:
        print_json(eng.explain())
    return 0
