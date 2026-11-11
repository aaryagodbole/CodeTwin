import pytest

from codetwin import config
from codetwin.cli import main
from codetwin.engine import Engine


def test_record_select_learn(toy_repo, capsys):
    assert main(["-C", str(toy_repo), "init"]) == 0
    cfg = config.load(toy_repo)
    assert cfg.packages == ["shop"] and cfg.src_root == "src"
    with Engine(toy_repo) as eng:
        _record_select_learn(eng, toy_repo)


def _record_select_learn(eng, toy_repo):
    run = eng.record()
    assert set(run.covered) == {"tests/test_price.py", "tests/test_names.py"}

    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    d = eng.select()
    assert "tests/test_price.py" in d.selected
    assert "tests/test_names.py" not in d.selected
    assert d.decision in ("proceed", "abstain")

    out = eng.learn()
    assert out["affected"] == ["tests/test_price.py"] and out["missed"] == []
    assert out["calibration_size"] == 1

    imp = eng.impact(["src/shop/price.py"])
    assert "tests/test_price.py" in imp.tests

    with pytest.raises(RuntimeError, match="already has an outcome"):
        eng.learn()                              # one change must not be counted twice


def test_budget_mode_does_not_move_adaptive_level(toy_repo):
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
        p = toy_repo / "src/shop/price.py"
        p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
        eng.select(budget=0.01)
        eng.learn()
        assert eng.store.get_state("alpha_t") is None          # level untouched by budget-mode outcomes
        assert len(eng.store.get_state("calibration")) == 1    # labels still collected
