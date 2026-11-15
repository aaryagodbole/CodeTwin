"""Read test outcomes from JUnit XML reports (written by pytest, Jest, Vitest, Mocha, Maven, Gradle, go-junit-report,
cargo-nextest, dotnet, PHPUnit and most CI systems), mapped to the repository's test files."""
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET  # noqa: S405


def _to_file(case: ET.Element, tests: list[str]) -> str | None:
    f = case.get("file")
    if f:
        f = f.replace("\\", "/").lstrip("./")
        hits = [t for t in tests if t == f or t.endswith("/" + f) or f.endswith("/" + t)]
        if hits:
            return hits[0]
    cls = (case.get("classname") or "").replace("\\", "/")
    if cls:
        dotted = cls.replace(".", "/")
        last = cls.split(".")[-1].split("/")[-1]
        for t in tests:
            stem = t.rsplit("/", 1)[-1].split(".")[0]
            if t.rsplit(".", 1)[0].endswith(dotted) or stem == last:
                return t
    return f


def read(paths: list[Path], tests: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Test file -> failing cases ([] = passed), and the cases that could not be mapped to a test file."""
    out: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for p in paths:
        root = ET.parse(p).getroot()  # noqa: S314 - local CI artefacts
        for case in root.iter("testcase"):
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            f = _to_file(case, tests)
            if f is None:
                unmapped.append(name)
                continue
            out.setdefault(f, [])
            if case.find("failure") is not None or case.find("error") is not None:
                out[f].append(f"{f}::{case.get('name', '')}")
    return out, unmapped
