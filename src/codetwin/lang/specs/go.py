"""Go: `go test` per test file (its Test functions), coverage from `-coverprofile` across all packages.

Imports of the module's own packages resolve to the files of that package directory; files of one package
see each other without imports, so every file depends on the other files in its directory. `reflect` and
`plugin.Open` are reported as dynamic. Weakcheck mutants return zero values early (the rest of the body
stays, so imports and variables remain used).
"""
from __future__ import annotations

import posixpath
import re

from ..spec import Runner, Spec
from ._util import leading_insert, same_dir, string_value, txt

TEST_FUNC = re.compile(r"^func\s+(Test[A-Z_0-9]\w*)\s*\(\s*\w+\s+\*testing\.T\s*\)", re.M)


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "import_spec":
        s = string_value(n.child_by_field_name("path"), src)
        return [s] if s else None
    return None


def dynamic(n, src: bytes) -> str | None:
    if n.type == "call_expression":
        fn = n.child_by_field_name("function")
        name = txt(fn, src) if fn is not None else ""
        if name.startswith("reflect."):
            return "reflect"
        if name == "plugin.Open":
            return "plugin"
    return None


def prepare(idx) -> None:
    mods: dict[str, str] = {}
    for gm in sorted(idx.root.glob("**/go.mod")):
        if "vendor" in gm.parts:
            continue
        m = re.search(r"^module\s+(\S+)", gm.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            d = gm.parent.relative_to(idx.root).as_posix()
            mods[m.group(1)] = "" if d == "." else d
    idx.data["modules"] = mods
    by_dir: dict[str, list[str]] = {}
    for f in idx.files:
        if not f.endswith("_test.go"):
            by_dir.setdefault(posixpath.dirname(f), []).append(f)
    idx.data["by_dir"] = by_dir


def resolve(spec: str, from_file: str, idx) -> list[str]:
    for mod, d in sorted(idx.data.get("modules", {}).items(), key=lambda kv: -len(kv[0])):
        if spec == mod or spec.startswith(mod + "/"):
            rel = spec[len(mod):].lstrip("/")
            pkg = posixpath.normpath(posixpath.join(d, rel)) if (d or rel) else ""
            return sorted(idx.data["by_dir"].get("" if pkg == "." else pkg, []))
    return []


def extra_deps(f: str, idx) -> list[str]:
    """Files of one package share a namespace. A test file sees the package and its other test files; a
    source file sees only the package's source files."""
    deps = same_dir(idx.files, f, (".go",))
    return deps if f.endswith("_test.go") else [d for d in deps if not d.endswith("_test.go")]


def mutant(fn, src: bytes, path: str) -> tuple[int, int, str] | None:
    body = fn.child_by_field_name("body")
    res = fn.child_by_field_name("result")
    if res is None:
        return leading_insert(body, src, "return;")
    if res.type == "parameter_list":
        params = [p for p in res.named_children if p.type in ("parameter_declaration", "variadic_parameter_declaration")]
        if any(p.child_by_field_name("name") is not None for p in params):
            return leading_insert(body, src, "return;")         # named results: a naked return yields zero values
        types = [txt(p.child_by_field_name("type") or p, src) for p in params]
    else:
        types = [txt(res, src)]
    decl = "; ".join(f"var codetwinZero{i} {t}" for i, t in enumerate(types))
    ret = ", ".join(f"codetwinZero{i}" for i in range(len(types)))
    return leading_insert(body, src, f"{decl}; return {ret};")


def _vars(test: str, text: str) -> dict:
    names = TEST_FUNC.findall(text)
    return {"names": "^(" + "|".join(names) + ")$" if names else "^$",
            "pkg": "./" + (posixpath.dirname(test) or ".")}


RUNNERS = [Runner(
    "go-test",
    "go test -count=1 -coverpkg=./... -coverprofile={cov_dir}/cover.out -run {names} {pkg}",
    "gocover", "cover.out",
    run_command="go test -count=1 -run {names} {pkg}",
    setup_command="go test -count=1 -run ^$ ./...",
    build_command="go test -count=1 -run ^$ ./...",   # compiles every package and its tests
    vars=_vars,
)]

SPEC = Spec(
    name="go",
    grammars={".go": "go"},
    test_globs=["*_test.go"],
    markers=["go.mod"],
    source_dirs=["."],
    tests_dirs=["."],
    function_types={"function_declaration", "method_declaration", "func_literal"},
    decl_types={"package_clause", "import_declaration", "type_declaration", "const_declaration"},
    imports=imports, dynamic=dynamic, prepare=prepare, resolve=resolve, extra_deps=extra_deps, mutant=mutant,
    runners=RUNNERS,
)
