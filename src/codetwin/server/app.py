"""FastAPI application. Every endpoint only reads evidence; nothing here changes a decision."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..commands.graph import build as build_view
from ..commands.graph import parse_lines
from ..engine import Engine
from ..graph.impact import build_graph
from ..graph.view import label


def _engine(request: Request) -> Iterator[Engine]:
    """Fresh engine per request (always reads the current evidence), closed when the request ends."""
    eng = Engine(request.app.state.root)
    try:
        yield eng
    finally:
        eng.close()


Eng = Annotated[Engine, Depends(_engine)]


def create_app(root: str | Path = ".", static_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="CodeTwin AI", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    # the Next.js dev server runs on another port during development
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                       allow_methods=["GET"], allow_headers=["*"])

    app.state.root = root

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/summary")
    def summary(eng: Eng) -> dict:
        base = eng.store.latest_run_sha()
        run = eng.store.get_run(base) if base else None
        counts = eng.store.counts()
        return {"root": str(eng.root), "packages": eng.cfg.packages, "alpha": eng.cfg.alpha,
                "alpha_t": eng.store.alpha_t(eng.cfg.alpha),
                "calibration_size": len(eng.store.calibration()),
                "recorded_commit": base, "test_files": len(run.durations) if run else 0,
                "suite_seconds": run.wall if run else None, **counts}

    @app.get("/api/llm")
    def llm_status(eng: Eng) -> dict:
        """Whether LLM explanations are available (which providers have keys); never returns the keys."""
        from ..llm import client_from_config
        return client_from_config(eng.cfg).status()

    @app.get("/api/decisions")
    def decisions(eng: Eng, limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
        keys = ["id", "recorded", "base", "mode", "alpha", "alpha_t", "threshold", "residual_risk", "decision",
                "selected", "reasons", "missed"]
        return [{k: d[k] for k in keys} for d in eng.store.decisions(limit)]

    @app.get("/api/calibration")
    def calibration(eng: Eng) -> dict:
        """Observed miss rate of labelled decisions over time, against the target alpha."""
        rows = eng.store.labelled("calibrated")
        points, misses = [], 0
        for i, (did, alpha, alpha_t, missed) in enumerate(rows, 1):
            misses += missed
            points.append({"n": i, "decision_id": did, "alpha": alpha, "alpha_t": alpha_t,
                           "observed_miss_rate": misses / i})
        return {"points": points, "labelled": len(rows), "misses": misses}

    @app.get("/api/map")
    def system_map(eng: Eng) -> dict:
        """Whole-project graph: files and tests, edges typed by evidence."""
        base = eng.store.latest_run_sha()
        run = eng.store.get_run(base) if base else None
        g = build_graph(eng.facts_now(), run)
        tests = set(eng.tests_now()) | (set(run.durations) if run else set())
        nodes = [{"id": n, "label": "unresolved" if n == "?" else label(n), "kind": "unknown" if n == "?" else
                  "test" if n in tests else "source", "path": n} for n in g.nodes]
        seen, edges = set(), []
        for u, v, data in g.edges(data=True):
            key = (u, v, data["type"])
            if key not in seen:
                seen.add(key)
                edges.append({"source": u, "target": v, "type": data["type"]})
        return {"nodes": nodes, "edges": edges, "recorded_commit": base}

    @app.get("/api/graph")
    def graph(eng: Eng, file: str, lines: str | None = None) -> dict:
        try:
            return build_view(eng, file, parse_lines(lines))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")
    return app
