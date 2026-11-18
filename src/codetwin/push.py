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
    # The path after the host: "owner/name" only. A nested path (GitLab groups) is not guessed from its last parts.
    m = re.search(r"^(?:[a-z+]+://[^/]+/|[^@/:]+@[^:/]+[:/])(.+?)(?:\.git)?/?$", url)
    path = m.group(1) if m else ""
    if path.count("/") != 1:
        raise PushError("cannot tell the repository name from the origin remote; pass --repository OWNER/NAME")
    return path


def _pull_request(env: dict[str, str]) -> int | None:
    path = env.get("GITHUB_EVENT_PATH")
    if path and Path(path).is_file():
        try:
            event = json.loads(Path(path).read_text(encoding="utf-8"))
            pr = event.get("pull_request") if isinstance(event, dict) else None
            number = pr.get("number") if isinstance(pr, dict) else None
            return int(number) if isinstance(number, int) and not isinstance(number, bool) and number > 0 else None
        except (ValueError, OSError):
            return None
    return None


def _finite(x: Any) -> float | None:
    """A number the cloud can store, or None: NaN and Infinity are not valid JSON and are refused there."""
    if x is None or isinstance(x, bool):
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _clean(value: Any) -> Any:
    """Free-form section content with NaN and Infinity replaced by null (the cloud refuses them)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


MAX_UNSELECTED_TESTS = 500   # keeps a report of a large suite under the cloud's 256 KB limit
MAX_REPORT_BYTES = 250 * 1024  # the cloud refuses more than 256 KB (docs/cloud.md); keep a margin
MAX_REASONS = 200              # the cloud's limit (codetwin.report/v1)


def validate_decision(decision: Any) -> dict:
    """The output of `codetwin select --json`, checked before use; anything else is a PushError."""
    if not isinstance(decision, dict):
        raise PushError("the decision file is not a JSON object from `codetwin select --json`")
    if decision.get("decision") not in ("proceed", "abstain"):
        raise PushError("the decision file has no valid `decision` (proceed or abstain)")
    risk = decision.get("residual_risk")
    if not isinstance(risk, (int, float)) or isinstance(risk, bool) or not 0 <= risk <= 1:
        raise PushError("the decision file has no `residual_risk` between 0 and 1")
    selected = decision.get("selected")
    if not isinstance(selected, list) or not all(isinstance(t, str) for t in selected):
        raise PushError("the decision file's `selected` must be a list of test ids")
    for key, kind in (("reasons", list), ("extras", dict)):
        if decision.get(key) is not None and not isinstance(decision[key], kind):
            raise PushError(f"the decision file's `{key}` must be a {kind.__name__}")
    threshold = decision.get("threshold")
    if threshold is not None and (not isinstance(threshold, (int, float)) or isinstance(threshold, bool)):
        raise PushError("the decision file's `threshold` must be a number")
    schema = decision.get("schema")
    if schema is not None and (not isinstance(schema, int) or isinstance(schema, bool)):
        raise PushError("the decision file's `schema` must be an integer")
    if decision.get("mode") is not None and not isinstance(decision["mode"], str):
        raise PushError("the decision file's `mode` must be a string")
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
    newest = eng.store.decisions(limit=1)
    # Scores and alpha come from the stored decision only when it is the same decision as the JSON file; otherwise
    # the report has none rather than another decision's.
    detail = newest[0] if newest and _same_decision(newest[0], decision) else None
    run = eng.store.get_run(detail["base"]) if detail else None
    durations = run.durations if run else {}
    scores = eng.store.scores(detail["id"]) if detail else {}
    selected = set(decision["selected"])
    # Every selected test, plus the highest-scored others, so a large suite stays under the upload size limit.
    unselected = sorted((t for t in scores if t not in selected), key=lambda t: (-(_finite(scores[t]) or 0.0), t))
    tests = sorted(selected | set(unselected[:MAX_UNSELECTED_TESTS]))
    published = report.publishable()
    in_actions = env.get("GITHUB_ACTIONS") == "true"
    head = env.get("GITHUB_SHA") if in_actions else _git(root, "rev-parse", "HEAD")
    if not head:
        raise PushError("cannot tell the head commit (not a git repository?)")
    if in_actions and not env.get("GITHUB_RUN_ID"):
        raise PushError("GITHUB_RUN_ID is not set; cannot identify this workflow run")
    run_info = ({"source": "github-actions", "id": env["GITHUB_RUN_ID"],
                 "attempt": int(env.get("GITHUB_RUN_ATTEMPT", "1") or 1)} if in_actions else
                {"source": "cli", "id": _cli_run_id(head, decision), "attempt": 1})
    missed = detail.get("missed") if detail else None
    return {
        "schema": REPORT_SCHEMA,
        "engine": {"version": __version__, "output_schema": int(decision.get("schema") or OUTPUT_SCHEMA)},
        "repository": repository or repository_name(root, env),
        "commit": {"head": head, "base": detail["base"] if detail else None,
                   "ref": env.get("GITHUB_REF") or _git(root, "rev-parse", "--abbrev-ref", "HEAD") or None,
                   "pull_request": _pull_request(env)},
        "run": run_info,
        "decision": {
            "decision": decision["decision"],
            "residual_risk": _finite(decision["residual_risk"]) or 0.0,
            "alpha": _finite(detail.get("alpha")) if detail else None,
            "threshold": _finite(decision.get("threshold")),
            "mode": decision.get("mode") or "",
            "selected": sorted(selected),
            "tests": [{"id": t, "selected": t in selected, "score": _finite(scores.get(t)),
                       "seconds": _finite(durations.get(t))} for t in tests],
            "reasons": _reasons(decision.get("reasons") or []),
            # A section that failed carries {"error": "<exception text>"}: free text that may quote source, so it
            # is never published (docs/data-policy.md).
            "sections": {k: _clean(v) for k, v in (decision.get("extras") or {}).items()
                         if k in published and isinstance(v, dict) and "error" not in v},
        },
        "outcome": None if missed is None else {"missed": bool(missed), "failing": []},
    }


def _reasons(reasons: list) -> list[str]:
    """At most MAX_REASONS lines; the rest summed up in the last one (a large refactor can list hundreds)."""
    out = [str(r) for r in reasons]
    if len(out) <= MAX_REASONS:
        return out
    return [*out[:MAX_REASONS - 1], f"... and {len(out) - MAX_REASONS + 1} more"]


def fit(body: dict) -> dict:
    """Shrink the per-test rows until the report fits the upload limit; the selection itself is never cut.

    First the unselected rows go, then all rows, then the report sections (largest first; a section is extra detail,
    the decision is not). If the decision alone is still too large, this is a PushError that says what is large."""
    def size(b: dict) -> int:
        return len(json.dumps(b, allow_nan=False).encode())
    if size(body) <= MAX_REPORT_BYTES:
        return body
    d = body["decision"]
    for rows in ([t for t in d["tests"] if t["selected"]], []):
        body = {**body, "decision": {**d, "tests": rows}}
        if size(body) <= MAX_REPORT_BYTES:
            return body
    sections = dict(d.get("sections") or {})
    for name in sorted(sections, key=lambda k: -len(json.dumps(sections[k]))):
        del sections[name]
        body = {**body, "decision": {**body["decision"], "sections": dict(sections)}}
        if size(body) <= MAX_REPORT_BYTES:
            return body
    raise PushError(f"report too large to upload: {len(d['selected'])} selected tests and "
                    f"{len(d.get('reasons') or [])} reasons are over {MAX_REPORT_BYTES // 1024} KB without any rows or sections")


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
    data = json.dumps(body, allow_nan=False).encode()   # the cloud refuses NaN and Infinity
    req = urllib.request.Request(f"{check_server(server)}/api/v1/reports", data=data, method="POST",  # noqa: S310
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}",
                                          "User-Agent": f"codetwin/{__version__}"})
    try:
        with _opener.open(req, timeout=timeout) as r:  # scheme checked by check_server
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode(errors="replace")[:500]
        except (http.client.HTTPException, OSError):          # the error body itself was cut off
            detail = "(no readable answer)"
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
