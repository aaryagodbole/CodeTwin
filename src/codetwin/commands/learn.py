from ._util import engine, print_json

NAME, HELP, ORDER = "learn", "run the full suite, record whether the last selection missed tests, update calibration", 40


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    with engine(args) as eng:
        print_json(eng.learn())
    return 0
