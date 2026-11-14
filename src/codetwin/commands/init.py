from .. import config

NAME, HELP, ORDER = "init", "write .codetwin.toml with guessed settings", 10


def add_arguments(p) -> None:
    p.add_argument("--language", help="python, javascript, go, java, ... (default: detected from the files)")


def run(args) -> int:
    path = config.write_template(args.root, getattr(args, "language", None))
    print(f"wrote {path}; review it, then run `codetwin record`")
    return 0
