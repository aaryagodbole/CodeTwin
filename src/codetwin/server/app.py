"""FastAPI application. Every endpoint only reads evidence; nothing here changes a decision."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .. import __version__, views
from ..commands.graph import build as build_view
from ..commands.graph import parse_lines
from ..engine import Engine
from ..graph.impact import build_graph
from ..graph.view import label


def _engine(request: Request) -> Iterator[Engine]:
    """Fresh engine per request (always reads the current evidence), closed when the request ends."""
    with Engine(request.app.state.root) as eng:
        yield eng


Eng = Annotated[Engine, Depends(_engine)]

_clean_decision = views.decision_row      # kept for callers of the old name


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
        return views.summary(eng)

    @app.get("/api/llm")
    def llm_status(eng: Eng) -> dict:
        """Whether LLM explanations are available (which providers have keys); never returns the keys."""
        from ..llm import client_from_config
        return client_from_config(eng.cfg).status()

    @app.get("/api/decisions")
    def decisions(eng: Eng, limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
        return [views.decision_row(d) for d in eng.store.decisions(limit)]

    @app.get("/api/decisions/{decision_id}")
    def decision_detail(eng: Eng, decision_id: int) -> dict:
        """One decision by id, including selection, reasons, per-test risk scores and outcome."""
        d = views.decision_detail(eng.store, decision_id)
        if d is None:
            raise HTTPException(404, f"decision {decision_id} not found")
        return d

    @app.get("/api/flaky")
    def flaky(eng: Eng) -> list[dict]:
        """Flaky tests (passed and failed on the same commit), grouped by test and sorted by total failures."""
        grouped: dict[str, dict] = {}
        for row in eng.store.flaky_tests():
            t = row["test"]
            if t not in grouped:
                grouped[t] = {"test": t, "passes": 0, "failures": 0, "commits": 0, "last_sha": row["sha"]}
            grouped[t]["passes"] += row["passes"]
            grouped[t]["failures"] += row["failures"]
            grouped[t]["commits"] += 1
            grouped[t]["last_sha"] = row["sha"]
        res = list(grouped.values())
        res.sort(key=lambda x: x["failures"], reverse=True)
        return res

    @app.get("/api/kg")
    def knowledge_graph(request: Request, eng: Eng, symbols: bool = Query(True)) -> dict:
        """Code knowledge graph: repositories, files, symbols and tests, with typed evidence edges."""
        sha = eng.store.latest_run_sha()
        if not sha:
            raise HTTPException(404, "no recorded run yet; run `codetwin record` first")

        key = (sha, eng.store.latest_run_recorded())
        cache = getattr(request.app.state, "_kg_cache", None)
        if cache is None or cache[0] != key:
            try:
                from ..kg import from_engine
                from ..kg.export import to_json
                kg = from_engine(eng, sha)
                raw = to_json(kg)
            except RuntimeError as e:
                raise HTTPException(404, str(e)) from e
            nodes = raw.get("nodes", [])
            edges = raw.get("links", raw.get("edges", []))
            stats = raw.get("stats", kg.stats())
            cache = (key, {"nodes": nodes, "edges": edges, "stats": stats})
            request.app.state._kg_cache = cache

        base_data = cache[1]
        if not symbols:
            nodes = [n for n in base_data["nodes"] if n.get("kind") != "symbol"]
            node_ids = {n["id"] for n in nodes}
            edges = [e for e in base_data["edges"] if e.get("source") in node_ids and e.get("target") in node_ids]
            nk = Counter(n["kind"] for n in nodes if "kind" in n)
            ek = Counter(e["kind"] for e in edges if "kind" in e)
            stats = {
                "nodes": len(nodes),
                "edges": len(edges),
                "node_kinds": dict(sorted(nk.items())),
                "edge_kinds": dict(sorted(ek.items())),
            }
            return {"nodes": nodes, "edges": edges, "stats": stats}
        return {"nodes": base_data["nodes"], "edges": base_data["edges"], "stats": base_data["stats"]}

    @app.get("/api/calibration")
    def calibration(eng: Eng) -> dict:
        """Observed miss rate of labelled decisions over time, against the target alpha."""
        return views.calibration(eng.store)

    @app.get("/api/map")
    def system_map(eng: Eng) -> dict:
        """Whole-project graph: files and tests, edges typed by evidence."""
        ch = eng.change(require_run=False)
        run = ch.prev
        base = ch.base if run is not None else None
        g = build_graph(ch.facts_now, run)
        tests = set(ch.tests_now) | (set(run.durations) if run else set())
        nodes = [{"id": n, "label": "unresolved" if n == "?" else label(n), "kind": "unknown" if n == "?" else
                  "test" if n in tests else "source", "path": n} for n in g.nodes]
        seen, edges = set(), []
        for u, v, data in g.edges(data=True):
            key = (u, v, data["type"])
            if key not in seen:
                seen.add(key)
                edge = {"source": u, "target": v, "type": data["type"]}
                if data.get("detail"):          # e.g. the dynamic calls behind an unresolved link
                    edge["detail"] = data["detail"]
                edges.append(edge)
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
