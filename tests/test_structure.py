"""The extension points that let features be added without editing shared files."""
import json

from codetwin import config
from codetwin.cli import build_parser, main
from codetwin.plugins import discover
from codetwin.store.db import Store


def test_commands_and_tools_are_discovered():
    names = [m.NAME for m in discover("codetwin.commands")]
    assert {"init", "record", "select", "learn", "impact", "explain"} <= set(names)
    for m in discover("codetwin.commands"):
        assert callable(m.run) and callable(m.add_arguments) and m.HELP
    for m in discover("codetwin.mcp_tools"):
        assert callable(m.register)
    for m in discover("codetwin.report"):
        assert m.NAME and callable(m.contribute)
    assert "select" in build_parser().format_help()


def test_migrations_apply_once(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        names = [r[0] for r in s.con.execute("select name from migrations")]
    assert "0001_initial.sql" in names
    with Store(tmp_path / "e.sqlite") as s:
        assert s.migrate() == []                                   # second open applies nothing


def test_select_json_has_contract_and_report_sections(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == 1
    assert {"decision", "residual_risk", "selected", "reasons", "extras"} <= set(out)
    assert out["extras"]["changed_files"]["files"] == {"src/shop/price.py": 1}


def test_feature_reads_its_own_config_section(toy_repo):
    main(["-C", str(toy_repo), "init"])
    path = toy_repo / ".codetwin.toml"
    path.write_text(path.read_text() + '\n[crossrepo]\nrepos = ["../app"]\n')
    assert config.load(toy_repo).section("crossrepo") == {"repos": ["../app"]}
    assert config.load(toy_repo).section("missing") == {}
