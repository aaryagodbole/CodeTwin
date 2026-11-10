from codetwin import config
from codetwin.cli import main
from codetwin.engine import Engine


def test_record_select_learn(toy_repo, capsys):
    assert main(["-C", str(toy_repo), "init"]) == 0
    cfg = config.load(toy_repo)
    assert cfg.packages == ["shop"] and cfg.src_root == "src"
    eng = Engine(toy_repo)
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
