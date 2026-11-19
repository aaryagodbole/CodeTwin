"""JavaScript and TypeScript (Node.js): Vitest, Jest, Mocha, node:test or any `npm test`, coverage as LCOV.

Imports: ES `import`/`export ... from`, `require()`, dynamic `import()`, `jest.mock()`/`vi.mock()` with a
string; relative paths (with TypeScript's `.js` -> `.ts` mapping and `index` files), `tsconfig.json`
`baseUrl`/`paths`, and packages of the same workspace (monorepos). A `require`/`import()` with a computed
name, `eval` and `new Function` are reported as dynamic.
"""
from __future__ import annotations

import json
import posixpath
from pathlib import Path

from ..spec import Runner, Spec
from ._util import first_arg, leading_insert, load_jsonc, rel_join, string_value, txt

EXTS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
TS = (".ts", ".tsx", ".mts", ".cts")
LOADERS = {"require", "import", "jest.mock", "jest.requireActual", "jest.doMock", "vi.mock", "vi.importActual",
           "require.resolve"}


def imports(n, src: bytes) -> list[str] | None:
    if n.type in ("import_statement", "export_statement"):
        s = string_value(n.child_by_field_name("source"), src)
        return [s] if s else None
    if n.type == "call_expression":
        fn = n.child_by_field_name("function")
        if fn is not None and txt(fn, src) in LOADERS:
            s = string_value(first_arg(n, src), src)
            return [s] if s else None
    return None


def dynamic(n, src: bytes) -> str | None:
    if n.type == "call_expression":
        fn = n.child_by_field_name("function")
        name = txt(fn, src) if fn is not None else ""
        if name in ("require", "import"):
            arg = first_arg(n, src)
            if arg is not None and string_value(arg, src) is None:
                return "dynamic-import"
        if name == "eval":
            return "eval"
    if n.type == "new_expression":
        c = n.child_by_field_name("constructor")
        if c is not None and txt(c, src) == "Function":
            return "function-constructor"
    return None


def _package_dirs(root: Path) -> dict[str, tuple[str, dict]]:
    out: dict[str, tuple[str, dict]] = {}
    for depth in ("", "*/", "*/*/", "*/*/*/"):
        for p in root.glob(f"{depth}package.json"):
            if "node_modules" in p.parts:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and isinstance(data.get("name"), str):
                d = p.parent.relative_to(root).as_posix()
                out[data["name"]] = ("" if d == "." else d, data)
    return out


def prepare(idx) -> None:
    ts = load_jsonc(idx.root / "tsconfig.json").get("compilerOptions", {})
    base = ts.get("baseUrl")
    idx.data["base_url"] = posixpath.normpath(base) if isinstance(base, str) else None
    paths = ts.get("paths") if isinstance(ts.get("paths"), dict) else {}
    idx.data["paths"] = {k: v for k, v in paths.items() if isinstance(v, list)}
    idx.data["packages"] = _package_dirs(idx.root)


def _candidates(p: str) -> list[str]:
    p = posixpath.normpath(p)
    out = [p]
    stem, ext = posixpath.splitext(p)
    if ext in (".js", ".jsx", ".mjs", ".cjs"):          # TypeScript ESM imports name the compiled file
        out += [stem + e for e in TS]
    out += [p + e for e in EXTS] + [posixpath.join(p, "index" + e) for e in EXTS]
    return out


def _first(files: set[str], cands: list[str]) -> list[str]:
    for c in cands:
        if c in files:
            return [c]
    return []


def resolve(spec: str, from_file: str, idx) -> list[str]:
    if spec.startswith((".", "/")):
        return _first(idx.files, _candidates(rel_join(from_file, spec)))
    for pat, targets in idx.data.get("paths", {}).items():       # tsconfig "paths": {"@app/*": ["src/*"]}
        pre = pat.split("*")[0]
        if spec == pat or (pat.endswith("*") and spec.startswith(pre)):
            rest = spec[len(pre):] if pat.endswith("*") else ""
            base = idx.data.get("base_url") or "."
            for tgt in targets:
                hit = _first(idx.files, _candidates(posixpath.join(base, tgt.replace("*", rest))))
                if hit:
                    return hit
    if idx.data.get("base_url"):
        hit = _first(idx.files, _candidates(posixpath.join(idx.data["base_url"], spec)))
        if hit:
            return hit
    pkgs = idx.data.get("packages", {})
    parts = spec.split("/")
    name = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
    if name in pkgs:                                             # a package of this workspace
        d, data = pkgs[name]
        rest = spec[len(name):].lstrip("/")
        if rest:
            return _first(idx.files, _candidates(posixpath.join(d, rest)) + _candidates(posixpath.join(d, "src", rest)))
        mains = [data.get(k) for k in ("source", "types", "module", "main") if isinstance(data.get(k), str)]
        cands = [c for m in mains for c in _candidates(posixpath.join(d, m))]
        return _first(idx.files, cands + _candidates(posixpath.join(d, "src", "index")) + _candidates(posixpath.join(d, "index")))
    return []


def mutant(fn, src: bytes, path: str) -> tuple[int, int, str] | None:
    name = fn.child_by_field_name("name")
    if name is not None and txt(name, src) == "constructor":
        return None                      # a constructor must initialise the object; no neutral "return"
    if any(c.type == "*" for c in fn.children):
        return None                      # generators
    value = "(undefined as any)" if path.endswith(TS) else "undefined"
    body = fn.child_by_field_name("body")
    if body is None:
        return None
    if fn.type == "arrow_function" and body.type != "statement_block":
        return body.start_byte, body.end_byte, value
    return leading_insert(body, src, f"return {value};")


