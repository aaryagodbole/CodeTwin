"""Failure triage: outcome history, suspect commits, likely cause, JUnit import."""
import json
import subprocess

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.triage import triage
from codetwin.triage.junit import read


def _commit(repo, msg):
    for cmd in (["add", "-A"], ["commit", "-qm", msg]):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *cmd], cwd=repo, check=True,
                       capture_output=True)


def test_regression_is_traced_to_the_commit_that_changed_executed_lines(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    _commit(toy_repo, "config")
    with Engine(toy_repo) as eng:
        eng.record()                                            # passing
    n = toy_repo / "src/shop/names.py"
    n.write_text(n.read_text() + "\n\ndef shout(x):\n    return x.upper()\n")
    _commit(toy_repo, "add shout")                              # unrelated to test_price
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] + 1'))
    _commit(toy_repo, "break total")
    with Engine(toy_repo) as eng:
        run = eng.record()
    assert any(c.startswith("tests/test_price.py") for c in run.failing)
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "why", "tests/test_price.py", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "failing" and out["hypothesis"] == "regression"
    assert [s["title"].split(" ", 1)[1] for s in out["suspects"]][:2] == ["break total", "add shout"]
    assert "lines of src/shop/price.py that the test executed" in out["suspects"][0]["reasons"][0]
    assert out["suspects"][1]["score"] == 0
    assert [h["passed"] for h in out["timeline"]] == [True, False]

    capsys.readouterr()
    assert main(["-C", str(toy_repo), "why", "tests/test_names.py", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passing"


def test_flaky_and_unknown(toy_repo):
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        sha = eng.head()
        eng.store.add_outcomes(sha, {"tests/test_price.py": []}, "ci", when=1.0)
        eng.store.add_outcomes(sha, {"tests/test_price.py": ["tests/test_price.py::test_total"]}, "ci", when=2.0)
        out = triage(eng.root, eng.store, eng.facts_now(), "tests/test_price.py")
        assert out["hypothesis"] == "flaky" and "same commit" in out["evidence"][0]
        none = triage(eng.root, eng.store, eng.facts_now(), "tests/test_other.py")
        assert none["status"] == "unknown" and "no recorded outcome" in none["unknowns"][0]


def test_rerun_counts(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "why", "tests/test_names.py", "--rerun", "2", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["evidence"] == ["reran 2 times: 2 passed, 0 failed"]
    assert [h["source"] for h in out["timeline"]] == ["rerun", "rerun"]


def test_junit_import_maps_cases_to_files(tmp_path, toy_repo, capsys):
    xml = tmp_path / "r.xml"
    xml.write_text('<testsuites><testsuite name="s">'
                   '<testcase classname="tests.test_price" name="test_total"><failure message="x"/></testcase>'
                   '<testcase classname="x" name="t" file="tests/test_names.py"/>'
                   '<testcase classname="com.acme.Unknown" name="z"/>'
                   '</testsuite></testsuites>')
    got, unmapped = read([xml], ["tests/test_price.py", "tests/test_names.py"])
    assert got == {"tests/test_price.py": ["tests/test_price.py::test_total"], "tests/test_names.py": []}
    assert unmapped == ["com.acme.Unknown::z"]
    main(["-C", str(toy_repo), "init"])
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "outcomes", "import", str(xml)]) == 0
    assert "2 test files (1 failing)" in capsys.readouterr().out
    with Engine(toy_repo) as eng:
        assert eng.store.outcomes("tests/test_price.py")[0]["source"] == "ci"
