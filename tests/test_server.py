import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.evidence import model
from codetwin.server.app import create_app


def test_api_reads_evidence(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
        p = toy_repo / "src/shop/price.py"
        p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
        eng.select()
        eng.learn()

    c = TestClient(create_app(toy_repo))
    assert c.get("/api/health").json()["status"] == "ok"
    s = c.get("/api/summary").json()
    assert s["test_files"] == 2 and s["decisions"] == 1 and s["labelled_decisions"] == 1
    d = c.get("/api/decisions").json()
    assert d[0]["missed"] is False and "tests/test_price.py" in d[0]["selected"]
    cal = c.get("/api/calibration").json()
    assert cal["labelled"] == 1 and cal["points"][0]["observed_miss_rate"] == 0.0
    m = c.get("/api/map").json()
    kinds = {n["id"]: n["kind"] for n in m["nodes"]}
    assert kinds["tests/test_price.py"] == "test" and kinds["src/shop/price.py"] == "source"
    assert any(e["type"] == "runtime" for e in m["edges"])
    g = c.get("/api/graph", params={"file": "src/shop/price.py", "lines": "1-2"}).json()
    assert g["counts"]["tests"] == 1
    assert c.get("/api/graph", params={"file": "src/shop/price.py", "lines": "x"}).status_code == 400
    st = c.get("/api/llm").json()
    assert [p["name"] for p in st["providers"]] == ["groq", "gemini"]
    assert all("key" not in p or p["key"] is None for p in st["providers"])


def test_decision_detail_and_flaky_and_kg(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    c = TestClient(create_app(toy_repo))
    assert c.get("/api/kg").status_code == 404
    assert c.get("/api/flaky").json() == []

    with Engine(toy_repo) as eng:
        eng.record()
        p = toy_repo / "src/shop/price.py"
        p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
        eng.select()
        sha = eng.store.latest_run_sha()
        eng.store.add_outcomes(sha, {"tests/test_price.py": []}, source="record")
        eng.store.add_outcomes(sha, {"tests/test_price.py": ["case"]}, source="rerun")

    c = TestClient(create_app(toy_repo))

    flaky = c.get("/api/flaky").json()
    assert len(flaky) == 1
    assert flaky[0]["test"] == "tests/test_price.py"
    assert flaky[0]["passes"] >= 1 and flaky[0]["failures"] >= 1
    assert flaky[0]["commits"] == 1
    assert flaky[0]["last_sha"] == sha

    # Regression: last_sha is chronologically newest (not alphabetically first)
    t0 = time.time()
    with Engine(toy_repo) as eng:
        eng.store._revision("f" * 40, when=t0 + 10.0)   # older in time
        eng.store._revision("0" * 40, when=t0 + 20.0)   # newer in time
        for s in ("f" * 40, "0" * 40):
            eng.store.add_outcomes(s, {"tests/test_price.py": []}, "record")
            eng.store.add_outcomes(s, {"tests/test_price.py": ["c"]}, "rerun")
    assert c.get("/api/flaky").json()[0]["last_sha"] == "0" * 40

    # Regression: flaky_tests() must not include results from other repositories
    with Engine(toy_repo) as eng:
        # Register a connected repo and insert a revision under it
        repo2_id = eng.store.repository("other-repo")
        rev2_id = eng.store._revision("a" * 40, when=t0 + 30.0, repo=repo2_id)
        # Use the store's own transaction helper so isolation/WAL mode is correct
        with eng.store._tx():
            test_ent = eng.store.con.execute(
                "select id from code_entity where path='tests/test_price.py' and repository_id=1"
            ).fetchone()
            assert test_ent, "test setup: tests/test_price.py must be a known entity"
            eng.store.con.execute(
                "insert into test_outcome (revision_id, test_id, recorded, passed, source)"
                " values (?,?,?,1,'record')",
                (rev2_id, test_ent[0], t0 + 31.0),
            )
            eng.store.con.execute(
                "insert into test_outcome (revision_id, test_id, recorded, passed, source)"
                " values (?,?,?,0,'rerun')",
                (rev2_id, test_ent[0], t0 + 32.0),
            )
    # The cross-repo SHA must NOT appear in /api/flaky
    flaky2 = c.get("/api/flaky").json()
    assert all(f["last_sha"] != "a" * 40 for f in flaky2), "cross-repo SHA must not appear in /api/flaky"

    d = c.get("/api/decisions/1").json()
    assert d["id"] == 1
    assert "scores" in d
    assert "tests/test_price.py" in d["scores"]
    assert c.get("/api/decisions/999").status_code == 404

    # /api/decisions list must also have NaN→null and default lists
    decisions_list = c.get("/api/decisions").json()
    assert len(decisions_list) >= 1
    for dec in decisions_list:
        assert "selected" in dec and "reasons" in dec

    kg = c.get("/api/kg").json()
    assert "nodes" in kg and "edges" in kg and "stats" in kg
    kinds = {n["kind"] for n in kg["nodes"]}
    assert "symbol" in kinds
    assert any(n["id"].startswith("symbol:") for n in kg["nodes"])

    kg_no_sym = c.get("/api/kg", params={"symbols": "false"}).json()
    kinds_no_sym = {n["kind"] for n in kg_no_sym["nodes"]}
    assert "symbol" not in kinds_no_sym
    assert all("::" not in n["id"] for n in kg_no_sym["nodes"])
    assert kg_no_sym["stats"]["nodes"] < kg["stats"]["nodes"]

    # Regression: cache invalidated after re-recording same SHA
    (toy_repo / "tests" / "test_extra.py").write_text("def test_extra(): assert 1 == 1\n")
    with Engine(toy_repo) as eng:
        eng.record()
    kg_updated = c.get("/api/kg").json()
    assert kg_updated["stats"]["nodes"] > kg["stats"]["nodes"]



def test_map_edges_carry_the_detail_of_unresolved_links(toy_repo: Path) -> None:
    """The dashboard says what could not be resolved, so /api/map keeps the edge detail (e.g. the dynamic calls)."""
    (toy_repo / "src/shop/dyn.py").write_text("def call(obj, name):\n    return getattr(obj, name)()\n")
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
    edges = TestClient(create_app(toy_repo)).get("/api/map").json()["edges"]
    unresolved = [e for e in edges if e["type"] == "unresolved"]
    assert unresolved, "test setup: a dynamic call must give an unresolved link"
    assert all(e.get("detail") for e in unresolved)


def test_runs_list_and_detail(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    c = TestClient(create_app(toy_repo))
    assert c.get("/api/runs").json() == []
    assert c.get("/api/runs/doesnotexist").status_code == 404

    with Engine(toy_repo) as eng:
        eng.record()
        sha1 = eng.store.latest_run_sha()
    assert sha1 is not None

    runs = c.get("/api/runs").json()
    assert len(runs) == 1
    assert runs[0]["sha"] == sha1
    assert runs[0]["test_files"] == 2
    assert runs[0]["failing"] == 0
    assert isinstance(runs[0]["suite_seconds"], float)
    assert runs[0]["covered_files"] >= 1
    assert runs[0]["latest"] is True

    detail1 = c.get(f"/api/runs/{sha1}").json()
    assert detail1["sha"] == sha1
    assert detail1["latest"] is True
    assert detail1["failing"] == []
    assert "tests/test_price.py" in detail1["durations"]
    assert c.get("/api/runs/nonexistent").status_code == 404
    assert c.post("/api/runs").status_code == 405

    sha2 = "b" * 40
    with Engine(toy_repo) as eng:
        eng.store.save_run(
            model.TestRun(
                sha=sha2,
                durations={"tests/test_fast.py": 0.1, "tests/test_slow.py": 2.5, "tests/test_mid.py": 0.8},
                failing=["tests/test_slow.py::test_fail"],
                covered={
                    "tests/test_fast.py": {"src/shop/price.py": [1, 2]},
                    "tests/test_slow.py": {"src/shop/price.py": [2, 3], "src/shop/tax.py": [1]},
                },
                wall=3.4,
            ),
            recorded=time.time() + 10.0,
        )

    runs2 = c.get("/api/runs").json()
    assert [r["sha"] for r in runs2] == [sha2, sha1]
    assert runs2[0]["latest"] is True and runs2[1]["latest"] is False
    assert runs2[0]["test_files"] == 3
    assert runs2[0]["failing"] == 1
    assert runs2[0]["suite_seconds"] == pytest.approx(3.4)
    assert runs2[0]["covered_files"] == 2

    detail2 = c.get(f"/api/runs/{sha2}").json()
    assert list(detail2["durations"].keys()) == ["tests/test_slow.py", "tests/test_mid.py", "tests/test_fast.py"]
    assert detail2["failing"] == ["tests/test_slow.py::test_fail"]
    assert detail2["latest"] is True
    assert c.get(f"/api/runs/{sha1}").json()["latest"] is False

    # Empty run (0 tests, 0 covered files) is handled cleanly
    sha3 = "c" * 40
    with Engine(toy_repo) as eng:
        eng.store.save_run(model.TestRun(sha=sha3, wall=0.0), recorded=time.time() + 20.0)
    detail3 = c.get(f"/api/runs/{sha3}").json()
    assert detail3["test_files"] == 0
    assert detail3["covered_files"] == 0
    assert detail3["durations"] == {}
    assert detail3["failing"] == []
    assert detail3["latest"] is True
