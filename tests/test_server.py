import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.server.app import create_app


def test_api_reads_evidence(toy_repo):
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


def test_decision_detail_and_flaky_and_kg(toy_repo):
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

    d = c.get("/api/decisions/1").json()
    assert d["id"] == 1
    assert "scores" in d
    assert "tests/test_price.py" in d["scores"]
    assert c.get("/api/decisions/999").status_code == 404

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
