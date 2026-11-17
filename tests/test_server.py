import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from codetwin.cli import main
from codetwin.engine import Engine
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
        # Insert a revision under repo_id=2 (a connected repo) with the same test name
        eng.store._revision("a" * 40, when=t0 + 30.0, repo=2)
        eng.store.con.execute(
            "insert or ignore into test_outcome (revision_id, test_id, recorded, passed, source) "
            "select r.id, e.id, ?, 1, 'record' from revision r, code_entity e "
            "where r.sha=? and r.repository_id=2 and e.path='tests/test_price.py' and e.repository_id=1 limit 1",
            (t0 + 31.0, "a" * 40),
        )
        eng.store.con.execute(
            "insert or ignore into test_outcome (revision_id, test_id, recorded, passed, source) "
            "select r.id, e.id, ?, 0, 'rerun' from revision r, code_entity e "
            "where r.sha=? and r.repository_id=2 and e.path='tests/test_price.py' and e.repository_id=1 limit 1",
            (t0 + 32.0, "a" * 40),
        )
        eng.store.con.commit()
    # The cross-repo SHA must NOT appear in /api/flaky
    flaky2 = c.get("/api/flaky").json()
    assert all(f["last_sha"] != "a" * 40 for f in flaky2), "cross-repo SHA must not appear in /api/flaky"

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
            if test_ent:
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

