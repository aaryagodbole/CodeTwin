"""Cross-repository impact: package names per ecosystem, consumers in dependents, tests, unknowns."""
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from codetwin.cli import main
from codetwin.crossrepo import packages as pk
from codetwin.engine import Engine


def _git_init(r: Path) -> None:
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *cmd], cwd=r, check=True, capture_output=True)


def test_package_detection_per_ecosystem(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "@acme/core"}')
    (tmp_path / "go.mod").write_text("module github.com/acme/core\n\ngo 1.22\n")
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "acme-core"\n')
    (tmp_path / "composer.json").write_text('{"autoload": {"psr-4": {"Acme\\\\Core\\\\": "src/"}}}')
    (tmp_path / "pom.xml").write_text("<project/>")
    (tmp_path / "src/main/java/com/acme/core").mkdir(parents=True)
    (tmp_path / "src/main/java/com/acme/core/A.java").write_text("package com.acme.core;\nclass A {}\n")
    got = pk.detect(tmp_path, ["acme"])
    for want in ("acme", "@acme/core", "github.com/acme/core", "acme-core", "acme_core", "Acme\\Core", "com.acme"):
        assert want in got, (want, got)


def test_import_matching():
    assert pk.matches("shop.price", "shop") and pk.matches("shop", "shop")
    assert not pk.matches("shopping.cart", "shop")
    assert pk.matches("@acme/core/util", "@acme/core") and pk.matches("'@acme/core'", "@acme/core")
    assert pk.matches("github.com/acme/core/pkg", "github.com/acme/core")
    assert pk.matches("acme_core::parse", "acme_core") and pk.matches("com.acme.core.A", "com.acme")


@pytest.fixture
def app_repo(tmp_path) -> Path:
    """A dependent of the toy library: one module uses shop.price.total, one only imports shop."""
    a = tmp_path / "app"
    (a / "app").mkdir(parents=True)
    (a / "tests").mkdir()
    (a / "app" / "__init__.py").write_text("")
    (a / "app" / "checkout.py").write_text(textwrap.dedent('''\
        from shop.price import total
        def pay(items):
            return total(items) * 2
        '''))
    (a / "app" / "greet.py").write_text("import shop\n\ndef hello():\n    return 'hi'\n")
    (a / "app" / "plugins.py").write_text("import importlib\nmod = importlib.import_module(name)\n")
    (a / "app" / "other.py").write_text("def nothing():\n    return 0\n")
    (a / "tests" / "test_checkout.py").write_text("from app.checkout import pay\n\ndef test_pay():\n    assert pay is not None\n")
    (a / "tests" / "test_other.py").write_text("from app.other import nothing\n\ndef test_other():\n    assert nothing() == 0\n")
    _git_init(a)
    main(["-C", str(a), "init"])
    return a


