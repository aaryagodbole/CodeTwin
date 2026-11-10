from .. import config

NAME, HELP, ORDER = "init", "write .codetwin.toml with guessed settings", 10


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    path = config.write_template(args.root)
    print(f"wrote {path}; review it, then run `codetwin record`")
    return 0
