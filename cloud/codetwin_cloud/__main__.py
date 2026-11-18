"""Operator commands (run where DATABASE_URL points at the cloud database):

    python -m codetwin_cloud migrate
    python -m codetwin_cloud add-project OWNER/NAME [--public | --private] [--token]
    python -m codetwin_cloud new-token OWNER/NAME
"""
from __future__ import annotations

import argparse
import sys

from . import auth, db


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m codetwin_cloud", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply database migrations")
    add = sub.add_parser("add-project", help="register a repository that may upload reports")
    add.add_argument("repository", help="OWNER/NAME")
    vis = add.add_mutually_exclusive_group()
    vis.add_argument("--public", dest="public", action="store_true", default=None,
                     help="anyone with the link can read its reports")
    vis.add_argument("--private", dest="public", action="store_false",
                     help="only signed-in members can read it (default for a new project)")
    add.add_argument("--token", action="store_true", help="also create an upload token (self-hosted, no OIDC)")
    tok = sub.add_parser("new-token", help="create an upload token for a registered repository")
    tok.add_argument("repository", help="OWNER/NAME")
    args = ap.parse_args(argv)
    owner, _, name = getattr(args, "repository", "").partition("/")
    if args.cmd != "migrate" and (not owner or not name):
        ap.error("repository must be OWNER/NAME")           # before connecting: a typo never touches the database

    with db.connect() as c:
        if args.cmd == "migrate":
            print("migrations up to date")      # db.connect() applied any pending migration
            return 0
        if args.cmd == "add-project":
            # Re-running add-project (e.g. only for --token) keeps the visibility unless --public/--private is given.
            row = c.execute("insert into project (owner, name, public) values (%s, %s, %s) "
                            "on conflict (lower(owner), lower(name)) do update set public = "
                            "coalesce(%s, project.public) returning public",
                            (owner, name, bool(args.public), args.public)).fetchone()
            print(f"registered {owner}/{name} ({'public' if row and row['public'] else 'private'})")
        row = db.find_project(c, owner, name)
        if row is None:
            print(f"{owner}/{name} is not registered; run add-project first", file=sys.stderr)
            return 1
        if args.cmd == "new-token" or getattr(args, "token", False):
            token, digest = auth.new_project_token()
            c.execute("insert into project_token (project_id, token_hash) values (%s, %s)", (row["id"], digest))
            print(f"upload token (shown once, store it as a CI secret): {token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