def test_change_in_library_reaches_dependent(toy_repo, app_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + f'\n[[repos]]\nname = "app"\npath = "{app_repo.as_posix()}"\n\n'
                   '[[repos]]\nname = "gone"\npath = "../does-not-exist"\n')
    with Engine(toy_repo) as eng:
        eng.record()
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "crossrepo", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["changed_symbols"] == ["total"] and "shop" in out["packages"]
    app = next(r for r in out["repos"] if r["name"] == "app")
    cons = {c["file"]: c for c in app["consumers"]}
    assert cons["app/checkout.py"]["link"] == "uses-changed-symbol" and cons["app/checkout.py"]["lines"] == [1, 3]
    assert cons["app/greet.py"]["link"] == "imports-package"
    assert "app/other.py" not in cons
    assert "tests/test_checkout.py" in app["tests"] and "tests/test_other.py" not in app["tests"]
    assert any("dynamic" in u for u in app["unknowns"])               # plugins.py may use shop without importing it
    assert any("no recorded run" in u for u in app["unknowns"])
    gone = next(r for r in out["repos"] if r["name"] == "gone")
    assert any("not found" in u for u in gone["unknowns"])

    with Engine(toy_repo) as eng:
        d = eng.select()
    assert d.extras["cross_repo"]["repos"][0]["name"] == "app"

    # both analyses are stored, with the dependent's commit and everything the output showed
    from codetwin.store.analyses import crossrepo_history, resolve_sha
    with Engine(toy_repo) as eng:
        st = eng.store
        hist = crossrepo_history(st)
        assert len(hist) == 2 and hist[0]["id"] == d.extras["cross_repo"]["analysis_id"] == hist[1]["id"] + 1
        assert hist[1]["id"] == out["analysis_id"]
        repos = {r["name"]: r for r in hist[0]["repos"]}
        assert repos["app"]["status"] == "analysed" and repos["app"]["revision"] == resolve_sha(app_repo, "HEAD")
        assert repos["app"]["consumers"] == len(app["consumers"]) and repos["app"]["tests"] == len(app["tests"])
        assert repos["gone"]["status"] == "not-found" and repos["gone"]["revision"] is None
        uses = st.con.execute("select s.symbol, s.line from consumer_symbol_use s join consumer_file c on c.id = "
                              "s.consumer_id join code_entity f on f.id = c.file_id where f.path='app/checkout.py' and "
                              "c.target_id = (select t.id from analysis_target t join repository r on r.id = "
                              "t.repository_id where r.name='app' and t.analysis_id=?)", (hist[0]["id"],)).fetchall()
        assert sorted(uses) == [("total", 1), ("total", 3)]
        sym = st.con.execute("select e.name, e.kind, e.path from analysis_changed_symbol a join code_entity e on "
                             "e.id = a.entity_id where a.analysis_id=?", (out["analysis_id"],)).fetchall()
        assert sym == [("total", "function", "src/shop/price.py")]
        rel = set(st.con.execute("select source, type, target from repository_relation"))
        assert {("app", "dependsOn", "."), ("gone", "dependsOn", "."), (".", "providesPackage", "shop")} <= rel
        assert repos["app"]["consumers"] > 0
        # app's files live in app's namespace: same path in two repositories is two entities
        assert st.con.execute("select count(distinct repository_id) from code_entity where path like 'app/%'"
                              ).fetchone()[0] == 1
        n_unk = st.con.execute("select count(*) from analysis_unknown where analysis_id=?", (out["analysis_id"],)).fetchone()[0]
        assert n_unk == sum(len(r["unknowns"]) for r in out["repos"])
        assert st.con.execute("pragma foreign_key_check").fetchall() == []


def test_no_connected_repositories(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "crossrepo"]) == 0
    assert "no connected repositories" in capsys.readouterr().out


def test_javascript_dependent(tmp_path, toy_repo, capsys):
    pytest.importorskip("tree_sitter_language_pack")
    lib = tmp_path / "lib"
    (lib / "src").mkdir(parents=True)
    (lib / "test").mkdir()
    (lib / "package.json").write_text('{"name": "@acme/money", "scripts": {"test": "jest"}}')
    (lib / "src" / "money.js").write_text("export function round(x) {\n  return Math.round(x);\n}\n")
    (lib / "test" / "money.test.js").write_text("import { round } from '../src/money';\ntest('r', () => round(1));\n")
    web = tmp_path / "web"
    (web / "src").mkdir(parents=True)
    (web / "test").mkdir()
    (web / "package.json").write_text('{"name": "web", "scripts": {"test": "jest"}}')
    (web / "src" / "cart.js").write_text("import { round } from '@acme/money';\nexport const sum = (a) => round(a);\n")
    (web / "test" / "cart.test.js").write_text("import { sum } from '../src/cart';\ntest('s', () => sum(1));\n")
    _git_init(web)
    (lib / ".codetwin.toml").write_text('[project]\nlanguage = "javascript"\nsource_dirs = ["src"]\ntests_dir = "test"\n'
                                        '\n[[repos]]\nname = "web"\npath = "../web"\n')
    _git_init(lib)
    m = lib / "src" / "money.js"
    m.write_text(m.read_text().replace("Math.round(x)", "Math.round(x * 100) / 100"))
    capsys.readouterr()
    assert main(["-C", str(lib), "crossrepo", "--json", "--base", "HEAD"]) == 0
    out = json.loads(capsys.readouterr().out)
    web_r = out["repos"][0]
    assert web_r["language"] == "javascript"
    assert web_r["consumers"][0]["file"] == "src/cart.js" and web_r["consumers"][0]["symbols"] == ["round"]
    assert "test/cart.test.js" in web_r["tests"]


