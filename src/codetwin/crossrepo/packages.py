"""The names under which other repositories import this one, read from its build files (any language).

A dependent repository refers to this repository by a package name: a Python top-level package, the `name` of
package.json, the module path of go.mod, the crate name of Cargo.toml, a Java/Kotlin/C# namespace prefix, a
Ruby gem or a PHP namespace. `[crossrepo] packages = [...]` overrides the detection.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

SKIP = {".git", "node_modules", "target", "build", "dist", "vendor", ".venv", "venv", "__pycache__", ".codetwin"}


def _files(root: Path, suffixes: tuple[str, ...], limit: int = 4000):
    n = 0
    for p in root.rglob("*"):
        if any(part in SKIP for part in p.relative_to(root).parts):
            continue
        if p.is_file() and p.suffix in suffixes:
            yield p
            n += 1
            if n >= limit:
                return


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _namespace_prefixes(root: Path, suffixes: tuple[str, ...], pattern: str, depth: int) -> list[str]:
    """Most common namespace prefixes declared in source files (`package com.acme.core;` -> com.acme)."""
    rx = re.compile(pattern, re.M)
    c: Counter[str] = Counter()
    for p in _files(root, suffixes):
        if "/test/" in p.as_posix() or "/tests/" in p.as_posix():
            continue
        m = rx.search(_read(p))
        if m:
            c[".".join(m.group(1).replace("\\", ".").split(".")[:depth])] += 1
    return [k for k, _ in c.most_common(3)]


def detect(root: Path, python_packages: list[str] | None = None) -> list[str]:
    root = Path(root)
    names: list[str] = list(python_packages or [])
    pj = root / "package.json"
    if pj.exists():
        try:
            n = json.loads(_read(pj)).get("name")
            if n:
                names.append(n)
        except json.JSONDecodeError:
            pass  # a broken manifest names no package; the other manifests may still name one
    gm = root / "go.mod"
    if gm.exists():
        m = re.search(r"^module\s+(\S+)", _read(gm), re.M)
        if m:
            names.append(m.group(1))
    ct = root / "Cargo.toml"
    if ct.exists():
        try:
            n = tomllib.loads(_read(ct)).get("package", {}).get("name")
            if n:
                names += sorted({n, n.replace("-", "_")})
        except tomllib.TOMLDecodeError:
            pass  # a broken manifest names no package; the other manifests may still name one
    if (root / "pom.xml").exists() or any(root.glob("build.gradle*")) or any(root.glob("settings.gradle*")):
        names += _namespace_prefixes(root, (".java", ".kt"), r"^\s*package\s+([\w.]+)", 2)
    if any(root.glob("*.csproj")) or any(root.glob("*.sln")):
        names += _namespace_prefixes(root, (".cs",), r"^\s*namespace\s+([\w.]+)", 1)
    for gs in root.glob("*.gemspec"):
        m = re.search(r"\.name\s*=\s*['\"]([^'\"]+)", _read(gs))
        if m:
            names.append(m.group(1))
    cj = root / "composer.json"
    if cj.exists():
        try:
            psr = json.loads(_read(cj)).get("autoload", {}).get("psr-4", {})
            names += [k.rstrip("\\") for k in psr]
        except json.JSONDecodeError:
            pass  # a broken manifest names no package; the other manifests may still name one
    if not names and (root / "pyproject.toml").exists():
        try:
            n = tomllib.loads(_read(root / "pyproject.toml")).get("project", {}).get("name")
            if n:
                names.append(n.replace("-", "_"))
        except tomllib.TOMLDecodeError:
            pass  # a broken pyproject.toml names no package
    seen: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    return seen


def matches(import_string: str, package: str) -> bool:
    """Does an import string refer to `package` (itself or something inside it)?"""
    s = import_string.strip().strip("'\"<>")
    if s == package:
        return True
    return any(s.startswith(package + sep) for sep in ("/", ".", "::", "\\"))
