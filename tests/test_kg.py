import json
import xml.etree.ElementTree as ET

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.evidence.model import FileFacts
from codetwin.evidence.model import TestRun as Run
from codetwin.kg import EdgeKind, NodeKind, build, from_engine
from codetwin.kg.export import to_json, write
from codetwin.kg.schema import node_id


def _toy():
    static = {
        "src/a.py": FileFacts(deps=[], symbols=[["f", "function", 1, 3], ["C", "class", 5, 9], ["C.m", "method", 6, 9]]),
        "src/b.py": FileFacts(deps=["src/a.py"], symbols=[["g", "function", 1, 2]], dynamic=["getattr"], dyn_lines=[2]),
        "tests/test_b.py": FileFacts(deps=["src/b.py"]),
    }
    run = Run("abc", durations={"tests/test_b.py": 0.1},
                  covered={"tests/test_b.py": {"src/b.py": [1, 2], "src/a.py": [2, 7]}})
    history = [["src/a.py", "src/b.py"], ["src/a.py", "src/b.py"], ["src/a.py", "README.md"]]
    return build(static, run, history, is_test=lambda p: p.startswith("tests/"))


def test_nodes_and_typed_edges():
    kg = _toy()
    st = kg.stats()
    assert st["node_kinds"] == {"file": 2, "repository": 1, "symbol": 4, "test": 1, "unknown": 1}
    assert node_id(NodeKind.TEST, "tests/test_b.py") in kg.g
    covers = {(u, v) for u, v, _ in kg.edges(EdgeKind.COVERS)}
    assert (node_id(NodeKind.TEST, "tests/test_b.py"), node_id(NodeKind.SYMBOL, "src/a.py::f")) in covers
    assert (node_id(NodeKind.TEST, "tests/test_b.py"), node_id(NodeKind.SYMBOL, "src/a.py::C.m")) in covers
    co = kg.edges(EdgeKind.CO_CHANGES)
    assert len(co) == 2 and all(d["commits"] == 2 for _, _, d in co)   # a<->b twice; README is not a project file
    assert all(d["evidence"] for _, _, d in kg.edges())                # every edge says what evidence it is


def test_blast_radius_follows_imports_and_keeps_unknowns():
    kg = _toy()
    br = kg.blast_radius({"src/a.py": [7]})
    assert br.symbols == [node_id(NodeKind.SYMBOL, "src/a.py::C.m")]       # innermost symbol only
    assert br.files == {"src/b.py": ["src/b.py", "src/a.py"]}
    assert br.tests == {"tests/test_b.py": ["runtime"]}
    assert any("dynamic calls (getattr)" in u for u in br.unknowns)       # unknown is not "no dependency"
    assert kg.blast_radius({"src/new.py": [1]}).unknowns == ["src/new.py: not in the graph (new or unparsed file)"]
    assert set(kg.symbols_at("src/a.py", [])) == {node_id(NodeKind.SYMBOL, "src/a.py::f"),
                                                  node_id(NodeKind.SYMBOL, "src/a.py::C")}
    assert "tests/test_b.py" in kg.context({"src/a.py": [7]})


def test_exports(tmp_path):
    kg = _toy()
    data = to_json(kg)
    assert data["stats"]["edges"] == kg.g.number_of_edges() and len(data["links"]) == kg.g.number_of_edges()
    json.loads(write(kg, tmp_path / "g.json").read_text())
    root = ET.parse(write(kg, tmp_path / "g.graphml", "graphml")).getroot()   # noqa: S314 (file written by the test)
    assert root.tag.endswith("graphml")


def test_from_engine_and_cli(toy_repo, capsys, tmp_path):
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
        kg = from_engine(eng)
    assert node_id(NodeKind.SYMBOL, "src/shop/price.py::total") in kg.g
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "kg", "blast", "src/shop/price.py"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["tests"] == {"tests/test_price.py": ["runtime"]}
    assert main(["-C", str(toy_repo), "kg", "export", "--format", "graphml", "-o", str(tmp_path / "x.graphml")]) == 0
    assert main(["-C", str(toy_repo), "kg", "stats"]) == 0