# ------------------------------------------------------------------ review fixes (PR #39)
def test_consumer_detection_details(toy_repo, app_repo, capsys, monkeypatch):
    from codetwin.crossrepo import analysis
    from codetwin.crossrepo.analysis import code_text, import_lines
    late = ["x = 1"] * 450 + ["    from shop.price import total"]
    assert import_lines(late, ["shop"]) == ["shop.price"]                 # imports inside functions, late in a file
    assert code_text("x = total(items)  # total") == "x = total(items) " and code_text("// total") == ""
    assert code_text('log("total failed")') == 'log("")' and code_text("*args = total") == "*args = total"
    (app_repo / "app" / "note.py").write_text("import shop\n# total is computed upstream\nmsg = 'total'\n")
    (app_repo / "app" / "broken.py").write_text("def broken(:\n")
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + f'\n[[repos]]\nname = "app"\npath = "{app_repo.as_posix()}"\n')
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    capsys.readouterr()
    main(["-C", str(toy_repo), "crossrepo", "--json"])
    app = json.loads(capsys.readouterr().out)["repos"][0]
    cons = {c["file"]: c for c in app["consumers"]}
    assert cons["app/note.py"]["link"] == "imports-package"               # names in comments/strings are not uses
    assert any("could not be fully parsed" in u and "app/broken.py" in u for u in app["unknowns"])

    real_get = analysis.langmod.get

    def get(cfg):
        a = real_get(cfg)
        if Path(cfg.root).resolve() == app_repo.resolve():
            def boom():
                raise RuntimeError("tree-sitter missing")
            a.facts = boom
        return a
    monkeypatch.setattr(analysis.langmod, "get", get)
    main(["-C", str(toy_repo), "crossrepo", "--json"])
    app = json.loads(capsys.readouterr().out)["repos"][0]
    assert app["consumers"] == [] and any("could not analyse" in u for u in app["unknowns"])


def test_no_source_change_has_no_cross_repo_impact(toy_repo, app_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    cfg.write_text(cfg.read_text() + f'\n[[repos]]\nname = "app"\npath = "{app_repo.as_posix()}"\n')
    t = next((toy_repo / "tests").glob("test_*.py"))
    t.write_text(t.read_text() + "\n# comment\n")
    capsys.readouterr()
    main(["-C", str(toy_repo), "crossrepo", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["repos"] == [] and "no source file changed" in out["summary"]


def test_stored_links_follow_the_configuration(toy_repo, app_repo, capsys):
    """Review fixes (#43): runtime evidence without consumers, removed [[repos]] links end."""
    from codetwin.store.analyses import crossrepo_history
    main(["-C", str(toy_repo), "init"])
    cfg = toy_repo / ".codetwin.toml"
    base_cfg = cfg.read_text()
    cfg.write_text(base_cfg + f'\n[[repos]]\nname = "app"\npath = "{app_repo.as_posix()}"\npackages = ["nothing_imports_this"]\n')
    with Engine(app_repo) as dep:
        dep.record()                                          # the dependent has a recorded run
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    main(["-C", str(toy_repo), "crossrepo", "--json"])
    with Engine(toy_repo) as eng:
        st = eng.store
        t = st.con.execute("select runtime_evidence from analysis_target").fetchone()[0]
        assert t == 1                                         # no consumers, but it had a recorded run
        assert ("nothing_imports_this",) not in st.con.execute("select name from package").fetchall()
    cfg.write_text(base_cfg + '\n[[repos]]\nname = "other"\npath = "../nowhere"\n')
    capsys.readouterr()
    main(["-C", str(toy_repo), "crossrepo", "--json"])
    with Engine(toy_repo) as eng:
        rel = set(eng.store.con.execute("select source, type, target from repository_relation"))
        assert ("other", "dependsOn", ".") in rel and ("app", "dependsOn", ".") not in rel
        ended = eng.store.con.execute("select r.name from repository_link l join repository r on r.id = l.consumer_id "
                                      "where l.ended is not null").fetchall()
        assert ended == [("app",)] and len(crossrepo_history(eng.store)) == 2
