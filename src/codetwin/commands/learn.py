from ._util import engine, print_json

NAME, HELP, ORDER = "learn", "run the full suite, record whether the last selection missed tests, update calibration", 40


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    print_json(engine(args).learn())
    return 0
