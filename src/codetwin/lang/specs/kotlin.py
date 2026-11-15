"""Kotlin (JVM): JUnit through Gradle or Maven with JaCoCo, like Java; imports resolve by package and file name.

Files of one package see each other without imports, so a file also depends on same-package files whose
names it mentions. Weakcheck mutants return a zero value early from block-bodied functions with a declared
primitive, String, Unit or nullable type.
"""
from __future__ import annotations

from ..spec import Spec
from . import java
from ._util import txt


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "import_header":
        ident = next((c for c in n.named_children if c.type == "identifier"), None)
        if ident is None:
            return None
        star = any(c.type == "wildcard_import" or txt(c, src) == ".*" for c in n.children)
        return [txt(ident, src) + (".*" if star else "")]
    return None


def names(n, src: bytes) -> str | None:
    if n.type in ("type_identifier", "simple_identifier"):
        t = txt(n, src)
        return t if t[:1].isupper() else None
    return None


def dynamic(n, src: bytes) -> str | None:
    if n.type == "call_expression":
        t = txt(n, src)
        if "Class.forName" in t or ".getMethod(" in t or ".callBy(" in t or "::class.java.getDeclared" in t:
            return "reflection"
    return None


KT_DEFAULTS = {"Int": "0", "Long": "0L", "Short": "0", "Byte": "0", "Double": "0.0", "Float": "0f",
               "Boolean": "false", "String": '""', "Char": "'\\u0000'"}


def mutant(fn, src: bytes, path: str) -> tuple[int, int, str] | None:
    """`if (true) return <zero value>` first in a block body (null for nullable types)."""
    if fn.type != "function_declaration":
        return None
    body = next((c for c in fn.named_children if c.type == "function_body"), None)
    if body is None or not body.children or body.children[0].type != "{":
        return None                      # expression bodies: the type is often inferred
    typ = next((c for c in fn.named_children if c.type in ("user_type", "nullable_type")), None)
    if typ is None:
        value = ""
    elif typ.type == "nullable_type":
        value = " null"
    elif txt(typ, src) in KT_DEFAULTS:
        value = " " + KT_DEFAULTS[txt(typ, src)]
    elif txt(typ, src) == "Unit":
        value = ""
    else:
        return None
    at = body.children[0].end_byte
    return at, at, f" if (true) return{value}; "


SPEC = Spec(
    name="kotlin",
    grammars={".kt": "kotlin", ".kts": "kotlin"},
    test_globs=["**/src/test/**/*Test.kt", "**/src/test/**/*Tests.kt", "**/src/*Test/**/*Test.kt"],
    markers=["settings.gradle.kts"],
    source_dirs=["src/main/kotlin", "src"],
    tests_dirs=["src/test/kotlin", "src/test"],
    function_types={"function_declaration", "anonymous_function", "lambda_literal"},
    decl_types={"package_header", "import_list", "function_declaration", "class_declaration", "object_declaration",
                "type_alias", "file_annotation", "shebang_line"},
    imports=imports, dynamic=dynamic, names=names, prepare=java.prepare, resolve=java.resolve,
    extra_deps=java.extra_deps, mutant=mutant, runners=java.RUNNERS,
)
