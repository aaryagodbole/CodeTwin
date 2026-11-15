"""Symbol-level impact: symbols from both adapters, callers, tests that execute a symbol, unknowns."""
import json
import textwrap

import pytest

from codetwin.cli import main
from codetwin.config import Config
from codetwin.engine import Engine
from codetwin.evidence.model import FileDiff, FileFacts, TestRun
from codetwin.evidence.static import analyse_file
from codetwin.graph.symbols import Symbol, changed_symbols, find, parse_target, symbol_impact


def test_python_symbols_are_qualified(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("class A:\n    @staticmethod\n    def f():\n        return 1\n\ndef g():\n    def inner():\n        pass\n")
    syms = analyse_file(f, tmp_path, []).symbols
    assert ["A", "class", 1, 4] in syms
    assert ["A.f", "method", 2, 4] in syms              # the span starts at the decorator
    assert ["g.inner", "function", 7, 8] in syms


def test_parse_target_and_find():
    assert parse_target("src/a.py:Parser.parse") == ("src/a.py", "Parser.parse")
    assert parse_target("src/a.py") == ("src/a.py", None)
    assert parse_target(r"C:\repo\a.py") == (r"C:\repo\a.py", None)
    facts = {"a.py": FileFacts(symbols=[["P", "class", 1, 9], ["P.parse", "method", 2, 4], ["P.run", "method", 5, 9]])}
    assert [s.name for s in find(facts, "a.py", "parse")] == ["P.parse"]
    assert [s.name for s in find(facts, "a.py", "P.run")] == ["P.run"]
    assert [s.name for s in find(facts, "a.py", "3")] == ["P.parse"]       # innermost symbol at a line
    assert find(facts, "a.py", "missing") == []


def test_symbol_impact_runtime_callers_and_unknowns(tmp_path):
    (tmp_path / "lib.py").write_text("def add(a, b):\n    return a + b\n\ndef unused():\n    return 0\n")
    (tmp_path / "use.py").write_text("from lib import add\n\ndef twice(x):\n    return add(x, x)\n")
    (tmp_path / "dyn.py").write_text("import lib\nf = getattr(lib, name)\n")
    facts = {"lib.py": FileFacts(symbols=[["add", "function", 1, 2], ["unused", "function", 4, 5]]),
             "use.py": FileFacts(deps=["lib.py"], symbols=[["twice", "function", 3, 4]]),
             "dyn.py": FileFacts(deps=["lib.py"], dynamic=["getattr-dynamic"])}
    run = TestRun(sha="x", covered={"t_lib.py": {"lib.py": [1, 2]}, "t_use.py": {"use.py": [1, 3, 4]}})
    add = Symbol("add", "function", "lib.py", 1, 2)
    imp = symbol_impact(tmp_path, facts, run, ["t_lib.py", "t_use.py"], add).to_dict()
    assert imp["tests"]["t_lib.py"] == ["runtime"]
    assert any(c == {"file": "use.py", "line": 4, "symbol": "twice"} for c in imp["callers"])
    assert "via-caller:runtime" in imp["tests"]["t_use.py"]
    assert any("dyn.py" in u and "dynamic" in u for u in imp["unknowns"])   # unknown is not "no dependency"

    gap = symbol_impact(tmp_path, facts, run, [], Symbol("unused", "function", "lib.py", 4, 5)).to_dict()
    assert gap["tests"] == {} and any("test gap" in u for u in gap["unknowns"])
    norun = symbol_impact(tmp_path, facts, None, [], add).to_dict()
    assert any("no recorded test run" in u for u in norun["unknowns"])


def test_changed_symbols_keeps_innermost():
    facts = {"a.py": FileFacts(symbols=[["P", "class", 1, 9], ["P.parse", "method", 2, 4], ["P.run", "method", 5, 9]])}
    run = TestRun(sha="x", covered={"t.py": {"a.py": [3]}})
    out = changed_symbols(facts, {"a.py": FileDiff("M", "a.py", [3], [3])}, run)
    assert [(s["name"], s["tests_before"]) for s in out] == [("P.parse", 1)]


def test_cli_impact_symbol_end_to_end(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        eng.record()
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "impact", "src/shop/price.py:total", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["symbol"]["name"] == "total"
    assert "runtime" in out["tests"]["tests/test_price.py"]
    assert "tests/test_names.py" not in out["tests"]
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    with Engine(toy_repo) as eng:
        d = eng.select()
    syms = d.extras["changed_symbols"]["symbols"]
    assert [(s["name"], s["tests_before"]) for s in syms] == [("total", 1)]


def test_tree_sitter_symbols_for_other_languages(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from codetwin import lang
    (tmp_path / "src").mkdir()
    files = {"javascript": ("src/a.js", "export class Parser {\n  parse(x) {\n    return x;\n  }\n}\n"
                                         "const mul = (a, b) => a * b;\n"),
             "go": ("src/b.go", "package m\n\ntype S struct{}\n\nfunc (s *S) Run() int {\n\treturn 1\n}\n"),
             "rust": ("src/c.rs", "pub struct P;\nimpl P {\n    pub fn go(&self) -> i32 {\n        1\n    }\n}\n"),
             "java": ("src/D.java", "package x;\npublic class D {\n  int f() {\n    return 1;\n  }\n}\n")}
    want = {"javascript": {"Parser.parse", "mul"}, "go": {"S.Run"}, "rust": {"P.go"}, "java": {"D.f"}}
    for name, (path, text) in files.items():
        (tmp_path / path).write_text(textwrap.dedent(text))
        a = lang.get(Config(root=tmp_path, language=name, source_dirs=["src"], tests_dir="test", raw={}))
        got = {s[0] for s in a.file_facts(path, (tmp_path / path).read_bytes())[0].symbols}
        assert want[name] <= got, (name, got)


# ------------------------------------------------------------------ review fixes (PR #38)
def test_recorded_coverage_is_matched_on_the_recorded_lines(tmp_path):
    """Ten lines inserted above `add` since the recorded run: its coverage is at the old lines."""
    (tmp_path / "lib.py").write_text("\n" * 10 + "def add(a, b):\n    return a + b\n")
    now = {"lib.py": FileFacts(symbols=[["add", "function", 11, 12], ["new", "function", 1, 2]])}
    base = {"lib.py": FileFacts(symbols=[["add", "function", 1, 2], ["other", "function", 11, 12]])}
    run = TestRun(sha="x", covered={"t_add.py": {"lib.py": [1, 2]}, "t_other.py": {"lib.py": [11, 12]}})
    add = Symbol("add", "function", "lib.py", 11, 12)
    imp = symbol_impact(tmp_path, now, run, ["t_add.py", "t_other.py"], add, base_facts=base).to_dict()
    assert list(imp["tests"]) == ["t_add.py"]                          # not the test of the code now at 11-12
    new = symbol_impact(tmp_path, now, run, [], Symbol("new", "function", "lib.py", 1, 2), base_facts=base).to_dict()
    assert new["tests"] == {} and any("did not exist at the recorded commit" in u for u in new["unknowns"])
    out = changed_symbols(now, {"lib.py": FileDiff("M", "lib.py", [], [11])}, run, base_facts=base)
    assert [(s["name"], s["tests_before"]) for s in out] == [("add", 1)]
    assert any("no static snapshot" in u for u in symbol_impact(tmp_path, now, run, [], add).to_dict()["unknowns"])


def test_partly_parsed_file_is_an_unknown(tmp_path):
    facts = {"a.js": FileFacts(dynamic=["parse-error"], symbols=[["f", "function", 1, 2]])}
    imp = symbol_impact(tmp_path, facts, None, [], Symbol("f", "function", "a.js", 1, 2)).to_dict()
    assert any("syntax errors" in u for u in imp["unknowns"])
