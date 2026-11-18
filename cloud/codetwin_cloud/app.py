"""CodeTwin Cloud API (docs/cloud.md). Upload endpoint plus read endpoints with the same response shapes as the
local `codetwin serve` API, scoped to a project, so the dashboard works against either."""

import hmac
import json
import logging
import math
import os
import re
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from . import auth, db
from .models import Report

log = logging.getLogger("codetwin_cloud")
_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
try:
    __version__ = version("codetwin-cloud")
except PackageNotFoundError:  # running from a source checkout (Vercel bundles the files)
    __version__ = "0.2.0"


@dataclass
class Settings:
    database_url: str | None = None                       # None: DATABASE_URL from the environment
    resolve_key: auth.KeyResolver = auth.github_key       # GitHub's JWKS; tests inject a local key
    audience: str = auth.AUDIENCE
    uploads_per_hour: int = 120
    max_report_bytes: int = 256 * 1024
    retention_days: int = 90
    cron_secret: str | None = field(default_factory=lambda: os.environ.get("CRON_SECRET"))
    cors_origins: list[str] = field(default_factory=lambda: [o.strip() for o in os.environ.get(
        "CODETWIN_CORS_ORIGINS", "*").split(",") if o.strip()])


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    app = FastAPI(title="CodeTwin Cloud", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_methods=["GET"], allow_headers=["*"])

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        given = request.headers.get("x-request-id") or ""
        # A caller's id is kept only if short and plain, so it cannot bloat or inject into the logs.
        rid = given if _REQUEST_ID.fullmatch(given) else uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        if request.url.path == "/api/health" and response.status_code == 200:
            return response         # health probes (every 30 s) would drown the request log; failures are logged
        # one JSON line per request; never the body, query string or any header value
        log.info(json.dumps({"rid": rid, "method": request.method, "path": request.url.path,
                             "status": response.status_code, "ms": round((time.perf_counter() - t0) * 1000, 1)}))
        return response

    @app.exception_handler(auth.AuthError)
    async def auth_error(_: Request, e: auth.AuthError) -> JSONResponse:
        return JSONResponse({"detail": str(e)}, status_code=e.status)

    def conn() -> Iterator[psycopg.Connection[DictRow]]:
        with db.connect(s.database_url) as c:
            yield c

    Conn = Annotated[psycopg.Connection[DictRow], Depends(conn)]

    # ------------------------------------------------------------------ health
    @app.get("/api/health")
    def health() -> JSONResponse:
        try:
            with db.connect(s.database_url) as c:
                c.execute("select 1")
            return JSONResponse({"status": "ok", "version": __version__, "database": "ok"})
        except Exception as e:  # noqa: BLE001  report any database failure as unhealthy, without details
            log.warning(json.dumps({"health": "database unavailable", "error": type(e).__name__}))
            return JSONResponse({"status": "degraded", "version": __version__, "database": "unavailable"},
                                status_code=503)

    # ------------------------------------------------------------------ upload
    @app.post("/api/v1/reports")
    async def upload(request: Request) -> JSONResponse:
        # Only reading the body is async. Everything else (psycopg, the JWKS fetch) blocks, so it runs in the
        # thread pool and never stalls the event loop for other requests.
        token = auth.bearer(request.headers.get("authorization"))
        body = await _read_capped(request, s.max_report_bytes)
        report_id, created = await run_in_threadpool(_store, body, token, s)
        return JSONResponse({"id": report_id, "created": created}, status_code=201 if created else 200)

    # ------------------------------------------------------------------ read (same shapes as codetwin serve)
    def project_of(c: psycopg.Connection[DictRow], owner: str, repo: str) -> dict:
        p = db.find_project(c, owner, repo)
        if p is None or not p["public"]:  # private projects need a session (not built yet)
            raise HTTPException(404, f"no public project {owner}/{repo}")
        return p

    @app.get("/api/v1/projects")
    def projects(c: Conn) -> list[dict]:
        rows = c.execute(
            "select p.owner, p.name, count(r.id) as reports, max(r.received_at) as last_report from project p "
            "left join report r on r.project_id = p.id where p.public group by p.id order by p.owner, p.name").fetchall()
        return [{"owner": r["owner"], "name": r["name"], "reports": r["reports"],
                 "last_report": r["last_report"].timestamp() if r["last_report"] else None} for r in rows]

    @app.get("/api/v1/projects/{owner}/{repo}/summary")
    def summary(owner: str, repo: str, c: Conn) -> dict:
        p = project_of(c, owner, repo)
        latest = c.execute("select base_sha, alpha, payload from report where project_id = %s "
                           "order by received_at desc, id desc limit 1", (p["id"],)).fetchone()
        counts = c.execute("select count(r.id) as decisions, count(o.report_id) as labelled from report r "
                           "left join outcome o on o.report_id = r.id where r.project_id = %s", (p["id"],)).fetchone()
        tests = (latest["payload"]["decision"].get("tests", []) if latest else [])
        seconds = [t["seconds"] for t in tests if t.get("seconds") is not None]
        alpha = latest["alpha"] if latest and latest["alpha"] is not None else 0.1
        return {"root": f"{p['owner']}/{p['name']}", "packages": [], "alpha": alpha, "alpha_t": alpha,
                "calibration_size": counts["labelled"] if counts else 0, "recorded_commit": latest["base_sha"] if latest else None,
                "test_files": len(tests), "suite_seconds": sum(seconds) if seconds else None,
                "decisions": counts["decisions"] if counts else 0, "labelled_decisions": counts["labelled"] if counts else 0}

    @app.get("/api/v1/projects/{owner}/{repo}/decisions")
    def decisions(owner: str, repo: str, c: Conn, limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
        p = project_of(c, owner, repo)
        rows = c.execute(_DECISIONS + "where r.project_id = %s order by r.id desc limit %s", (p["id"], limit)).fetchall()
        return [_decision_row(r) for r in rows]

    @app.get("/api/v1/projects/{owner}/{repo}/decisions/{decision_id}")
    def decision(owner: str, repo: str, decision_id: int, c: Conn) -> dict:
        p = project_of(c, owner, repo)
        r = c.execute(_DECISIONS + "where r.project_id = %s and r.id = %s", (p["id"], decision_id)).fetchone()
        if r is None:
            raise HTTPException(404, f"decision {decision_id} not found")
        d = r["payload"]["decision"]
        return {**_decision_row(r), "scores": {t["id"]: t.get("score") for t in d.get("tests", [])},
                "sections": d.get("sections", {}), "commit": r["payload"]["commit"],
                "run": r["payload"]["run"]}

    @app.get("/api/v1/projects/{owner}/{repo}/calibration")
    def calibration(owner: str, repo: str, c: Conn) -> dict:
        p = project_of(c, owner, repo)
        # Same population as the local API (store.labelled("calibrated")): full or fallback runs execute every
        # test, never miss, and would understate the miss rate.
        rows = c.execute("select r.id, r.alpha, o.missed from report r join outcome o on o.report_id = r.id "
                         "where r.project_id = %s and r.mode = 'calibrated' order by r.id", (p["id"],)).fetchall()
        points, misses = [], 0
        for i, row in enumerate(rows, 1):
            misses += int(row["missed"])
            points.append({"n": i, "decision_id": row["id"], "alpha": row["alpha"], "alpha_t": row["alpha"],
                           "observed_miss_rate": misses / i})
        return {"points": points, "labelled": len(rows), "misses": misses}

    # ------------------------------------------------------------------ retention (Vercel Cron, daily)
    @app.get("/api/cron/retention")
    def retention(request: Request) -> dict:
        given = request.headers.get("authorization") or ""
        if not s.cron_secret or not hmac.compare_digest(given.encode(), f"Bearer {s.cron_secret}".encode()):
            raise HTTPException(401, "cron secret required")      # before connecting: no database work for strangers
        with db.connect(s.database_url) as c:
            cur = c.execute("delete from report where received_at < now() - make_interval(days => %s)",
                            (s.retention_days,))
            c.commit()      # before the response: the count we return must be what was deleted
        return {"deleted": cur.rowcount, "retention_days": s.retention_days}

    return app


_DECISIONS = ("select r.id, r.received_at, r.base_sha, r.head_sha, r.mode, r.alpha, r.threshold, r.residual_risk, "
              "r.decision, r.payload, o.missed from report r left join outcome o on o.report_id = r.id ")


def _decision_row(r: dict[str, Any]) -> dict:
    """Same keys as `/api/decisions` of `codetwin serve`."""
    d = r["payload"]["decision"]
    return {"id": r["id"], "recorded": r["received_at"].timestamp(), "base": r["base_sha"] or r["head_sha"],
            "mode": r["mode"], "alpha": r["alpha"], "alpha_t": r["alpha"], "threshold": r["threshold"],
            "residual_risk": r["residual_risk"], "decision": r["decision"], "selected": d["selected"],
            "reasons": d.get("reasons", []), "missed": r["missed"]}


def _project_token(c: psycopg.Connection[DictRow], token: str) -> auth.Caller:
    row = c.execute("update project_token set last_used = now() where token_hash = %s returning project_id",
                    (auth.hash_token(token),)).fetchone()
    if row is None:
        raise auth.AuthError(401, "unknown project token")
    return auth.Caller("project-token", project_id=row["project_id"])


async def _read_capped(request: Request, limit: int) -> bytes:
    """The request body, refused with 413 as soon as it is larger than `limit` (never buffered in full)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, f"report larger than {limit // 1024} KB")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"report larger than {limit // 1024} KB")
        chunks.append(chunk)
    return b"".join(chunks)


def _store(body: bytes, token: str, s: Settings) -> tuple[int, bool]:
    """Authenticate, validate and store one report; commits before returning, so a 201 means it is stored.

    A GitHub OIDC token is verified before anything else and before a database connection is opened, so bad
    tokens never see schema errors and a slow key fetch never holds a connection."""
    oidc_caller = None if token.startswith(auth.TOKEN_PREFIX) else auth.verify_github_oidc(token, s.resolve_key,
                                                                                           s.audience)
    with db.connect(s.database_url) as c:
        caller = oidc_caller or _project_token(c, token)
        try:
            report = Report.model_validate_json(body)
        except ValidationError as e:
            raise HTTPException(422, json.loads(e.json(include_url=False, include_input=False))) from None
        if not _finite(report.decision.sections):
            raise HTTPException(422, "report sections contain NaN or Infinity")
        if caller.kind == "github-oidc":
            _check_claims(caller, report)          # before the lookup: a token cannot probe other projects
        project = db.find_project(c, *report.owner_name)
        if project is None or not project["uploads_enabled"]:
            raise HTTPException(403, f"{report.repository} is not registered for uploads (cloud/README.md)")
        if caller.kind == "github-oidc":
            _check_repository_id(c, project, caller)
        elif caller.project_id != project["id"]:
            raise HTTPException(403, "this project token belongs to another project")
        # One upload per project at a time from here on, so concurrent uploads cannot all pass the hourly limit.
        c.execute("select pg_advisory_xact_lock(%s, %s)", (_UPLOAD_LOCK, project["id"]))
        # A retry of a report that is already stored is not a new upload: answer it before the rate limit.
        existing = _existing(c, project["id"], report)
        if existing is not None:
            _add_outcome(c, existing, report)     # an outcome may arrive with a later upload of the same run
            c.commit()
            return existing, False
        recent = c.execute("select count(*) as n from report where project_id = %s and "
                           "received_at > now() - interval '1 hour'", (project["id"],)).fetchone()
        if recent and recent["n"] >= s.uploads_per_hour:
            raise HTTPException(429, f"at most {s.uploads_per_hour} uploads per project per hour")
        result = _insert(c, project["id"], report)
        c.commit()          # before the response is sent, so the client never sees "stored" for a lost write
        return result


_UPLOAD_LOCK = 0x0C0D7715             # pg_advisory_xact_lock class for per-project uploads (db.MIGRATION_LOCK + 1)


def _finite(value: Any) -> bool:
    """No NaN or Infinity anywhere inside free-form JSON (they cannot be stored in jsonb or served as JSON)."""
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, list):
        return all(_finite(v) for v in value)
    return True


def _check_repository_id(c: psycopg.Connection[Any], project: Any, caller: auth.Caller) -> None:
    """Bind the project to GitHub's repository id on its first OIDC upload, then require that id.

    One atomic statement, so two first uploads racing from different repositories cannot both pass."""
    if project["github_repository_id"] is not None and project["github_repository_id"] == caller.repository_id:
        return                             # already bound to this repository: no write, no row lock
    ok = c.execute("update project set github_repository_id = coalesce(github_repository_id, %s) "
                   "where id = %s and (github_repository_id is null or github_repository_id = %s) returning id",
                   (caller.repository_id, project["id"], caller.repository_id)).fetchone()
    if ok is None:
        raise HTTPException(403, "the token's repository id does not match this project (renamed or recreated "
                                 "repository); ask the operator to re-register it")


def _existing(c: psycopg.Connection[DictRow], project_id: int, report: Report) -> int | None:
    row = c.execute("select id from report where project_id = %s and run_id = %s and run_attempt = %s "
                    "and head_sha = %s", (project_id, report.run.id, report.run.attempt, report.commit.head)).fetchone()
    return row["id"] if row else None


def _check_claims(caller: auth.Caller, report: Report) -> None:
    """A job may upload only its own result: same repository, run, attempt and commit as in its OIDC token."""
    if (caller.repository or "").lower() != report.repository.lower():
        raise HTTPException(403, "the token's repository does not match the report")
    if report.run.source != "github-actions" or caller.run_id != report.run.id:
        raise HTTPException(403, "the token's workflow run does not match the report")
    if caller.run_attempt != report.run.attempt:
        raise HTTPException(403, "the token's run attempt does not match the report")
    if caller.sha != report.commit.head:
        raise HTTPException(403, "the token's commit does not match the report's head commit")


def _insert(c: psycopg.Connection[DictRow], project_id: int, report: Report) -> tuple[int, bool]:
    d = report.decision
    payload = report.model_dump(mode="json", by_alias=True)
    row = c.execute(
        "insert into report (project_id, head_sha, base_sha, ref, pull_request, run_source, run_id, run_attempt, "
        "engine_version, decision, residual_risk, alpha, threshold, mode, selected_count, payload) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "on conflict (project_id, run_id, run_attempt, head_sha) do nothing returning id",
        (project_id, report.commit.head, report.commit.base, report.commit.ref, report.commit.pull_request,
         report.run.source, report.run.id, report.run.attempt, report.engine.version, d.decision, d.residual_risk,
         d.alpha, d.threshold, d.mode, len(d.selected), Jsonb(payload))).fetchone()
    if row is None:                # stored by a concurrent request after _existing() looked
        existing = _existing(c, project_id, report)
        if existing is None:       # deleted between the two statements (retention); treat as a conflict
            raise HTTPException(409, "report was removed while it was being stored; retry")
        return existing, False
    _add_outcome(c, row["id"], report)
    return row["id"], True


def _add_outcome(c: psycopg.Connection[DictRow], report_id: int, report: Report) -> None:
    """Store the outcome if the report has one; the first outcome for a report is kept."""
    if report.outcome is not None:
        c.execute("insert into outcome (report_id, missed, failing) values (%s, %s, %s) "
                  "on conflict (report_id) do nothing",
                  (report_id, report.outcome.missed, Jsonb(report.outcome.failing)))
