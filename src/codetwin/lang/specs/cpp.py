"""C and C++: `#include "..."` dependencies (and the matching implementation file of a header).

There is no common test runner, so set `[runner] test_command` (one test file per run, writing LCOV via
gcov/lcov, llvm-cov or gcovr) and `coverage_format` yourself; see docs/languages.md for an example.
`dlopen`/`dlsym` and `GetProcAddress` are reported as dynamic.
"""
from __future__ import annotations

import posixpath

from ..spec import Spec
from ._util import leading_insert, rel_join, string_value, txt

HEADERS = (".h", ".hh", ".hpp", ".hxx", ".h++")
IMPLS = (".c", ".cc", ".cpp", ".cxx", ".c++")


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "preproc_include":
        p = n.child_by_field_name("path")
        if p is not None and p.type == "string_literal":
            s = string_value(p, src)
            return [s] if s else None
    return None


def dynamic(n, src: bytes) -> str | None:
    if n.type == "call_expression":
        fn = n.child_by_field_name("function")
        if fn is not None and txt(fn, src) in ("dlopen", "dlsym", "GetProcAddress", "LoadLibrary", "LoadLibraryA"):
            return "dlopen"
    return None


def prepare(idx) -> None:
    by_name: dict[str, list[str]] = {}
    for f in idx.files:
        by_name.setdefault(posixpath.basename(f), []).append(f)
    idx.data["by_name"] = by_name


def resolve(spec: str, from_file: str, idx) -> list[str]:
    hits = []
    rel = rel_join(from_file, spec)
    if rel in idx.files:
        hits = [rel]
    else:
        # include directories are unknown without the build system: accept a unique match by path suffix
        cands = [f for f in idx.data["by_name"].get(posixpath.basename(spec), []) if f.endswith("/" + spec) or f == spec]
        hits = cands if len(cands) == 1 else []
    out = list(hits)
    for h in hits:          # a header's implementation lives next to it (or in a sibling src/ folder)
        stem = posixpath.splitext(h)[0]
        if h.endswith(HEADERS):
            out += [stem + e for e in IMPLS if stem + e in idx.files]
            name = posixpath.basename(stem)
            out += [f for f in idx.files if f.endswith(IMPLS) and posixpath.splitext(posixpath.basename(f))[0] == name
                    and f not in out and len(idx.data["by_name"].get(posixpath.basename(f), [])) == 1]
    return out


C_SCALARS = {"int", "long", "short", "char", "unsigned", "signed", "float", "double", "size_t", "ssize_t", "bool",
             "_Bool", "uint8_t", "uint16_t", "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t"}


def mutant(fn, src: bytes, path: str) -> tuple[int, int, str] | None:
    """`return;` / `return 0;` (C scalars and pointers) / `return {};` (C++ value-initialisation) first."""
    if fn.type != "function_definition":
        return None
    body = fn.child_by_field_name("body")
    typ = fn.child_by_field_name("type")
    decl = fn.child_by_field_name("declarator")
    if body is None or typ is None:
        return None                      # constructors, destructors
    t = txt(typ, src).replace("const", "").strip()
    pointer = decl is not None and txt(decl, src).lstrip().startswith("*")
    if t == "void" and not pointer:
        stmt = "return;"
    elif pointer or t.split()[-1] in C_SCALARS:
        stmt = "return 0;"
    elif path.endswith(".c"):
        return None                      # a C struct has no literal zero value
    else:
        stmt = "return {};"
    return leading_insert(body, src, stmt)


SPEC = Spec(
    name="cpp",
    grammars={".c": "c", ".h": "cpp", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".c++": "cpp", ".hh": "cpp",
              ".hpp": "cpp", ".hxx": "cpp"},
    test_globs=["**/test/**/*.*", "**/tests/**/*.*", "*_test.*", "test_*.*", "*_unittest.*", "*Test.*"],
    markers=["CMakeLists.txt", "meson.build", "configure.ac"],
    source_dirs=["src", "lib", "include", "."],
    tests_dirs=["test", "tests"],
    function_types={"function_definition", "lambda_expression"},
    decl_types={"preproc_include", "preproc_def", "preproc_function_def", "preproc_call", "function_definition",
                "type_definition", "struct_specifier", "class_specifier", "enum_specifier", "union_specifier",
                "using_declaration", "alias_declaration", "namespace_alias_definition", "static_assert_declaration",
                "concept_definition", "template_instantiation"},
    container_types={"preproc_ifdef", "preproc_if", "preproc_else", "preproc_elif", "namespace_definition",
                     "declaration_list", "linkage_specification", "template_declaration"},
    imports=imports, dynamic=dynamic, prepare=prepare, resolve=resolve, mutant=mutant,
)
