import json

from codetwin.cli import main


def test_graph_of_selected_lines(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "graph", "src/shop/price.py", "--json"]) == 0
    v = json.loads(capsys.readouterr().out)
    ids = {n["id"] for n in v["nodes"]}
    assert "tests/test_price.py" in ids and "tests/test_names.py" not in ids
    assert any(e["type"] == "runtime" for e in v["edges"])
    assert v["counts"]["tests"] == 1 and v["evidence"]["has_coverage"]

    # a line range no test executes: no runtime edge from a test to the selection
    assert main(["-C", str(toy_repo), "graph", "src/shop/price.py", "--lines", "1-1", "--json"]) == 0
    v = json.loads(capsys.readouterr().out)
    assert v["target"]["id"] == "src/shop/price.py:1-1"
    assert not any(e["type"] == "runtime" and e.get("detail") == "executes the selected lines" for e in v["edges"])


def test_graph_reports_unrecorded_and_new_files(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "graph", "src/shop/new.py", "--json"]) == 0
    v = json.loads(capsys.readouterr().out)
    assert any("new or unparsed" in u for u in v["unknowns"])
    assert any("codetwin record" in u for u in v["unknowns"])
