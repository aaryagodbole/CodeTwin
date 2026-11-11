"""CLI commands, one module per command (auto-discovered by ``codetwin.cli``).

A command module defines::

    NAME = "gaps"                       # sub-command name
    HELP = "one-line help"
    ORDER = 50                          # optional: position in --help (lower first)
    def add_arguments(p): ...           # argparse sub-parser
    def run(args) -> int: ...           # use ``with engine(args) as eng:`` (commands._util)

Add a new file here for a new command; do not edit ``cli.py``.
"""
