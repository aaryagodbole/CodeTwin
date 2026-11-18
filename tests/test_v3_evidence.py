"""Semantic no-op detection, change-level risk, the promise monitor and weak-check evidence."""
import json
import subprocess

import pytest

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.evidence.noop import classify_source
from codetwin.report.promise import wilson
from codetwin.risk.change_risk import FEATURES, ChangeRiskModel


def test_classify_source():
    base = 'def f(x: int) -> int:\n    """Add one."""\n    return x + 1  # c\n'
    assert classify_source(base, 'def f(x: int) -> int:\n    """Add 1 to x."""\n\n    return x+1\n') == "noop"
    assert classify_source(base, 'def f(x: float) -> float:\n    """Add one."""\n    return x + 1\n') == "annotation"
    assert classify_source(base, 'def f(x: int) -> int:\n    return x + 2\n') == "semantic"
    assert classify_source(base, "def f(:\n") == "unparsable"
    # annotated assignments are not stripped: dataclasses read them
    assert classify_source("class A:\n    x: int = 1\n", "class A:\n    x: str = 1\n") == "semantic"


def test_change_risk_prior_and_fit():
    z = {k: 0.0 for k in FEATURES}
    m = ChangeRiskModel()
    low = m(z)
    z2 = dict(z, max_p=0.9, log_sum_p=0.7, r_prod=0.9, n_skip_file=1.0)
    assert 0 < low < m(z2) < 1 and m.source == "prior"
    assert ChangeRiskModel.fit([[z, 0]] * 10).source == "prior"            # too few labelled changes
    pts = [[z, 0]] * 30 + [[z2, 1]] * 15
    fitted = ChangeRiskModel.fit(pts)
    assert fitted.source.startswith("fitted") and fitted(z2) > fitted(z)


def test_wilson_interval():
    lo, hi = wilson(0, 0)
    assert (lo, hi) == (0.0, 1.0)
    lo, hi = wilson(5, 50)
    assert 0 < lo < 0.1 < hi < 0.3


def test_noop_and_change_risk_sections(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
    capsys.readouterr()
    p = toy_repo / "src/shop/price.py"
    p.write_text('def total(items):\n    """Sum of prices."""\n    return sum(i["price"] for i in items)  # total\n')
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["extras"]["semantic_noop"]["kind"] == "noop"
    assert 0 <= out["extras"]["change_risk"]["q"] <= 1
    assert out["extras"]["promise"]["labelled"] == 0
    assert main(["-C", str(toy_repo), "learn"]) == 0
    learned = json.loads(capsys.readouterr().out)
    assert learned["change_points"] == 1


def test_weakcheck_finds_checked_and_unchecked(toy_repo, capsys):
    (toy_repo / "src/shop/names.py").write_text(
        'def label(name):\n    return name.title()\n\n\ndef shout(name):\n    return name.upper()\n')
    (toy_repo / "tests/test_names.py").write_text(
        'from shop.names import label, shout\n\ndef test_label():\n    assert label("ada") == "Ada"\n\n'
        'def test_shout_runs():\n    shout("ada")          # executed, never checked\n')
    for cmd in (["add", "-A"], ["commit", "-q", "-m", "shout"]):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *cmd], cwd=toy_repo, check=True)
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
    capsys.readouterr()
    p = toy_repo / "src/shop/names.py"
    p.write_text(p.read_text().replace("name.title()", "name.strip().title()").replace("name.upper()", "name.strip().upper()"))
    assert main(["-C", str(toy_repo), "weakcheck", "--json"]) == 0
    res = {f["line"]: f["status"] for f in json.loads(capsys.readouterr().out)["functions"]}
    assert res == {1: "checked", 5: "unchecked"}


def test_mutate_keeps_header_of_one_line_functions():
    from codetwin.evidence.weakcheck import _mutate
    src = "def f(x): return x + 1\n\n\ndef g(x):\n    y = x\n    return y\n"
    assert _mutate(src, 1, 1, 1) == "def f(x): return None\n\n\ndef g(x):\n    y = x\n    return y\n"
    assert _mutate(src, 4, 5, 6) == "def f(x): return x + 1\n\n\ndef g(x):\n    return None\n"
    assert _mutate(src, 4, 2, 6) is None                       # no function there: reported as error


def _commit(repo, msg):
    for cmd in (["add", "-A"], ["commit", "-q", "-m", msg]):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *cmd], cwd=repo, check=True)


def test_weakcheck_baseline_failures_and_added_files(toy_repo, capsys):
    (toy_repo / "src/shop/names.py").write_text('def shout(name):\n    return name.upper()\n')
    (toy_repo / "tests/test_names.py").write_text(
        'from shop.names import shout\n\ndef test_shout_runs():\n    shout("ada")\n\n'
        'def test_already_broken():\n    shout("ada")\n    assert False\n')
    _commit(toy_repo, "names")
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
    capsys.readouterr()
    p = toy_repo / "src/shop/names.py"
    p.write_text(p.read_text().replace("name.upper()", "name.strip().upper()"))
    (toy_repo / "src/shop/extra.py").write_text("def new_fn():\n    return 1\n")      # added file
    assert main(["-C", str(toy_repo), "weakcheck", "--json"]) == 0
    res = {f["file"]: f for f in json.loads(capsys.readouterr().out)["functions"]}
    # the pre-existing failure must not count as catching the mutant
    assert res["src/shop/names.py"]["status"] == "error"
    assert res["src/shop/names.py"]["baseline_failures"] == ["tests/test_names.py"]
    assert res["src/shop/extra.py"]["status"] == "untested"


def test_weakcheck_unrecorded_base(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
    (toy_repo / "README.md").write_text("x\n")
    _commit(toy_repo, "readme")
    with pytest.raises(SystemExit, match="no recorded run"):      # HEAD is a valid commit, but not recorded
        main(["-C", str(toy_repo), "weakcheck", "--base", "HEAD"])


def test_learn_ignores_features_of_another_decision(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
        p = toy_repo / "src/shop/price.py"
        p.write_text(p.read_text() + "\n# note\n")
        eng.select()
        eng.store.set_state("pending_change_features", {"base": "other", "mode": "calibrated", "selected": [],
                                                        "features": {k: 0.0 for k in FEATURES}})
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "learn"]) == 0
    assert "change_points" not in json.loads(capsys.readouterr().out)