def _has_dep(root: Path, name: str) -> bool:
    try:
        data = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    if name in deps:
        return True
    return name in json.dumps(data.get("scripts", {}))


def _jest_config(root: Path) -> list[str]:
    """`--config <file>` when the Jest configuration is not where Jest looks for it by default."""
    if any((root / f"jest.config.{e}").exists() for e in ("js", "ts", "mjs", "cjs", "json")):
        return []
    try:
        if "jest" in json.loads((root / "package.json").read_text(encoding="utf-8")):
            return []
    except (OSError, ValueError):
        pass  # no readable package.json: look for a config file one or two levels down instead
    for p in sorted(root.glob("*/jest.config.*")) + sorted(root.glob("*/*/jest.config.*")):
        if "node_modules" not in p.parts:
            return ["--config", p.relative_to(root).as_posix()]
    return []


def vitest_provider(root: Path) -> str:
    """Coverage provider of the installed Vitest: `c8` before 0.34 (renamed `v8` in 0.34)."""
    try:
        v = json.loads((root / "node_modules" / "vitest" / "package.json").read_text(encoding="utf-8"))["version"]
        major, minor = (int(x) for x in v.split(".")[:2])
    except (OSError, ValueError, KeyError):
        return "v8"
    return "c8" if (major, minor) < (0, 34) else "v8"


def _vitest_vars(test: str, text: str, cwd: Path) -> dict:
    return {"vitest_provider": [f"--coverage.provider={vitest_provider(cwd)}"]}


def _jest_vars(test: str, text: str, cwd: Path) -> dict:
    return {"jest_config": _jest_config(cwd)}


def _script(root: Path) -> str:
    try:
        return str(json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts", {}).get("test", ""))
    except (OSError, ValueError, AttributeError):
        return ""


C8 = "npx --yes c8@10 --reporter=lcovonly --report-dir={cov_dir} --exclude-after-remap"
RUNNERS = [
    Runner("vitest",
           "npx --no-install vitest run --coverage.enabled=true {vitest_provider} --coverage.reporter=lcov "
           "--coverage.reportsDirectory={cov_dir} {test}",
           "lcov", "lcov.info", run_command="npx --no-install vitest run {test}",
           detect=lambda root: _has_dep(root, "vitest"), vars=_vitest_vars),
    Runner("jest",
           "npx --no-install jest --ci --coverage --coverageReporters=lcov --coverageDirectory={cov_dir} "
           "{jest_config} --runTestsByPath {test}",
           "lcov", "lcov.info", run_command="npx --no-install jest --ci {jest_config} --runTestsByPath {test}",
           detect=lambda root: _has_dep(root, "jest"), vars=_jest_vars),
    Runner("mocha", f"{C8} npx --no-install mocha {{test}}", "lcov", "lcov.info",
           run_command="npx --no-install mocha {test}", detect=lambda root: _has_dep(root, "mocha")),
    Runner("node-test", "node --test --experimental-test-coverage --test-reporter=lcov "
           "--test-reporter-destination={cov_dir}/lcov.info {test}", "lcov", "lcov.info",
           run_command="node --test {test}",
           detect=lambda root: "node --test" in _script(root)),
    Runner("npm-test", f"{C8} npm test --silent -- {{test}}", "lcov", "lcov.info",
           run_command="npm test --silent -- {test}", detect=lambda root: bool(_script(root))),
]

SPEC = Spec(
    name="javascript",
    grammars={".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "tsx",
              ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript"},
    test_globs=["*.test.*", "*.spec.*", "*.tests.*", "**/__tests__/**/*.*", "test/*.*", "tests/*.*", "**/test/**/*.test.*",
                "**/test/**/*.spec.*", "**/tests/**/*.test.*", "**/tests/**/*.spec.*", "**/tests/**/test.ts",
                "**/tests/**/test.js", "**/tests/**/test.mjs"],
    exclude_globs=["*.config.*", "*.d.ts", "*.mock.*", "*.snap", "**/fixtures/**", "**/e2e/**", "**/__snapshots__/**"],
    helper_globs=["*setup*", "*helper*", "*util*", "*fixture*", "*mock*", "**/samples/**", "**/shared/**"],
    markers=["package.json", "tsconfig.json"],
    source_dirs=["src", "lib", "packages", "app"],
    tests_dirs=["test", "tests", "__tests__"],
    function_types={"function_declaration", "function_expression", "function", "arrow_function", "method_definition",
                    "generator_function_declaration", "generator_function"},
    decl_types={"import_statement", "function_declaration", "class_declaration", "abstract_class_declaration",
                "interface_declaration", "type_alias_declaration", "ambient_declaration", "empty_statement",
                "hash_bang_line", "generator_function_declaration", "module", "internal_module"},
    container_types={"export_statement"},
    annotation_types={"type_annotation", "type_arguments", "type_parameters", "interface_declaration",
                      "type_alias_declaration", "implements_clause", "optional_type", "omitting_type_annotation",
                      "opting_type_annotation", "asserts_annotation", "type_predicate_annotation"},
    imports=imports, dynamic=dynamic, prepare=prepare, resolve=resolve, mutant=mutant, runners=RUNNERS,
)
