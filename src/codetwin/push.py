"""Build and upload a decision report to CodeTwin Cloud (docs/cloud.md, "Report format"; docs/data-policy.md).

The report holds identifiers, the decision, test ids with scores and durations, and the report sections that opted
in with ``PUBLISH = True``. It never holds source code, diffs, coverage line maps or git history. ``--dry-run``
prints exactly what would be sent.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__, report
from .selection import OUTPUT_SCHEMA

REPORT_SCHEMA = "codetwin.report/v1"
AUDIENCE = "codetwin-cloud"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class PushError(Exception):
    pass


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return out.stdout.strip() if out.returncode == 0 else ""


def repository_name(root: Path, env: dict[str, str]) -> str:
    """owner/name: GITHUB_REPOSITORY in Actions, else parsed from the `origin` remote."""
    if env.get("GITHUB_REPOSITORY"):
        return env["GITHUB_REPOSITORY"]
    url = _git(root, "remote", "get-url", "origin")
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        raise PushError("cannot tell the repository name; pass --repository OWNER/NAME")
    return f"{m.group(1)}/{m.group(2)}"


def _pull_request(env: dict[str, str]) -> int | None:
    path = env.get("GITHUB_EVENT_PATH")
    if path and Path(path).is_file():
        try:
            pr = json.loads(Path(path).read_text()).get("pull_request") or {}
            return int(pr["number"]) if "number" in pr else None
        except (ValueError, OSError):
            return None
    return None


def _finite(x: Any) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def build_report(eng: Any, decision: dict, env: dict[str, str] | None = None,
                 repository: str | None = None) -> dict:
    """The upload body for one decision: `decision` is the output of `codetwin select --json`."""
    env = dict(os.environ if env is None else env)
    root = Path(eng.root)
    stored = eng.store.last_decision()
    # Scores and alpha come from the stored decision only when it is the same decision as the JSON file.
    same = bool(stored) and sorted(stored["selected"]) == sorted(decision.get("selected", []))
    detail = eng.store.decision(stored["id"]) if same else None
    run = eng.store.get_run(detail["base"]) if detail else None
    durations = run.durations if run else {}
    scores = stored["scores"] if same else {}
    selected = set(decision.get("selected", []))
    tests = sorted(set(scores) | selected)
    published = report.publishable()
    in_actions = env.get("GITHUB_ACTIONS") == "true"
    head = env.get("GITHUB_SHA") if in_actions else _git(root, "rev-parse", "HEAD")
    if not head:
        raise PushError("cannot tell the head commit (not a git repository?)")
    run_info = ({"source": "github-actions", "id": env.get("GITHUB_RUN_ID", ""),
                 "attempt": int(env.get("GITHUB_RUN_ATTEMPT", "1") or 1)} if in_actions else
                {"source": "cli", "id": f"cli-{detail['id']}" if detail else f"cli-{head[:12]}", "attempt": 1})
    missed = detail.get("missed") if detail else None
    return {
        "schema": REPORT_SCHEMA,
        "engine": {"version": __version__, "output_schema": int(decision.get("schema", OUTPUT_SCHEMA))},
        "repository": repository or repository_name(root, env),
        "commit": {"head": head, "base": detail["base"] if detail else None,
                   "ref": env.get("GITHUB_REF") or _git(root, "rev-parse", "--abbrev-ref", "HEAD") or None,
                   "pull_request": _pull_request(env)},
        "run": run_info,
        "decision": {
            "decision": decision["decision"],
            "residual_risk": float(decision["residual_risk"]),
            "alpha": _finite(detail.get("alpha")) if detail else None,
            "threshold": _finite(decision.get("threshold")),
            "mode": str(decision.get("mode", "")),
            "selected": sorted(selected),
            "tests": [{"id": t, "selected": t in selected, "score": _finite(scores.get(t)),
                       "seconds": _finite(durations.get(t))} for t in tests],
            "reasons": list(decision.get("reasons", [])),
            "sections": {k: v for k, v in (decision.get("extras") or {}).items()
                         if k in published and isinstance(v, dict)},
        },
        "outcome": None if missed is None else {"missed": bool(missed), "failing": []},
    }


def check_server(url: str) -> str:
    """HTTPS only, except for a server on this machine (self-hosting, development)."""
    u = urllib.parse.urlparse(url)
    if u.scheme == "https" or (u.scheme == "http" and u.hostname in LOCAL_HOSTS):
        return url.rstrip("/")
    raise PushError(f"refusing to send a report to {url!r}: use https (http only for localhost)")


def github_oidc_token(env: dict[str, str], audience: str = AUDIENCE) -> str:
    """Ask GitHub Actions for an OIDC token (the job needs `permissions: id-token: write`)."""
    url, bearer = env.get("ACTIONS_ID_TOKEN_REQUEST_URL"), env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not bearer:
        raise PushError("no GitHub OIDC token available: give the job `permissions: id-token: write`, "
                        "or pass --token for a self-hosted server")
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}audience={urllib.parse.quote(audience)}",  # noqa: S310  GitHub URL
                                 headers={"Authorization": f"bearer {bearer}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
            return str(json.loads(r.read())["value"])
    except (urllib.error.URLError, KeyError, ValueError) as e:
        raise PushError(f"could not get a GitHub OIDC token: {e}") from None


def send(server: str, body: dict, token: str, timeout: float = 20) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{check_server(server)}/api/v1/reports", data=data, method="POST",  # noqa: S310
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}",
                                          "User-Agent": f"codetwin/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310  scheme checked by check_server
            return {"status": r.status, **json.loads(r.read() or b"{}")}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise PushError(f"upload refused ({e.code}): {detail}") from None
    except urllib.error.URLError as e:
        raise PushError(f"cannot reach {server}: {e.reason}") from None
