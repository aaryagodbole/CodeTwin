"""Readers for the coverage formats that nearly every toolchain can write.

Each reader returns {repository-relative source path: set of executed line numbers}. Paths that cannot be
mapped into the repository (dependencies, generated files) are dropped.

| format    | written by (examples)                                                          |
|-----------|--------------------------------------------------------------------------------|
| lcov      | Jest, Vitest, c8/nyc (JS/TS), cargo-llvm-cov (Rust), gcov/lcov (C/C++), SimpleCov, coverlet, Kover, Swift |
| gocover   | `go test -coverprofile`                                                         |
| jacoco    | JaCoCo XML (Java, Kotlin, Scala on the JVM)                                     |
| cobertura | coverlet, coverage.py, gcovr, PHPUnit, istanbul                                 |
| clover    | PHPUnit, istanbul                                                               |
"""
from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree as ET  # noqa: S405  (reports written by our own test runs)

Lines = dict[str, set[int]]


class PathMapper:
    """Map a path from a coverage report to a repository-relative path."""

    def __init__(self, root: Path, known: list[str], cwd: Path | None = None):
        self.root = root.resolve()
        self.cwd = (cwd or root).resolve()
        self.known = set(known)
        self.by_suffix: dict[str, list[str]] = {}
        for f in known:
            parts = f.split("/")
            for k in range(1, len(parts) + 1):
                self.by_suffix.setdefault("/".join(parts[-k:]), []).append(f)

    def __call__(self, p: str) -> str | None:
        p = p.replace("\\", "/")
        if p.startswith("file://"):
            p = p[7:]
        cands = []
        base = Path(p) if os.path.isabs(p) else self.cwd / p
        with contextlib.suppress(ValueError):
            cands.append(base.resolve().relative_to(self.root).as_posix())
        if not os.path.isabs(p):
            cands.append(p[2:] if p.startswith("./") else p)
        for c in cands:
            if c in self.known:
                return c
        # unique suffix match (e.g. JaCoCo `com/acme/Foo.java`, Go `module/path/foo.go`)
        parts = p.strip("/").split("/")
        for k in range(len(parts), 0, -1):
            hit = self.by_suffix.get("/".join(parts[-k:]))
            if hit and len(hit) == 1:
                return hit[0]
            if hit and len(hit) > 1:
                return None
        return None


def read_lcov(text: str, mapper: Callable[[str], str | None]) -> Lines:
    out: Lines = {}
    cur: str | None = None
    for line in text.splitlines():
        if line.startswith("SF:"):
            cur = mapper(line[3:].strip())
        elif line.startswith("DA:") and cur:
            parts = line[3:].split(",")
            try:
                if int(float(parts[1])) > 0:
                    out.setdefault(cur, set()).add(int(parts[0]))
            except (IndexError, ValueError):
                continue
        elif line.startswith("end_of_record"):
            cur = None
    return out


GO_LINE = re.compile(r"^(.+?):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)$")


def read_gocover(text: str, mapper: Callable[[str], str | None]) -> Lines:
    out: Lines = {}
    for line in text.splitlines():
        m = GO_LINE.match(line.strip())
        if not m or int(m.group(4)) == 0:
            continue
        f = mapper(m.group(1))
        if f:
            out.setdefault(f, set()).update(range(int(m.group(2)), int(m.group(3)) + 1))
    return out


def read_jacoco(text: str, mapper: Callable[[str], str | None]) -> Lines:
    out: Lines = {}
    root = ET.fromstring(text)  # noqa: S314
    for pkg in root.iter("package"):
        pname = pkg.get("name", "")
        for sf in pkg.iter("sourcefile"):
            f = mapper(f"{pname}/{sf.get('name')}" if pname else sf.get("name", ""))
            if not f:
                continue
            for ln in sf.iter("line"):
                if int(ln.get("ci", "0")) > 0:
                    out.setdefault(f, set()).add(int(ln.get("nr", "0")))
    return out


def read_cobertura(text: str, mapper: Callable[[str], str | None]) -> Lines:
    out: Lines = {}
    root = ET.fromstring(text)  # noqa: S314
    sources = [s.text.strip() for s in root.iter("source") if s.text]
    for cls in root.iter("class"):
        name = cls.get("filename", "")
        f = None
        for s in sources + [""]:
            f = mapper(os.path.join(s, name) if s else name)
            if f:
                break
        if not f:
            continue
        for ln in cls.iter("line"):
            if int(ln.get("hits", "0")) > 0:
                out.setdefault(f, set()).add(int(ln.get("number", "0")))
    return out


def read_clover(text: str, mapper: Callable[[str], str | None]) -> Lines:
    out: Lines = {}
    root = ET.fromstring(text)  # noqa: S314
    for fe in root.iter("file"):
        f = mapper(fe.get("path") or fe.get("name") or "")
        if not f:
            continue
        for ln in fe.iter("line"):
            if int(ln.get("count", "0")) > 0:
                out.setdefault(f, set()).add(int(ln.get("num", "0")))
    return out


READERS: dict[str, Callable[[str, Callable[[str], str | None]], Lines]] = {
    "lcov": read_lcov, "gocover": read_gocover, "jacoco": read_jacoco, "cobertura": read_cobertura, "clover": read_clover,
}

DEFAULT_FILES = {"lcov": "**/lcov.info", "gocover": "cover.out", "jacoco": "**/jacoco*.xml",
                 "cobertura": "**/cobertura*.xml", "clover": "**/clover.xml"}


def read_dir(fmt: str, cov_dir: Path, pattern: str | None, mapper: Callable[[str], str | None]) -> Lines:
    """Merge every report matching `pattern` under `cov_dir`."""
    reader = READERS[fmt]
    out: Lines = {}
    for p in sorted(cov_dir.glob(pattern or DEFAULT_FILES[fmt])):
        try:
            part = reader(p.read_text(encoding="utf-8", errors="replace"), mapper)
        except ET.ParseError:
            continue
        for f, ls in part.items():
            out.setdefault(f, set()).update(ls)
    return out
