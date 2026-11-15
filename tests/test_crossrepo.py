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
