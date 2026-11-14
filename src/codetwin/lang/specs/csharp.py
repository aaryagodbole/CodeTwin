"""C#: `dotnet test` with the coverlet collector (Cobertura XML), one test class per run.

`using` directives resolve to every file that declares the namespace, and a file depends on files of its own
namespace whose type names it mentions. Reflection (`Type.GetType`, `Activator.CreateInstance`, `Invoke`,
`GetMethod`) is reported as dynamic.
"""
from __future__ import annotations

import posixpath
import re

from ..spec import Runner, Spec
from ._util import txt

NAMESPACE = re.compile(r"^\s*namespace\s+([\w.]+)", re.M)
REFLECT = {"GetType", "CreateInstance", "Invoke", "GetMethod", "GetProperty", "GetField", "Load", "LoadFrom"}


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "using_directive":
        named = [c for c in n.named_children if c.type in ("qualified_name", "identifier")]
        return [txt(named[-1], src)] if named else None
    return None


def dynamic(n, src: bytes) -> str | None:
    if n.type == "invocation_expression":
        fn = n.child_by_field_name("function")
        name = txt(fn, src).rsplit(".", 1)[-1] if fn is not None else ""
        if name in REFLECT:
            return "reflection"
    return None


def names(n, src: bytes) -> str | None:
    if n.type == "identifier":
        t = txt(n, src)
        return t if t[:1].isupper() else None
    return None


def prepare(idx) -> None:
    ns_of: dict[str, str] = {}
    by_ns: dict[str, list[str]] = {}
    for f in sorted(idx.files):
        try:
            m = NAMESPACE.search((idx.root / f).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        ns = m.group(1) if m else ""
        ns_of[f] = ns
        by_ns.setdefault(ns, []).append(f)
    idx.data.update(ns_of=ns_of, by_ns=by_ns)


def resolve(spec: str, from_file: str, idx) -> list[str]:
    files = idx.data["by_ns"].get(spec, [])
    used = idx.names.get(from_file, set())
    # a namespace can be large: depend only on its files whose type name the importing file mentions
    return sorted(f for f in files if posixpath.splitext(posixpath.basename(f))[0] in used)


def extra_deps(f: str, idx) -> list[str]:
    files = idx.data["by_ns"].get(idx.data["ns_of"].get(f, "\0"), [])
    used = idx.names.get(f, set())
    return sorted(x for x in files if posixpath.splitext(posixpath.basename(x))[0] in used)


def _vars(test: str, text: str) -> dict:
    m = NAMESPACE.search(text)
    cls = posixpath.splitext(posixpath.basename(test))[0]
    return {"test_class": f"{m.group(1)}.{cls}" if m else cls}


RUNNERS = [Runner("dotnet",
                  'dotnet test --nologo --filter FullyQualifiedName~{test_class} --collect "XPlat Code Coverage" '
                  "--results-directory {cov_dir}", "cobertura", "**/coverage.cobertura.xml",
                  run_command="dotnet test --nologo --filter FullyQualifiedName~{test_class}",
                  build_command="dotnet build --nologo", vars=_vars,
                  detect=lambda root: any(root.glob("*.sln")) or any(root.glob("**/*.csproj")))]

SPEC = Spec(
    name="csharp",
    grammars={".cs": "csharp"},
    test_globs=["*Tests.cs", "*Test.cs"],
    markers=["global.json", "Directory.Build.props"],
    source_dirs=["src", "."],
    tests_dirs=["tests", "test"],
    function_types={"method_declaration", "constructor_declaration", "local_function_statement", "lambda_expression"},
    decl_types={"using_directive", "namespace_declaration", "file_scoped_namespace_declaration", "class_declaration",
                "interface_declaration", "struct_declaration", "enum_declaration", "record_declaration",
                "delegate_declaration", "extern_alias_directive", "attribute_list"},
    imports=imports, dynamic=dynamic, names=names, prepare=prepare, resolve=resolve, extra_deps=extra_deps,
    runners=RUNNERS,
)
