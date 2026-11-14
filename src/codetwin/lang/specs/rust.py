"""Rust: `cargo llvm-cov` (needs `cargo install cargo-llvm-cov`), coverage as LCOV.

Test ids are the integration test files (`tests/*.rs`) and, for unit tests, `path::tests` for every source
file with a `#[cfg(test)]` module. `mod x;` and `use crate::...`/`use <crate name>::...` paths resolve to
files. Mutants are not built (a neutral return value needs `Default`, which not every type has).
"""
from __future__ import annotations

import posixpath
import re
from pathlib import Path

from ..spec import Runner, Spec
from ._util import txt

CFG_TEST = re.compile(r"#\[cfg\(test\)\]")


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "mod_item" and n.child_by_field_name("body") is None:
        name = n.child_by_field_name("name")
        return ["mod:" + txt(name, src)] if name is not None else None
    if n.type == "use_declaration":
        arg = n.child_by_field_name("argument")
        if arg is None:
            return None
        path = arg.child_by_field_name("path") if arg.type in ("scoped_use_list", "use_as_clause") else arg
        return ["use:" + txt(path if path is not None else arg, src)]
    return None


def _crate_name(root: Path) -> str:
    try:
        m = re.search(r'^\s*name\s*=\s*"([^"]+)"', (root / "Cargo.toml").read_text(encoding="utf-8"), re.M)
    except OSError:
        return ""
    return m.group(1).replace("-", "_") if m else ""


def prepare(idx) -> None:
    idx.data["crate"] = _crate_name(idx.root)


def _module_dir(f: str) -> str:
    """Folder that holds the submodules declared in file `f`."""
    d, name = posixpath.split(f)
    stem = posixpath.splitext(name)[0]
    return d if stem in ("lib", "main", "mod") else posixpath.join(d, stem)


def _module_file(files: set[str], d: str, name: str) -> str | None:
    for c in (posixpath.join(d, name + ".rs"), posixpath.join(d, name, "mod.rs")):
        if c in files:
            return c
    return None


def resolve(spec: str, from_file: str, idx) -> list[str]:
    kind, _, path = spec.partition(":")
    if kind == "mod":
        hit = _module_file(idx.files, _module_dir(from_file), path)
        return [hit] if hit else []
    parts = [p for p in path.split("::") if p]
    if not parts:
        return []
    if parts[0] in ("crate", idx.data.get("crate")):
        d, parts = "src", parts[1:]
    elif parts[0] == "self":
        d, parts = _module_dir(from_file), parts[1:]
    elif parts[0] == "super":
        d = posixpath.dirname(_module_dir(from_file))
        parts = parts[1:]
    else:
        return []
    found: list[str] = []
    for p in parts:
        hit = _module_file(idx.files, d, p)
        if not hit:
            break
        found = [hit]
        d = posixpath.join(d, p)
    if not found and spec.split("::")[0].endswith(("crate", idx.data.get("crate") or "\0")):
        found = [f for f in ("src/lib.rs", "src/main.rs") if f in idx.files][:1]
    return found


def test_ids(root: Path, f: str) -> list[str]:
    try:
        return [f + "::tests"] if CFG_TEST.search((root / f).read_text(encoding="utf-8", errors="replace")) else []
    except OSError:
        return []


def _vars(test: str, text: str) -> dict:
    if "::" in test:
        f = test.split("::", 1)[0]
        mod = posixpath.splitext(f[4:] if f.startswith("src/") else f)[0].replace("/", "::")
        mod = re.sub(r"(^|::)(lib|main|mod)$", "", mod)
        return {"target": ["--lib", "--", (mod + "::" if mod else "") + "tests::"]}
    return {"target": ["--test", posixpath.splitext(posixpath.basename(test))[0]]}


RUNNERS = [Runner("cargo-llvm-cov", "cargo llvm-cov --lcov --output-path {cov_dir}/lcov.info {target}", "lcov",
                  "lcov.info", run_command="cargo test {target}", build_command="cargo test --no-run",
                  detect=lambda root: (root / "Cargo.toml").exists(), vars=_vars)]

SPEC = Spec(
    name="rust",
    grammars={".rs": "rust"},
    test_globs=["tests/*.rs", "**/tests/*.rs"],
    markers=["Cargo.toml"],
    source_dirs=["src"],
    tests_dirs=["tests"],
    function_types={"function_item", "closure_expression"},
    decl_types={"use_declaration", "mod_item", "function_item", "struct_item", "enum_item", "impl_item", "trait_item",
                "const_item", "static_item", "type_item", "macro_definition", "attribute_item", "inner_attribute_item",
                "extern_crate_declaration", "union_item", "foreign_mod_item", "macro_invocation"},
    imports=imports, prepare=prepare, resolve=resolve, test_ids=test_ids, runners=RUNNERS,
)
