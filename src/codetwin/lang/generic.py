"""Any language: syntax trees from tree-sitter, per-test coverage from the project's own test runner.

Static facts come from a tree-sitter grammar (tree-sitter-language-pack ships grammars for 300+ languages)
and the language's `Spec`. Coverage comes from running each test file on its own with a command template
that writes a coverage report in one of the formats of `coverage_formats.py`. Pass/fail is taken from JUnit
XML when the runner writes it, otherwise from the exit code.

Settings in `.codetwin.toml` (all optional when a runner preset matches the project):

    [project]
    language = "javascript"
    source_dirs = ["src"]
    tests_dir = "tests"              # may be "." when tests sit next to the sources

    [runner]
    test_command = "npx jest --coverage --coverageReporters=lcov --coverageDirectory={cov_dir} {test}"
    coverage_format = "lcov"         # lcov | gocover | jacoco | cobertura | clover
    coverage_file = "lcov.info"      # glob under {cov_dir}
    run_command = "npx jest {test}"  # without coverage, for weakcheck
    setup_command = ""               # once before a recorded run (install, compile)
    build_command = ""               # does a mutated copy compile? (weakcheck)
    test_globs = ["**/*.test.ts"]
    workers = 1
    timeout = 600                    # seconds per test file
"""
from __future__ import annotations

import os
import posixpath
import shlex
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from xml.etree import ElementTree as ET  # noqa: S405

from ..evidence.model import FileFacts, TestRun
from . import auto
from . import coverage_formats as covfmt
from .base import Language, glob_match, repo_files, under
from .spec import Runner, Spec

BODY_TYPES = {"function_body", "block", "compound_statement", "body_statement", "statement_block"}


class TreeSitterMissing(RuntimeError):
    pass


@cache
def parser_for(grammar: str):
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise TreeSitterMissing("languages other than Python need tree-sitter: pip install 'codetwin[languages]'") from e
    return get_parser(grammar)


def parse(grammar: str, src: bytes):
    return parser_for(grammar).parse(src)


def walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def line(node) -> int:
    return node.start_point[0] + 1


def end_line(node) -> int:
    return node.end_point[0] + 1


@dataclass
class Index:
    """What import resolution may look at: all files of the project and per-spec precomputed data."""
    root: Path
    files: set[str]
    names: dict[str, set[str]] = field(default_factory=dict)     # file -> identifiers it references
    data: dict = field(default_factory=dict)


