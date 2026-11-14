"""Language adapters: coverage readers, tree-sitter facts, import resolution, no-ops, mutants, end to end."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from codetwin import lang
from codetwin.cli import main
from codetwin.config import Config
from codetwin.lang import coverage_formats as cf
from codetwin.lang.base import glob_match

ts = pytest.importorskip("tree_sitter_language_pack")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"})


def _write(root: Path, files: dict[str, str]) -> None:
    for p, text in files.items():
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text(text)


def _adapter(root: Path, name: str, **project):
    cfg = Config(root=root, language=name, source_dirs=project.get("source_dirs", ["src"]),
                 tests_dir=project.get("tests_dir", "test"), raw=project.get("raw", {}))
    return lang.get(cfg)


# ------------------------------------------------------------------ helpers and formats
def test_glob_star_does_not_cross_folders():
    assert glob_match("test/a.js", ["test/*.*"])
    assert not glob_match("test/fixtures/a.js", ["test/*.*"])
    assert glob_match("pkg/__tests__/x/y.ts", ["**/__tests__/**/*.*"])
    assert glob_match("src/test/java/FooTest.java", ["**/src/test/**/*Test.java"])
    assert glob_match("a/b/c.spec.ts", ["*.spec.*"])


def test_coverage_readers(tmp_path):
    known = ["src/a.js", "src/b.go", "src/main/java/com/x/Foo.java", "lib/c.py", "src/D.php"]
    m = cf.PathMapper(tmp_path, known)
    assert cf.read_lcov("SF:src/a.js\nDA:1,1\nDA:2,0\nDA:3,4\nend_of_record\nSF:/elsewhere/x.js\nDA:1,1\n", m) == \
        {"src/a.js": {1, 3}}
    assert cf.read_gocover("mode: set\nexample.com/m/src/b.go:3.10,5.2 2 1\nexample.com/m/src/b.go:7.1,8.2 1 0\n", m) == \
        {"src/b.go": {3, 4, 5}}
    jac = ('<report name="r"><package name="com/x"><sourcefile name="Foo.java"><line nr="4" mi="0" ci="2"/>'
           '<line nr="5" mi="3" ci="0"/></sourcefile></package></report>')
    assert cf.read_jacoco(jac, m) == {"src/main/java/com/x/Foo.java": {4}}
    cob = ('<coverage><sources><source>lib</source></sources><packages><package><classes>'
           '<class filename="c.py"><lines><line number="1" hits="1"/><line number="2" hits="0"/></lines></class>'
           '</classes></package></packages></coverage>')
    assert cf.read_cobertura(cob, m) == {"lib/c.py": {1}}
    clo = '<coverage><project><file name="D.php" path="src/D.php"><line num="9" count="2"/></file></project></coverage>'
    assert cf.read_clover(clo, m) == {"src/D.php": {9}}


def test_detect_counts_files_among_marked_languages(tmp_path):
    _write(tmp_path, {"package.json": "{}", "pyproject.toml": "", "src/a.py": "", "src/b.py": "", "web/x.js": ""})
    assert lang.detect(tmp_path) == "python"           # package.json for tooling does not make it JavaScript
    _write(tmp_path, {"go.mod": "module m\n", "x.go": "package m\n", "y.go": "package m\n", "z.go": "package m\n"})
    assert lang.detect(tmp_path) == "go"


def test_custom_language_from_config(tmp_path):
    a = _adapter(tmp_path, "lua", raw={"language": {"grammar": "lua", "extensions": [".lua"],
                                                    "test_globs": ["*_spec.lua"]}})
    assert a.name == "lua" and a.is_test("spec/x_spec.lua") and not a.is_test("src/x.lua")
    with pytest.raises(ValueError):
        _adapter(tmp_path, "cobol")


# ------------------------------------------------------------------ JavaScript / TypeScript
JS = {
    "package.json": '{"name": "demo", "type": "module", "scripts": {"test": "node --test"}}',
    "tsconfig.json": '{ // comment\n "compilerOptions": {"baseUrl": ".", "paths": {"@lib/*": ["src/lib/*"]},},\n}',
    "src/math.ts": "export function add(a: number, b: number): number {\n  return a + b;\n}\n"
                   "export const twice = (x: number) => add(x, x);\nexport class K { constructor() {} m() { return 1; } }\n",
    "src/lib/fmt.ts": "export const fmt = (s: string) => s;\n",
    "src/index.ts": "import { add } from './math.js';\nimport { fmt } from '@lib/fmt';\nconst m = require(name);\n"
                    "export const v = add(1, 2);\n",
    "test/math.test.ts": "import { add } from '../src/math';\n",
}


def test_javascript_facts_resolution_and_kinds(tmp_path):
    _write(tmp_path, JS)
    a = _adapter(tmp_path, "typescript")
    facts = a.facts()
    assert a.list_tests() == ["test/math.test.ts"]
    assert facts["src/index.ts"].deps == ["src/math.ts", "src/lib/fmt.ts"]    # .js -> .ts and tsconfig paths
    assert facts["test/math.test.ts"].deps == ["src/math.ts"]
    assert "dynamic-import" in facts["src/index.ts"].dynamic
    assert 4 in facts["src/index.ts"].mod_lines and 1 not in facts["src/index.ts"].mod_lines
    assert [1, 3, 2] in facts["src/math.ts"].defs
    old = JS["src/math.ts"]
    assert a.classify_source(old, old.replace("return a + b;", "return a + b; // sum"), "src/math.ts") == "noop"
    assert a.classify_source(old, old.replace("b: number)", "b: any)"), "src/math.ts") == "annotation"
    assert a.classify_source(old, old.replace("a + b", "a - b"), "src/math.ts") == "semantic"
    mut = a.extreme_mutant(old, [1, 3, 2], "src/math.ts")
    assert mut.startswith("export function add(a: number, b: number): number { return (undefined as any);")
    assert a.extreme_mutant(old, [4, 4, 4], "src/math.ts").startswith(old.split("\n")[0])
    assert "(undefined as any)" in a.extreme_mutant(old, [4, 4, 4], "src/math.ts").split("\n")[3]


def test_javascript_end_to_end_with_node_test(tmp_path, monkeypatch):
    if not shutil.which("node"):
        pytest.skip("node not installed")
    _write(tmp_path, {
        "package.json": '{"name": "demo", "type": "module", "scripts": {"test": "node --test"}}',
        "src/math.js": "export function add(a, b) {\n  return a + b;\n}\nexport function mul(a, b) {\n  return a * b;\n}\n",
        "src/util.js": "import { add } from './math.js';\nexport const inc = (x) => add(x, 1);\n",
        "test/math.test.js": "import test from 'node:test';\nimport assert from 'node:assert';\n"
                             "import { mul } from '../src/math.js';\ntest('m', () => assert.strictEqual(mul(2, 3), 6));\n",
        "test/util.test.js": "import test from 'node:test';\nimport { inc } from '../src/util.js';\ntest('i', () => { inc(1); });\n",
    })
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert 'language = "javascript"' in (tmp_path / ".codetwin.toml").read_text()
    assert main(["record"]) == 0
    src = (tmp_path / "src/math.js").read_text()
    (tmp_path / "src/math.js").write_text(src.replace("return a + b;", "return a + b + 0;"))
    from codetwin.engine import Engine
    with Engine(tmp_path) as eng:
        run = eng.store.get_run(eng.store.latest_run_sha())
        assert run.covered["test/util.test.js"]["src/math.js"]
        assert "src/math.js" not in run.covered["test/math.test.js"] or 2 not in run.covered["test/math.test.js"]["src/math.js"]
        d = eng.select()
        assert d.extras["semantic_noop"]["kind"] == "semantic"
        assert "test/util.test.js" in d.selected
        rows, _ = eng.analyse()[3], None
        assert rows["test/util.test.js"]["cov_line"] == 1 and rows["test/math.test.js"]["cov_line"] == 0
        assert rows["test/util.test.js"]["static_inv_dist"] == 0.5       # util.test -> util -> math
    from codetwin.evidence.weakcheck import changed_functions, run_checks
    with Engine(tmp_path) as eng:
        base = eng.store.latest_run_sha()
        checks = changed_functions(eng.changed(base), eng.store.get_run(base), eng.store.get_static(base),
                                   eng.facts_now(), eng.is_source)
        run_checks(eng.root, ".", checks, eng.facts_now(), 120, eng.lang)
    assert [(c.file, c.status) for c in checks] == [("src/math.js", "unchecked")]   # util.test asserts nothing
    assert main(["run", "test/math.test.js"]) == 0


# ------------------------------------------------------------------ Go
GO = {
    "go.mod": "module example.com/demo\n\ngo 1.21\n",
    "calc/calc.go": "package calc\n\n// Add adds.\nfunc Add(a, b int) int {\n\treturn a + b\n}\n\n"
                    "func Div(a, b int) (int, error) {\n\treturn a / b, nil\n}\n\nvar cache = map[int]int{}\n",
    "calc/calc_test.go": 'package calc\n\nimport "testing"\n\nfunc TestAdd(t *testing.T) {\n\tif Add(1, 2) != 3 {\n'
                         '\t\tt.Fatal("bad")\n\t}\n}\n',
    "app/app.go": 'package app\n\nimport (\n\t"reflect"\n\t"example.com/demo/calc"\n)\n\n'
                  "func Twice(x int) int { return calc.Add(x, x) }\n\nfunc T(v any) string { return reflect.TypeOf(v).Name() }\n",
    "app/app_test.go": 'package app\n\nimport "testing"\n\nfunc TestTwice(t *testing.T) {\n\tTwice(2)\n}\n',
}


def test_go_facts_and_mutants(tmp_path):
    _write(tmp_path, GO)
    a = _adapter(tmp_path, "go", source_dirs=["."], tests_dir=".")
    facts = a.facts()
    assert a.list_tests() == ["app/app_test.go", "calc/calc_test.go"]
    assert facts["app/app.go"].deps == ["calc/calc.go"]               # source files never depend on tests
    assert set(facts["app/app_test.go"].deps) == {"app/app.go"}
    assert facts["app/app.go"].dynamic == ["reflect"]
    assert facts["calc/calc.go"].mod_lines == [12]                       # package-level var initialiser
    src = GO["calc/calc.go"]
    assert a.classify_source(src, src.replace("// Add adds.", "// Add returns a+b."), "calc/calc.go") == "noop"
    m = a.extreme_mutant(src, [8, 10, 9], "calc/calc.go")
    assert "var codetwinZero0 int; var codetwinZero1 error; return codetwinZero0, codetwinZero1;" in m
    assert a.extreme_mutant(src, [4, 6, 5], "calc/calc.go").split("\n")[3] == "func Add(a, b int) int { var codetwinZero0 int; return codetwinZero0; "
    v = a.runner.vars("calc/calc_test.go", GO["calc/calc_test.go"])
    assert v == {"names": "^(TestAdd)$", "pkg": "./calc"}


def test_go_end_to_end(tmp_path, monkeypatch):
    if not shutil.which("go"):
        pytest.skip("go not installed")
    _write(tmp_path, GO)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--language", "golang"]) == 0
    assert main(["record"]) == 0
    from codetwin.engine import Engine
    with Engine(tmp_path) as eng:
        run = eng.store.get_run(eng.store.latest_run_sha())
        assert run.covered["app/app_test.go"]["calc/calc.go"] and not run.failing
    p = tmp_path / "calc/calc.go"
    p.write_text(GO["calc/calc.go"].replace("// Add adds.", "// Add returns the sum."))
    with Engine(tmp_path) as eng:
        assert eng.select().extras["semantic_noop"]["kind"] == "noop"


# ------------------------------------------------------------------ Java (static parts; no build tool needed)
JAVA = {
    "pom.xml": "<project/>",
    "src/main/java/com/acme/Calc.java": "package com.acme;\n\npublic class Calc {\n    static final int Z = compute();\n"
                                        "    public int mul(int a, int b) {\n        return a * b;\n    }\n"
                                        "    void r() throws Exception { Class.forName(\"x\"); }\n}\n",
    "src/main/java/com/acme/Shop.java": "package com.acme;\n\nimport com.acme.util.*;\n\npublic class Shop {\n"
                                        "    Calc c = new Calc();\n    String s() { return Fmt.f(); }\n}\n",
    "src/main/java/com/acme/util/Fmt.java": "package com.acme.util;\n\npublic class Fmt { public static String f() "
                                             "{ return \"\"; } }\n",
    "src/test/java/com/acme/ShopTest.java": "package com.acme;\n\nclass ShopTest { void t() { new Shop(); } }\n",
}


def test_java_facts_and_mutants(tmp_path):
    _write(tmp_path, JAVA)
    a = _adapter(tmp_path, "java", source_dirs=["src/main/java"], tests_dir="src/test/java")
    facts = a.facts()
    assert a.list_tests() == ["src/test/java/com/acme/ShopTest.java"]
    assert facts["src/main/java/com/acme/Shop.java"].deps == ["src/main/java/com/acme/util/Fmt.java",
                                                              "src/main/java/com/acme/Calc.java"]
    assert facts["src/test/java/com/acme/ShopTest.java"].deps == ["src/main/java/com/acme/Shop.java"]
    assert facts["src/main/java/com/acme/Calc.java"].dynamic == ["reflection"]
    assert 4 in facts["src/main/java/com/acme/Calc.java"].mod_lines      # static field initialiser
    src = JAVA["src/main/java/com/acme/Calc.java"]
    assert "{ if (true) return 0; " in a.extreme_mutant(src, [5, 7, 6], "Calc.java")
    assert a.runner.name == "maven"
    assert a.runner.vars("src/test/java/com/acme/ShopTest.java", JAVA["src/test/java/com/acme/ShopTest.java"]) == \
        {"test_class": "com.acme.ShopTest"}


# ------------------------------------------------------------------ other specs: import resolution only
@pytest.mark.parametrize("name,files,src_file,expected", [
    ("rust", {"Cargo.toml": '[package]\nname = "my-crate"\n', "src/lib.rs": "mod a;\npub use crate::a::b::f;\n",
              "src/a.rs": "pub mod b;\n", "src/a/b.rs": "pub fn f() {}\n#[cfg(test)]\nmod tests {}\n",
              "tests/it.rs": "use my_crate::a::b::f;\n"}, "tests/it.rs", ["src/a/b.rs"]),
    ("cpp", {"src/x.h": "int f();\n", "src/x.cpp": '#include "x.h"\nint f() { return 1; }\n',
             "src/main.cpp": '#include "x.h"\n#include <vector>\n'}, "src/main.cpp", ["src/x.h", "src/x.cpp"]),
    ("ruby", {"lib/a.rb": "def a; end\n", "lib/b.rb": "require_relative 'a'\n", "spec/b_spec.rb": "require 'b'\n"},
     "spec/b_spec.rb", ["lib/b.rb"]),
    ("php", {"src/Model/User.php": "<?php\nnamespace App\\Model;\nclass User {}\n",
             "src/Svc.php": "<?php\nuse App\\Model\\User;\n"}, "src/Svc.php", ["src/Model/User.php"]),
    ("csharp", {"src/A.cs": "namespace Shop.Core { class Cart {} }\n", "src/Cart.cs": "namespace Shop.Core { public class Cart {} }\n",
                "src/B.cs": "using Shop.Core;\nnamespace Shop.App { class B { Cart c; } }\n"}, "src/B.cs", ["src/Cart.cs"]),
    ("kotlin", {"src/main/kotlin/a/Util.kt": "package a\nfun u() = 1\n",
                "src/main/kotlin/b/Use.kt": "package b\nimport a.Util\nfun x() = 2\n"}, "src/main/kotlin/b/Use.kt",
     ["src/main/kotlin/a/Util.kt"]),
])
def test_other_languages_resolve_imports(tmp_path, name, files, src_file, expected):
    _write(tmp_path, files)
    a = _adapter(tmp_path, name, source_dirs=["."], tests_dir=".")
    assert a.facts()[src_file].deps == expected


def test_rust_unit_test_ids(tmp_path):
    _write(tmp_path, {"Cargo.toml": '[package]\nname = "c"\n', "src/lib.rs": "mod a;\n",
                      "src/a.rs": "#[cfg(test)]\nmod tests {}\n", "tests/it.rs": ""})
    a = _adapter(tmp_path, "rust", source_dirs=["src"], tests_dir="tests")
    assert a.list_tests() == ["src/a.rs::tests", "tests/it.rs"]
    assert a._vars("src/a.rs::tests", tmp_path, a.runner)["target"] == ["--lib", "--", "a::tests::"]
    assert a._argv("cargo test {target}", {"target": ["--test", "it"]}) == ["cargo", "test", "--test", "it"]


def test_python_projects_still_use_the_python_adapter(tmp_path):
    cfg = Config(root=tmp_path, packages=["pkg"], source_dirs=["pkg"])          # old config: no language key
    assert lang.get(cfg).name == "python"
    assert json.dumps(lang.names()).startswith('["python"')


# ------------------------------------------------------------------ any repository
def test_unknown_language_gets_an_automatic_spec(tmp_path):
    _write(tmp_path, {"src/calc.lua": "local M = {}\nfunction M.mul(a, b)\n  return a * b\nend\nreturn M\n",
                      "src/cart.lua": 'local calc = require("src.calc")\nreturn calc\n',
                      "spec/cart_spec.lua": 'local cart = require("src.cart")\n'})
    assert lang.detect_all(tmp_path) == ["lua"]
    a = lang.get(Config(root=tmp_path))
    assert a.name == "lua" and a.runner is None and not a.has_runtime_evidence("src/calc.lua")
    facts = a.facts()
    assert facts["src/cart.lua"].deps == ["src/calc.lua"] and facts["spec/cart_spec.lua"].deps == ["src/cart.lua"]
    assert facts["src/calc.lua"].defs == [[2, 4, 3]]
    run = a.run_suite("x")
    assert run.returncode == "no-runner" and not run.covered and list(run.durations) == ["spec/cart_spec.lua"]
    old = (tmp_path / "src/calc.lua").read_text()
    assert a.classify_source(old, old.replace("a * b", "a * b -- x"), "src/calc.lua") == "noop"


def test_mixed_repository_combines_languages(tmp_path):
    _write(tmp_path, {"backend/pyproject.toml": "", "backend/src/shop/__init__.py": "",
                      "backend/src/shop/calc.py": "def mul(a, b):\n    return a * b\n",
                      "backend/src/shop/cart.py": "from shop.calc import mul\n",
                      "backend/tests/test_cart.py": "from shop.cart import mul\n",
                      "web/package.json": '{"name": "web", "devDependencies": {"vitest": "1"}}',
                      "web/src/a.ts": "export const a = 1;\n", "web/test/a.test.ts": "import { a } from '../src/a';\n",
                      "tools/x.js": "module.exports = 1;\n"})
    assert lang.detect_all(tmp_path) == ["python", "javascript"]
    a = lang.get(Config(root=tmp_path, raw={"project": {"languages": ["python", "javascript"]}}))
    assert a.name == "python+javascript"
    assert a.list_tests() == ["backend/tests/test_cart.py", "web/test/a.test.ts"]
    assert a.is_source("backend/src/shop/calc.py") and a.is_source("web/src/a.ts") and not a.is_test("web/src/a.ts")
    facts = a.facts()
    assert facts["backend/src/shop/cart.py"].deps == ["backend/src/shop/calc.py"]       # import roots found
    assert facts["web/test/a.test.ts"].deps == ["web/src/a.ts"]
    js = a.adapters[1]
    assert js.project_dir("web/test/a.test.ts") == "web" and js.runner_for("web").name == "vitest"
    assert js.project_dir("tools/x.js") == ""


def test_select_abstains_without_runtime_evidence(tmp_path, monkeypatch):
    _write(tmp_path, {"src/calc.lua": "return 1\n", "spec/calc_spec.lua": 'require("src.calc")\n'})
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0 and main(["record"]) == 0
    (tmp_path / "src/calc.lua").write_text("return 2\n")
    from codetwin.engine import Engine
    with Engine(tmp_path) as eng:
        d = eng.select()
        assert d.decision == "abstain" and d.selected == {"spec/calc_spec.lua"}
        assert any("no test runner" in r for r in d.reasons)
        with pytest.raises(RuntimeError, match="no test runner"):
            eng.learn()


@pytest.mark.parametrize("name,path,src,fn,expected", [
    ("csharp", "A.cs", "class A {\n    int M(int a) {\n        return a;\n    }\n}\n", [2, 4, 3],
     "{ if (true) return default; "),
    ("ruby", "a.rb", "def m(a)\n  a + 1\nend\n", [1, 3, 2], "return nil; a + 1"),
    ("php", "a.php", "<?php\nfunction f(int $a): int {\n    return $a;\n}\n", [2, 4, 3], "{ if (true) return 0; "),
    ("rust", "a.rs", "fn f(a: i64) -> i64 {\n    a\n}\n", [1, 3, 2], "{ return Default::default(); "),
    ("cpp", "a.cpp", "int f(int a) {\n    return a;\n}\n", [1, 3, 2], "{ return 0; "),
    ("cpp", "a.cpp", "std::string f() {\n    return \"\";\n}\n", [1, 3, 2], "{ return {}; "),
    ("kotlin", "a.kt", "fun f(a: Int): Int {\n    return a\n}\n", [1, 3, 2], "{ if (true) return 0; "),
])
def test_weakcheck_mutants_for_more_languages(tmp_path, name, path, src, fn, expected):
    a = _adapter(tmp_path, name, source_dirs=["."], tests_dir=".")
    assert expected in a.extreme_mutant(src, fn, path)


def test_python_inside_a_larger_repository_finds_import_roots(tmp_path):
    from codetwin.lang.python import import_roots
    _write(tmp_path, {"svc/src/app/__init__.py": "", "svc/src/app/core/__init__.py": "", "lib/util/__init__.py": ""})
    assert import_roots(tmp_path) == ["lib", "svc/src"]
