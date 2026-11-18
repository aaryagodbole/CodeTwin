"""Build and upload a decision report to CodeTwin Cloud (docs/cloud.md, "Report format"; docs/data-policy.md).

The report holds identifiers, the decision, test ids with scores and durations, and the report sections that opted
in with ``PUBLISH = True``. It never holds source code, diffs, coverage line maps or git history. ``--dry-run``
prints exactly what would be sent.
"""
from __future__ import annotations

import hashlib
import http.client
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
            pr = json.loads(Path(path).read_text(encoding="utf-8")).get("pull_request") or {}
            return int(pr["number"]) if "number" in pr else None
        except (ValueError, OSError):
            return None
    return None


def _finite(x: Any) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def validate_decision(decision: Any) -> dict:
    """The output of `codetwin select --json`, checked before use; anything else is a PushError."""
    if not isinstance(decision, dict):
        raise PushError("the decision file is not a JSON object from `codetwin select --json`")
    if decision.get("decision") not in ("proceed", "abstain"):
        raise PushError("the decision file has no valid `decision` (proceed or abstain)")
    if not isinstance(decision.get("residual_risk"), (int, float)) or isinstance(decision.get("residual_risk"), bool):
        raise PushError("the decision file has no numeric `residual_risk`")
    selected = decision.get("selected")
    if not isinstance(selected, list) or not all(isinstance(t, str) for t in selected):
        raise PushError("the decision file's `selected` must be a list of test ids")
    for key, kind in (("reasons", list), ("extras", dict)):
        if decision.get(key) is not None and not isinstance(decision[key], kind):
            raise PushError(f"the decision file's `{key}` must be a {kind.__name__}")
    if decision.get("threshold") is not None and not isinstance(decision["threshold"], (int, float)):
        raise PushError("the decision file's `threshold` must be a number")
    return decision


def _same_decision(stored: dict, decision: dict) -> bool:
    """Whether the newest stored decision is the one in the JSON file. The JSON carries no decision id, so compare
    what it does carry: verdict, mode, threshold and selection. (Not residual_risk: for an abstention the stored
    value can differ from the printed one.)"""
    def close(a: Any, b: Any) -> bool:
        return (a is None and b is None) or (a is not None and b is not None and math.isclose(float(a), float(b)))
    return (stored.get("decision") == decision["decision"] and stored.get("mode") == decision.get("mode")
            and close(stored.get("threshold"), decision.get("threshold"))
            and sorted(stored.get("selected", [])) == sorted(decision["selected"]))


def build_report(eng: Any, decision: dict, env: dict[str, str] | None = None,
                 repository: str | None = None) -> dict:
    """The upload body for one decision: `decision` is the output of `codetwin select --json`."""
    decision = validate_decision(decision)
    env = dict(os.environ if env is None else env)
    root = Path(eng.root)
    stored = eng.store.last_decision()
    full = eng.store.decision(stored["id"]) if stored else None
    # Scores and alpha come from the stored decision only when it is the same decision as the JSON file; otherwise
    # the report has none rather than another decision's.
    same = stored is not None and full is not None and _same_decision({**full, "selected": stored["selected"]},
                                                                       decision)
    detail = full if same else None
    run = eng.store.get_run(detail["base"]) if detail else None
    durations = run.durations if run else {}
    scores = stored["scores"] if same and stored else {}
    selected = set(decision["selected"])
    tests = sorted(set(scores) | selected)
    published = report.publishable()
    in_actions = env.get("GITHUB_ACTIONS") == "true"
    head = env.get("GITHUB_SHA") if in_actions else _git(root, "rev-parse", "HEAD")
    if not head:
        raise PushError("cannot tell the head commit (not a git repository?)")
    run_info = ({"source": "github-actions", "id": env.get("GITHUB_RUN_ID", ""),
                 "attempt": int(env.get("GITHUB_RUN_ATTEMPT", "1") or 1)} if in_actions else
                {"source": "cli", "id": _cli_run_id(head, decision), "attempt": 1})
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


def _cli_run_id(head: str, decision: dict) -> str:
    """A run id for uploads outside CI. The same decision on the same commit gets the same id, so a retry is
    deduplicated; a different decision (or another clone's) gets another id, so it is not discarded as a duplicate."""
    canonical = json.dumps({k: decision.get(k) for k in ("decision", "residual_risk", "threshold", "mode",
                                                         "selected", "reasons")}, sort_keys=True)
    return "cli-" + hashlib.sha256(f"{head}\n{canonical}".encode()).hexdigest()[:20]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect with credentials: urllib would resend the Authorization header, possibly over
    plain HTTP or to another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise PushError(f"refusing to follow a redirect ({code}) to {newurl!r} with credentials")


_opener = urllib.request.build_opener(_NoRedirect)


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
        with _opener.open(req, timeout=15) as r:
            return str(json.loads(r.read())["value"])
    except (urllib.error.URLError, http.client.HTTPException, OSError, KeyError, TypeError, ValueError) as e:
        raise PushError(f"could not get a GitHub OIDC token: {e}") from None


def send(server: str, body: dict, token: str, timeout: float = 20) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{check_server(server)}/api/v1/reports", data=data, method="POST",  # noqa: S310
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}",
                                          "User-Agent": f"codetwin/{__version__}"})
    try:
        with _opener.open(req, timeout=timeout) as r:  # scheme checked by check_server
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise PushError(f"upload refused ({e.code}): {detail}") from None
    except urllib.error.URLError as e:
        raise PushError(f"cannot reach {server}: {e.reason}") from None
    except (http.client.HTTPException, OSError) as e:      # e.g. IncompleteRead: the answer was cut off
        raise PushError(f"incomplete answer from {server}: {type(e).__name__}") from None
    try:
        answer = json.loads(raw or b"{}")
    except ValueError:
        raise PushError(f"the server's answer is not JSON (status {status})") from None
    if not isinstance(answer, dict) or not isinstance(answer.get("id"), int) or not isinstance(
            answer.get("created"), bool):
        raise PushError(f"unexpected answer from the server (status {status}): expected an id and created flag")
    # Not retried here: the upload may already be stored; the next run's push is deduplicated by run id.
    return {"status": status, **answer}