class Generic(Language):
    def __init__(self, cfg, spec: Spec):
        super().__init__(cfg)
        self.spec = spec
        self.name = spec.name
        self.extensions = tuple(spec.grammars)
        r = cfg.raw.get("runner", {}) if isinstance(cfg.raw.get("runner", {}), dict) else {}
        self.opts = r
        self.test_globs = list(r.get("test_globs", spec.test_globs))
        self._runners: dict[str, Runner | None] = {}
        self._mappers: dict[str, covfmt.PathMapper] = {}
        self.runner = self.runner_for("")

    # --------------------------------------------------------------- configuration
    def project_dir(self, path: str) -> str:
        """The folder a test runs from: the nearest one above it with a build file of this language
        (`web/` with its package.json in a monorepo, a Go module, a Maven module), else the repository root.
        A configured `test_command` always runs from the repository root."""
        if self.opts.get("test_command") or not self.spec.markers:
            return ""
        d = posixpath.dirname(path.split("::", 1)[0])
        while d:
            if any(self._has_marker(self.root / d, m) for m in self.spec.markers):
                return d
            d = posixpath.dirname(d)
        return ""

    @staticmethod
    def _has_marker(folder: Path, marker: str) -> bool:
        return any(folder.glob(marker)) if "*" in marker else (folder / marker).exists()

    def runner_for(self, path_or_dir: str, is_dir: bool = True) -> Runner | None:
        d = path_or_dir if is_dir else self.project_dir(path_or_dir)
        if d not in self._runners:
            self._runners[d] = self._runner(self.root / d)
        return self._runners[d]

    def _runner(self, base: Path) -> Runner | None:
        r = self.opts
        preset = next((x for x in self.spec.runners if (r.get("preset") or "") == x.name), None)
        if preset is None and not r.get("test_command"):
            preset = next((x for x in self.spec.runners if x.detect(base)), None)
        if r.get("test_command"):
            tpl = preset or Runner("custom", "", r.get("coverage_format", "lcov"))
            return Runner(name=tpl.name if preset else "custom", test_command=r["test_command"],
                          coverage_format=r.get("coverage_format", tpl.coverage_format),
                          coverage_file=r.get("coverage_file", tpl.coverage_file),
                          run_command=r.get("run_command", tpl.run_command if preset else None),
                          setup_command=r.get("setup_command", tpl.setup_command),
                          build_command=r.get("build_command", tpl.build_command),
                          result_glob=r.get("result_glob", tpl.result_glob), vars=tpl.vars,
                          env={**(tpl.env or {}), **r.get("env", {})})
        if preset is None:
            return None
        # presets are shared module-level objects: override on a copy
        return replace(preset, **{k: r[k] for k in ("coverage_file", "run_command", "setup_command", "build_command",
                                                    "result_glob") if k in r})

    def describe(self) -> str:
        return f"{self.name} ({self.runner.name if self.runner else 'no test runner: static evidence only'})"

    def grammar(self, path: str) -> str | None:
        for ext, g in self.spec.grammars.items():
            if path.endswith(ext):
                return g
        return None

    # --------------------------------------------------------------- files
    def is_test(self, path: str) -> bool:
        td = self.cfg.tests_dir.strip("/")
        in_tests = td not in ("", ".") and (path.startswith(td + "/"))
        return path.endswith(self.extensions) and (glob_match(path, self.test_globs) or
                                                   (in_tests and not self.test_globs))

    def is_source(self, path: str) -> bool:
        return path.endswith(self.extensions) and not self.is_test(path) and under(path, self.cfg.source_dirs)

    def _all_files(self) -> list[str]:
        if not self.cfg.source_dirs:            # nothing configured: the whole repository
            return repo_files(self.root, self.extensions)
        dirs = sorted(set(self.cfg.source_dirs + ([self.cfg.tests_dir] if self.cfg.tests_dir else [])))
        return repo_files(self.root, self.extensions, [d for d in dirs if d] or ["."])

    def list_tests(self) -> list[str]:
        files = self._all_files()
        tests = [f for f in files if self.is_test(f)]
        if self.spec.test_ids:
            for f in files:
                if not self.is_test(f):
                    tests.extend(self.spec.test_ids(self.root, f))
        return sorted(tests)

    # --------------------------------------------------------------- static facts
    def file_facts(self, path: str, src: bytes) -> tuple[FileFacts, list[str], set[str]]:
        """Facts of one file, its raw import strings and the identifiers it references."""
        g = self.grammar(path)
        if g is None:
            return FileFacts(dynamic=["unparsed"]), [], set()
        tree = parse(g, src)
        sp = self.spec
        raw: list[str] = []
        names: set[str] = set()
        dyn: set[str] = set()
        dyn_lines: set[int] = set()
        defs: list[list[int]] = []
        for n in walk(tree.root_node):
            if sp.imports:
                got = sp.imports(n, src)
                if got:
                    raw.extend(got)
            if sp.dynamic:
                k = sp.dynamic(n, src)
                if k:
                    dyn.add(k)
                    dyn_lines.add(line(n))
            if sp.names:
                nm = sp.names(n, src)
                if nm:
                    names.add(nm)
            if n.type in sp.function_types or (sp.auto and auto.is_function(n.type)):
                body = n.child_by_field_name("body") or next(
                    (c for c in n.named_children if c.type in BODY_TYPES), None)
                if body is not None:
                    # brace-delimited body: the first statement; expression body (arrow function): the body itself
                    stmts = [c for c in body.named_children if c.type not in sp.comment_types]
                    braced = bool(body.children) and body.children[0].type == "{"
                    first_line = line(stmts[0]) if braced and stmts else (end_line(body) if braced else line(body))
                    defs.append([line(n), end_line(n), first_line])
        if tree.root_node.has_error:
            dyn.add("parse-error")
        mod_lines: set[int] = set(sp.load_time(tree.root_node, src)) if sp.load_time else set()
        stack = [] if sp.load_time else list(reversed(tree.root_node.named_children))
        while stack:
            ch = stack.pop()
            if ch.type in sp.container_types:
                stack.extend(reversed(ch.named_children))
                continue
            if ch.type in sp.comment_types or ch.type in sp.decl_types or ch.type in sp.function_types:
                continue
            if sp.auto and (auto.is_function(ch.type) or auto.IMPORT.search(ch.type)
                            or any(k in ch.type for k in ("class", "module", "struct", "interface", "type", "package"))):
                continue
            mod_lines.update(range(line(ch), end_line(ch) + 1))
        return (FileFacts(imports=sorted(set(raw)), dynamic=sorted(dyn), dyn_lines=sorted(dyn_lines),
                          defs=sorted(defs), mod_lines=sorted(mod_lines)), raw, names)

    def facts(self) -> dict[str, FileFacts]:
        files = self._all_files()
        out: dict[str, FileFacts] = {}
        raws: dict[str, list[str]] = {}
        idx = Index(self.root, set(files))
        for f in files:
            src = (self.root / f).read_bytes()
            facts, raw, names = self.file_facts(f, src)
            out[f], raws[f] = facts, raw
            idx.names[f] = names
        if self.spec.prepare:
            self.spec.prepare(idx)
        for f, facts in out.items():
            deps: list[str] = []
            for r in raws[f]:
                for t in (self.spec.resolve(r, f, idx) if self.spec.resolve else []):
                    if t != f and t not in deps:
                        deps.append(t)
            for t in (self.spec.extra_deps(f, idx) if self.spec.extra_deps else []):
                if t != f and t not in deps:
                    deps.append(t)
            facts.deps = deps
        return out

    # --------------------------------------------------------------- running tests
    def _require_runner(self, test: str = "") -> Runner:
        r = self.runner_for(test, is_dir=False) if test else self.runner
        if r is None:
            raise RuntimeError(f"no test runner preset matched this {self.name} project; set [runner] test_command "
                               "and coverage_format in .codetwin.toml (see docs/languages.md)")
        return r

    def _vars(self, test: str, cwd: Path, r: Runner) -> dict[str, str | list[str]]:
        """Template values for one test id, relative to the folder the test runs from (`cwd`). Ids are file
        paths, or `path::name` for tests inside a source file."""
        path = test.split("::", 1)[0]
        v: dict[str, str | list[str]] = {"test": test, "test_file": path, "test_stem": self.stem(path),
                                         "test_dir": os.path.dirname(path) or "."}
        if r.vars:
            try:
                src = (cwd / path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                src = ""
            v.update(r.vars(test, src))
        return v

    @staticmethod
    def _argv(template: str, values: dict) -> list[str]:
        """Split a command template (no shell) and fill its placeholders. A token that is exactly `{name}`
        with a list value expands to several arguments (possibly none)."""
        out: list[str] = []
        for tok in shlex.split(template):
            if tok.startswith("{") and tok.endswith("}") and isinstance(values.get(tok[1:-1]), list):
                out.extend(values[tok[1:-1]])
            else:
                out.append(tok.format(**values))
        return out

    def _timeout(self, default: int) -> int:
        return int(self.opts.get("timeout", default))

    def _setup(self, cwd: Path, r: Runner, timeout: int) -> None:
        if r.setup_command:
            subprocess.run(self._argv(r.setup_command, {}), cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, check=False)

    @staticmethod
    def _junit_failed(paths: list[Path]) -> bool | None:
        """True if a JUnit report has a failure/error, False if reports exist without one, None if none exist."""
        seen = False
        for p in paths:
            try:
                root = ET.parse(p).getroot()  # noqa: S314
            except ET.ParseError:
                continue
            seen = True
            if any(ch.tag in ("failure", "error") for tc in root.iter("testcase") for ch in tc):
                return True
        return False if seen else None

    def _mapper(self, pdir: str) -> covfmt.PathMapper:
        if pdir not in self._mappers:
            known = [f for f in repo_files(self.root, self.extensions) if not self.is_test(f)]
            self._mappers[pdir] = covfmt.PathMapper(self.root, known, self.root / pdir)
        return self._mappers[pdir]

    def _run_one(self, test: str, base: Path, timeout: int, coverage: bool) -> tuple[str, float, bool | None, dict]:
        r = self._require_runner(test)
        pdir = self.project_dir(test)
        cwd = base / pdir
        local = test[len(pdir) + 1:] if pdir else test        # the test id as seen from its project folder
        with tempfile.TemporaryDirectory(prefix="codetwin-cov-") as tmp:
            cov = Path(tmp)
            values = dict(self._vars(local, cwd, r), cov_dir=str(cov))
            template = r.test_command if coverage or not r.run_command else r.run_command
            in_project = r.coverage_file.startswith("./") if r.coverage_file else False
            for pattern in [r.result_glob, r.coverage_file[2:] if in_project and r.coverage_file else None]:
                for old in (cwd.glob(pattern) if pattern else []):      # stale reports of an earlier run
                    old.unlink(missing_ok=True)
            env = dict(os.environ, **{k: v.format(**values) for k, v in (r.env or {}).items()})
            argv = self._argv(template, values)
            t0 = time.time()
            output, rc = "", "timeout"
            try:
                proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False,
                                      stdin=subprocess.DEVNULL, env=env)
                ok: bool | None = proc.returncode == 0
                output, rc = proc.stdout + proc.stderr, str(proc.returncode)
            except subprocess.TimeoutExpired as e:
                ok = None
                output = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else str(e.stdout or "")
            dt = time.time() - t0
            if r.result_glob and ok is not None:
                jf = self._junit_failed(sorted(cwd.glob(r.result_glob)))
                if jf is not None:
                    ok = not jf
            lines: dict = {}
            if coverage:
                where, pattern = (cwd, r.coverage_file[2:]) if in_project and r.coverage_file else (cov, r.coverage_file)
                lines = covfmt.read_dir(r.coverage_format, where, pattern, self._mapper(pdir))
            if ok is not True or (coverage and not lines):
                self._log(test, argv, cwd, rc, output, sorted(str(p.relative_to(cov)) for p in cov.rglob("*")))
            return test, dt, ok, lines

    def _log(self, test: str, argv: list[str], cwd: Path, rc: str, output: str, produced: list[str]) -> None:
        """Append a failed or coverage-less run to .codetwin/runner.log (the output of the test runner is the
        only way to see why a runner preset did not fit a project)."""
        try:
            d = self.root / ".codetwin"
            d.mkdir(exist_ok=True)
            with (d / "runner.log").open("a", encoding="utf-8") as f:
                f.write(f"\n=== {test}  (exit {rc}, cwd {cwd})\n$ {shlex.join(argv)}\nfiles in cov_dir: {produced[:20]}\n"
                        f"{output[-6000:]}\n")
        except OSError:
            pass

    def run_suite(self, sha: str, tests: list[str] | None = None, timeout: int = 3600) -> TestRun:
        tests = tests if tests is not None else self.list_tests()
        # Static-evidence mode for tests whose project has no known test runner: listed, not run, no coverage;
        # decisions on files without runtime evidence say so and run everything.
        runnable = [t for t in tests if self.runner_for(t, is_dir=False) is not None]
        run = TestRun(sha=sha, durations={t: 1.0 for t in tests if t not in runnable})
        if not runnable:
            run.returncode = "no-runner"
            return run
        per = self._timeout(min(timeout, 600))
        t0 = time.time()
        for pdir in sorted({self.project_dir(t) for t in runnable}):
            self._setup(self.root / pdir, self.runner_for(pdir), timeout)  # type: ignore[arg-type]
        workers = max(1, int(self.opts.get("workers", 1)))
        with ThreadPoolExecutor(workers) as ex:
            results = list(ex.map(lambda t: self._run_one(t, self.root, per, True), runnable))
        for test, dt, ok, lines in results:
            run.durations[test] = dt
            if ok is not True:
                run.failing.append(f"{test}::" + ("timeout" if ok is None else "failed"))
            run.covered[test] = {f: sorted(ls) for f, ls in lines.items() if not self.is_test(f)}
        run.returncode = 0 if not run.failing else 1
        run.wall = time.time() - t0
        return run

    def run_tests(self, work: Path, tests: list[str], timeout: int) -> dict[str, bool | None]:
        return {t: (self._run_one(t, work, self._timeout(timeout), False)[2]
                    if self.runner_for(t, is_dir=False) is not None else None) for t in tests}

    def has_runtime_evidence(self, path: str) -> bool:
        return self.runner_for(path, is_dir=False) is not None

    def run_all(self, work: Path, tests: list[str], timeout: int) -> bool:
        for t in tests:
            self._require_runner(t)
        return super().run_all(work, tests, timeout)

    def build_ok(self, work: Path, timeout: int) -> bool:
        for pdir in sorted({self.project_dir(t) for t in self.list_tests()}):
            r = self.runner_for(pdir)
            if r is None or not r.build_command:
                continue
            try:
                p = subprocess.run(self._argv(r.build_command, {}), cwd=work / pdir, capture_output=True, text=True,
                                   timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                return False
            if p.returncode != 0:
                return False
        return True

    # --------------------------------------------------------------- no-ops and mutants
    def _tokens(self, path: str, src: str, strip_annotations: bool) -> list[tuple[str, str]] | None:
        g = self.grammar(path)
        if g is None:
            return None
        b = src.encode("utf-8")
        tree = parse(g, b)
        if tree.root_node.has_error:
            return None
        skip = set(self.spec.comment_types) | (self.spec.annotation_types if strip_annotations else set())
        out: list[tuple[str, str]] = []
        stack = [tree.root_node]
        while stack:
            n = stack.pop()
            if n.type in skip or "comment" in n.type:
                continue
            if n.child_count == 0:
                out.append((n.type, text(n, b)))
            else:
                stack.extend(reversed(n.children))
        return out

    def classify_source(self, old: str, new: str, path: str) -> str:
        a, b = self._tokens(path, old, False), self._tokens(path, new, False)
        if a is None or b is None:
            return "unparsable"
        if a == b:
            return "noop"
        if self.spec.annotation_types and self._tokens(path, old, True) == self._tokens(path, new, True):
            return "annotation"
        return "semantic"

    def extreme_mutant(self, text_: str, fn: list[int], path: str) -> str | None:
        g = self.grammar(path)
        if g is None or self.spec.mutant is None:
            return None
        b = text_.encode("utf-8")
        tree = parse(g, b)
        best = None
        for n in walk(tree.root_node):
            if (n.type in self.spec.function_types or (self.spec.auto and auto.is_function(n.type))) \
                    and line(n) == fn[0] and end_line(n) == fn[1]:
                best = n
        if best is None:
            return None
        edit = self.spec.mutant(best, b, path)
        if edit is None:
            return None
        s, e, rep = edit
        return (b[:s] + rep.encode("utf-8") + b[e:]).decode("utf-8")

    # --------------------------------------------------------------- init
    def guess_config(self) -> dict:
        # the first candidate that exists (src/main/java before src); "." when none does
        dirs = next(([d] for d in self.spec.source_dirs if (self.root / d).is_dir()), ["."])
        tests = next((d for d in self.spec.tests_dirs if (self.root / d).is_dir()), ".")
        return {"source_dirs": dirs, "tests_dir": tests,
                "runner": self.runner.name if self.runner else None}

