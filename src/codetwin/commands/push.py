"""`codetwin push`: upload a decision report to CodeTwin Cloud (docs/cloud.md, docs/data-policy.md).

Opt-in: nothing is ever uploaded unless this command runs. `--dry-run` prints exactly what would be sent.
In GitHub Actions it authenticates with the job's OIDC token (no secret); elsewhere it needs a project token
from a self-hosted server.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ..push import PushError, build_report, check_server, fit, github_oidc_token, send
from ._util import engine, print_json

NAME, HELP, ORDER = "push", "upload the decision report to CodeTwin Cloud (opt-in; --dry-run shows what is sent)", 34


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--decision", required=True, help="JSON from `codetwin select --json` ('-' for standard input)")
    p.add_argument("--server", default=os.environ.get("CODETWIN_SERVER"),
                   help="CodeTwin Cloud URL (default: $CODETWIN_SERVER); https, or http only for localhost")
    p.add_argument("--token", default=os.environ.get("CODETWIN_TOKEN"),
                   help="project token for a self-hosted server (default: $CODETWIN_TOKEN; GitHub Actions uses OIDC)")
    p.add_argument("--repository", help="OWNER/NAME (default: $GITHUB_REPOSITORY or the origin remote)")
    p.add_argument("--dry-run", action="store_true", help="print the report that would be sent; send nothing")
    p.add_argument("--best-effort", action="store_true",
                   help="exit 0 with a warning if the upload fails (CI: never fail a build because of the cloud)")


def run(args: argparse.Namespace) -> int:
    try:
        raw = sys.stdin.read() if args.decision == "-" else Path(args.decision).read_text(encoding="utf-8")
        decision = json.loads(raw)
        with engine(args) as eng:
            body = fit(build_report(eng, decision, repository=args.repository))
        if args.dry_run:
            print_json(body)
            return 0
        if not args.server:
            raise PushError("no server: pass --server or set CODETWIN_SERVER")
        check_server(args.server)          # before asking GitHub for a token: a bad URL costs nothing
        token = args.token or github_oidc_token(dict(os.environ))
        res = send(args.server, body, token)
        what = "stored" if res.get("created") else "already stored"
        print(f"report {what} as #{res.get('id')} on {args.server}")
        return 0
    except (PushError, OSError, ValueError, KeyError) as e:
        print(f"{'warning' if args.best_effort else 'error'}: codetwin push: {e}", file=sys.stderr)
        return 0 if args.best_effort else 1
    except Exception as e:  # noqa: BLE001  --best-effort promises never to fail the job because of the cloud
        if not args.best_effort:
            raise
        print(f"warning: codetwin push: {type(e).__name__}: {e}", file=sys.stderr)
        return 0
