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
