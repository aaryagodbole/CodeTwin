"""PHP: PHPUnit (needs Xdebug or PCOV for coverage), Clover XML.

`use` statements resolve PSR-4 style (the file whose path ends with the namespace path of the class);
`require`/`include` with a literal path resolve relative to the file. Variable functions, `call_user_func`
and `eval` are reported as dynamic.
"""
from __future__ import annotations

from ..spec import Runner, Spec
from ._util import rel_join, txt

DYNAMIC = {"call_user_func", "call_user_func_array", "eval", "create_function"}


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "namespace_use_clause":
        return ["use:" + txt(n.named_children[0], src)] if n.named_children else None
    if n.type in ("require_expression", "require_once_expression", "include_expression", "include_once_expression"):
        for s in (c for c in _walk(n) if c.type in ("string_content", "string_value")):
            return ["file:" + txt(s, src)]
    return None


def _walk(n):
    stack = [n]
    while stack:
        x = stack.pop()
        yield x
        stack.extend(x.children)


def dynamic(n, src: bytes) -> str | None:
    if n.type == "function_call_expression":
        fn = n.child_by_field_name("function")
        if fn is not None and (fn.type == "variable_name" or txt(fn, src) in DYNAMIC):
            return "dynamic-call"
    return None


def prepare(idx) -> None:
    idx.data["by_suffix"] = {}
    for f in idx.files:
        parts = f[:-4].split("/")
        for k in range(1, len(parts) + 1):
            idx.data["by_suffix"].setdefault("/".join(parts[-k:]).lower(), []).append(f)


def resolve(spec: str, from_file: str, idx) -> list[str]:
    kind, _, path = spec.partition(":")
    if kind == "file":
        c = rel_join(from_file, path.lstrip("/"))
        return [c] if c in idx.files else []
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    for k in range(len(parts), 0, -1):              # longest namespace suffix that names exactly one file
        hit = idx.data["by_suffix"].get("/".join(parts[-k:]).lower(), [])
        if len(hit) == 1:
            return hit
        if len(hit) > 1:
            break
    return []


RUNNERS = [Runner("phpunit", "vendor/bin/phpunit --coverage-clover {cov_dir}/clover.xml {test}", "clover", "clover.xml",
                  run_command="vendor/bin/phpunit {test}", detect=lambda root: (root / "vendor/bin/phpunit").exists())]

SPEC = Spec(
    name="php",
    grammars={".php": "php"},
    test_globs=["*Test.php"],
    markers=["composer.json"],
    source_dirs=["src", "lib", "app"],
    tests_dirs=["tests", "test"],
    function_types={"function_definition", "method_declaration", "anonymous_function", "arrow_function"},
    decl_types={"php_tag", "namespace_definition", "namespace_use_declaration", "function_definition",
                "class_declaration", "interface_declaration", "trait_declaration", "enum_declaration", "text"},
    imports=imports, dynamic=dynamic, prepare=prepare, resolve=resolve, runners=RUNNERS,
)
