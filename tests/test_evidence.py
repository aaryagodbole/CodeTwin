from pathlib import Path

from codetwin.evidence import diff, static


def test_changed_lines_working_tree(toy_repo):
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 2'))
    d = diff.changed_lines(toy_repo, "HEAD")
    assert d["src/shop/price.py"].status == "M"
    assert d["src/shop/price.py"].old == [2] and d["src/shop/price.py"].new == [2]


def test_untracked_file_counts_as_added(toy_repo):
    (toy_repo / "src/shop/tax.py").write_text("RATE = 0.1\n")
    d = diff.changed_lines(toy_repo, "HEAD")
    assert d["src/shop/tax.py"].status == "A"


def test_static_facts(tmp_path: Path):
    f = tmp_path / "pkg" / "m.py"
    f.parent.mkdir()
    f.write_text("import pkg.other\n@deco\ndef f(x):\n    return getattr(x, name)\nREGISTRY = make()\n")
    facts = static.analyse_file(f, tmp_path, ["pkg"])
    assert "pkg.other" in facts.imports
    assert facts.dynamic == ["getattr-dynamic"] and facts.dyn_lines == [4]
    assert facts.defs == [[2, 4, 4]]
    assert 2 in facts.mod_lines and 5 in facts.mod_lines      # decorator and module-level call
    assert static.module_of("src/pkg/__init__.py", "src") == "pkg"
