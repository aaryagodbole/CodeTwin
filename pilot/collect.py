#!/usr/bin/env python3
"""
CodeTwin AI -- data collector (study v2).

For a set of commits of an open-source Python project it records the evidence CodeTwin needs
and the data used as ground truth:
  * per-test-file coverage of source lines (coverage.py dynamic contexts) and run times
  * per-test-case outcomes (pytest junit xml)
  * the git diff (changed source / test files and line numbers) against the evaluated parent
  * static facts of every file: imports, dynamic-call markers AND their line numbers,
    function spans and module-level statement lines (for line-level features and triggers)
  * commit history (for co-change)
  * seeded faults (mutants) on changed lines and the test files that detect them

Two ways of choosing commits:
  history mode : the last N mainline commits that change source files (each commit is
                 compared with the previous chosen one)
  pairs mode   : the (parent, current) commit pairs of the NameRTS replication package
                 (--pairs gt_<project>.json), so that results can be compared with NameRTS

Output: data/<project>/meta.json, data/<project>/snap/<sha>.json (one per checked-out commit),
        data/<project>/commits/<idx>_<sha>.json (one per evaluated change, with mutants).
Sharding: --shard i/k processes the i-th of k contiguous blocks of changes (used to parallelise on GitHub Actions).

Usage:
    python collect.py --project click --commits 250 --shard 0/5
    python collect.py --project loguru --pairs gt_loguru.json --shard 0/4
"""
import argparse, ast, json, os, random, re, shutil, sqlite3, subprocess, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOS = HERE / "repos"
DATA = HERE / "data"

# name: (git url, PYTHONPATH dir, [packages for --cov], tests dir, package source dirs)
PROJECTS = {
    "toy":          (str(Path(os.environ.get("TOY_REPO", "/nonexistent"))), "src", ["toypkg"], "tests", ["src/toypkg"]),
    "click":        ("https://github.com/pallets/click",                "src", ["click"],        "tests",       ["src/click"]),
    "marshmallow":  ("https://github.com/marshmallow-code/marshmallow", "src", ["marshmallow"],  "tests",       ["src/marshmallow"]),
    "toolz":        ("https://github.com/pytoolz/toolz",                 ".",   ["toolz"],        "toolz/tests", ["toolz"]),
    "itsdangerous": ("https://github.com/pallets/itsdangerous",          "src", ["itsdangerous"], "tests",       ["src/itsdangerous"]),
    "dateutil":     ("https://github.com/dateutil/dateutil",             "src", ["dateutil"],     "tests",       ["src/dateutil"]),
    # projects of the NameRTS replication package (pairs mode)
    "loguru":       ("https://github.com/Delgan/loguru",                 ".",   ["loguru"],       "tests",       ["loguru"]),
    "pvlib":        ("https://github.com/pvlib/pvlib-python",            ".",   ["pvlib"],        "tests",       ["pvlib"]),
    "seaborn":      ("https://github.com/mwaskom/seaborn",               ".",   ["seaborn"],      "tests",       ["seaborn"]),
}

MUTANTS_PER_CHANGE = 3

def run(cmd, cwd=None, timeout=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)

def git(repo, *args):
    r = run(["git", *args], cwd=repo)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout

def is_test_path(p, tests_dir):
    name = os.path.basename(p)
    return p.startswith(tests_dir.rstrip("/") + "/") or name.startswith("test_") or name.endswith("_test.py")

def is_src_path(p, src_dirs, tests_dir):
    return p.endswith(".py") and any(p.startswith(d.rstrip("/") + "/") for d in src_dirs) and not is_test_path(p, tests_dir)

# ---------------------------------------------------------------- commits
CUTOFF = "2026-11-10T00:00:00Z"     # newest commit considered: makes the commit list reproducible

def pick_commits(repo, n, src_dirs, tests_dir):
    """Last n mainline commits that change at least one source .py file, oldest first, plus the
    commit just before the first one (baseline). Merge commits are included: most changes land as
    pull-request merges, and their diff against the first parent is the change that entered main."""
    log = git(repo, "log", "--first-parent", f"--before={CUTOFF}", "--format=%H %P", "-n", "6000", "HEAD").splitlines()
    chosen = []
    for line in log:
        sha, *parents = line.split()
        if not parents:
            continue
        files = git(repo, "diff", "--name-only", parents[0], sha).split()
        if any(is_src_path(f, src_dirs, tests_dir) for f in files):
            chosen.append(sha)
        if len(chosen) == n + 1:
            break
    chosen.reverse()
    return chosen

# ---------------------------------------------------------------- diff
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
def diff_lines(repo, a, b):
    """{path: {'old': [...], 'new': [...], 'status': 'M'|'A'|'D'|'R', 'old_path': ...}} for .py files."""
    out = {}
    for line in git(repo, "diff", "--name-status", "-M", a, b).splitlines():
        parts = line.split("\t")
        st, path = parts[0][0], parts[-1]
        if path.endswith(".py"):
            out[path] = {"old": [], "new": [], "status": st, "old_path": parts[1] if st == "R" else path}
    cur = None
    for line in git(repo, "diff", "-U0", "-M", a, b, "--", "*.py").splitlines():
        if line.startswith("+++ "):
            p = line[4:]
            cur = p[2:] if p.startswith("b/") else None
            if cur and cur not in out:
                out[cur] = {"old": [], "new": [], "status": "M", "old_path": cur}
        m = HUNK.match(line)
        if m and cur:
            os_, oc = int(m.group(1)), int(m.group(2) or 1)
            ns, nc = int(m.group(3)), int(m.group(4) or 1)
            out[cur]["old"].extend(range(os_, os_ + oc) if oc else [os_])
            out[cur]["new"].extend(range(ns, ns + nc) if nc else [ns, ns + 1])
    return out

# ---------------------------------------------------------------- static analysis
DYN_CALLS = {"__import__", "eval", "exec", "import_module"}
def analyse_file(path, root, pkgs):
    """imports (absolute module names within pkgs), dynamic markers, and line-level facts."""
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return {"imports": [], "dynamic": ["unparsed"], "defs": [], "dyn_lines": [], "mod_lines": []}
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    mod_parts = rel[:-3].split("/")
    imports, dyn, dyn_lines = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = mod_parts[:-1]
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                modname = ".".join(base) + ("." + node.module if node.module else "")
            else:
                modname = node.module or ""
            imports.add(modname)
            for a in node.names:
                imports.add(modname + "." + a.name)
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            hit = None
            if name in DYN_CALLS:
                hit = name
            if name in ("getattr", "setattr", "hasattr") and len(node.args) >= 2 and not isinstance(node.args[1], ast.Constant):
                hit = "getattr-dynamic"
            if hit:
                dyn.add(hit)
                dyn_lines.add(node.lineno)
    # function spans (decorators included) and statements that run at import time
    defs, mod_lines = [], set()
    def visit_body(body, at_import_time):
        for i, st in enumerate(body):
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([d.lineno for d in st.decorator_list] + [st.lineno])
                defs.append([start, st.end_lineno, st.body[0].lineno])
                if at_import_time:
                    for d in st.decorator_list:          # decorators run at import time
                        mod_lines.update(range(d.lineno, d.end_lineno + 1))
                visit_body(st.body, False)
            elif isinstance(st, ast.ClassDef):
                if at_import_time:
                    for d in st.decorator_list + st.bases + [k.value for k in st.keywords]:
                        mod_lines.update(range(d.lineno, d.end_lineno + 1))
                visit_body(st.body, at_import_time)
            elif at_import_time:
                is_doc = (i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str))
                if isinstance(st, (ast.Import, ast.ImportFrom, ast.Pass)) or is_doc:
                    continue
                if isinstance(st, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(st, "value", None), ast.Constant):
                    continue                              # plain constants: not behaviour-bearing at import
                if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in st.targets):
                    continue
                mod_lines.update(range(st.lineno, st.end_lineno + 1))
            else:
                # nested statements of a function body: walk for nested defs only
                for sub in ast.iter_child_nodes(st):
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        visit_body([sub], False)
    visit_body(tree.body, True)
    keep = sorted(i for i in imports if i and any(i == p or i.startswith(p + ".") for p in pkgs))
    return {"imports": keep, "dynamic": sorted(dyn), "defs": sorted(defs),
            "dyn_lines": sorted(dyn_lines), "mod_lines": sorted(mod_lines)}

def static_snapshot(repo, src_root, pkgs, src_dirs, tests_dir):
    files = {}
    root = repo / src_root if src_root != "." else repo
    for d in list(src_dirs) + [tests_dir]:
        base = repo / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            rel = p.relative_to(repo).as_posix()
            if rel in files:
                continue
            files[rel] = analyse_file(p, root, pkgs)
    return files

# ---------------------------------------------------------------- test runs
def test_env(repo, spec, workdir):
    src_root = spec[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / src_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["COVERAGE_CORE"] = "ctrace"          # per-test contexts need the ctrace core
    env["COVERAGE_FILE"] = str(workdir / ".coverage")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["MPLBACKEND"] = "Agg"
    return env

def junit_file_of(tc, repo):
    f = tc.get("file")
    if not f:
        parts = tc.get("classname", "").replace(".", "/").split("/")
        f = "/".join(parts)
        for k in range(len(parts), 0, -1):
            cand = "/".join(parts[:k]) + ".py"
            if (repo / cand).exists():
                f = cand
                break
    return f.replace(os.sep, "/")

def parse_junit(junit, repo):
    durations, failing, files = {}, set(), set()
    if junit.exists():
        try:
            for tc in ET.parse(junit).getroot().iter("testcase"):
                f = junit_file_of(tc, repo)
                files.add(f)
                durations[f] = durations.get(f, 0.0) + float(tc.get("time", 0) or 0)
                if any(ch.tag in ("failure", "error") for ch in tc):
                    failing.add(f + "::" + tc.get("classname", "") + "::" + tc.get("name", ""))
        except ET.ParseError:
            pass
    return durations, failing, files

PYTEST_BASE = ["-q", "-p", "no:cacheprovider", "--no-header", "-o", "junit_family=xunit1",
               "-o", "filterwarnings=default", "--continue-on-collection-errors"]

def run_tests(repo, spec, timeout, workdir):
    url, src_root, pkgs, tests_dir, src_dirs = spec
    env = test_env(repo, spec, workdir)
    junit, covrc = workdir / "junit.xml", workdir / "coveragerc"
    covrc.write_text("[run]\nbranch = False\nparallel = False\n")
    for f in (workdir / ".coverage", junit):
        if f.exists():
            f.unlink()
    cmd = [sys.executable, "-m", "pytest", tests_dir, *PYTEST_BASE, f"--cov-config={covrc}", "--cov-context=test",
           "--cov-report=", f"--junitxml={junit}"] + [f"--cov={p}" for p in pkgs]
    t0 = time.time()
    try:
        r = run(cmd, cwd=repo, timeout=timeout, env=env)
        rc, tail = r.returncode, (r.stdout + r.stderr)[-800:]
    except subprocess.TimeoutExpired:
        rc, tail = "timeout", ""
    wall = time.time() - t0
    durations, failing, _ = parse_junit(junit, repo)
    outcomes = {f: not any(x.startswith(f + "::") for x in failing) for f in durations}

    covered, import_lines = {}, {}
    covfile = workdir / ".coverage"
    if covfile.exists():
        from coverage.numbits import numbits_to_nums, nums_to_numbits
        con = sqlite3.connect(covfile)
        ctx = dict(con.execute("select id, context from context"))
        files = dict(con.execute("select id, path from file"))
        rows = con.execute("select file_id, context_id, numbits from line_bits").fetchall()
        con.close()
        for fid, cid, bits in rows:
            c = ctx.get(cid, "")
            src = os.path.relpath(files[fid], repo).replace(os.sep, "/")
            if not c or "::" not in c:
                import_lines.setdefault(src, set()).update(numbits_to_nums(bits))
                continue
            testfile = c.split("::")[0].replace(os.sep, "/")
            covered.setdefault(testfile, {}).setdefault(src, set()).update(numbits_to_nums(bits))
        covered = {t: {s: sorted(l) for s, l in d.items()} for t, d in covered.items()}
        import_lines = {s: sorted(l) for s, l in import_lines.items()}
    return {"returncode": rc, "wall": wall, "durations": durations, "outcomes": outcomes,
            "failing": sorted(failing), "covered": covered, "import_lines": import_lines, "tail": tail}

# ---------------------------------------------------------------- mutants
SWAP_CMP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE,
            ast.LtE: ast.Gt, ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In}
SWAP_BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult, ast.FloorDiv: ast.Mult,
            ast.Mod: ast.FloorDiv, ast.BitOr: ast.BitAnd, ast.BitAnd: ast.BitOr}

def mutations_of(node):
    """Yield (operator name, mutated node) for one expression node; classic mutation operators."""
    import copy
    if isinstance(node, ast.Compare) and type(node.ops[0]) in SWAP_CMP:
        m = copy.deepcopy(node); m.ops[0] = SWAP_CMP[type(node.ops[0])](); yield "ROR", m
    elif isinstance(node, ast.BinOp) and type(node.op) in SWAP_BIN:
        m = copy.deepcopy(node); m.op = SWAP_BIN[type(node.op)](); yield "AOR", m
    elif isinstance(node, ast.BoolOp):
        m = copy.deepcopy(node); m.op = ast.Or() if isinstance(node.op, ast.And) else ast.And(); yield "LCR", m
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        yield "UOD", node.operand
    elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
        yield "BCR", ast.Constant(not node.value)
    elif isinstance(node, ast.Constant) and type(node.value) is int:
        yield "CRP", ast.Constant(node.value + 1)

def candidate_mutants(text, lines):
    """All single-line mutants whose mutated expression lies on one of the given lines."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            docs.add(id(n.body[0].value))
    out, src_lines = [], text.splitlines(keepends=True)
    for n in ast.walk(tree):
        if isinstance(n, ast.Return) and n.value is not None and n.lineno == n.value.end_lineno and n.lineno in lines \
                and not (isinstance(n.value, ast.Constant) and n.value.value is None):
            out.append(("RVR", n.lineno, n.value.col_offset, n.value.end_col_offset, "None"))
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and n.lineno == n.end_lineno and n.lineno in lines:
            out.append(("SDL", n.lineno, n.value.col_offset, n.value.end_col_offset, "None"))      # drop a call statement
        if isinstance(n, (ast.Assign, ast.AugAssign)) and n.value.lineno == n.value.end_lineno and n.value.lineno in lines \
                and not isinstance(n.value, ast.Constant):
            out.append(("ASR", n.value.lineno, n.value.col_offset, n.value.end_col_offset, "None"))  # assign None
        if not isinstance(n, ast.expr) or id(n) in docs:
            continue
        if getattr(n, "lineno", None) not in lines or n.lineno != n.end_lineno:
            continue
        for op, m in mutations_of(n):
            try:
                out.append((op, n.lineno, n.col_offset, n.end_col_offset, "(" + ast.unparse(m) + ")"))
            except Exception:
                pass
    good = []
    for op, ln, c0, c1, rep in out:
        b = src_lines[ln - 1].encode("utf-8")          # ast offsets are UTF-8 byte offsets
        new_line = (b[:c0] + rep.encode() + b[c1:]).decode("utf-8", errors="replace")
        mutated = "".join(src_lines[: ln - 1]) + new_line + "".join(src_lines[ln:])
        try:
            ast.parse(mutated)
        except SyntaxError:
            continue
        good.append({"op": op, "line": ln, "col": c0, "replacement": rep, "text": mutated})
    return good

try:
    import pytest_timeout  # noqa: F401   (loaded by pytest through its entry point)
    HAVE_TIMEOUT = True
except ImportError:
    HAVE_TIMEOUT = False

def run_mutants(repo, spec, rec, snap, timeout_base, workdir, seed):
    """Seed up to MUTANTS_PER_CHANGE faults on changed source lines of the new version and record which
    test files detect each one (a test case that passed on the unmutated code fails on the mutant)."""
    url, src_root, pkgs, tests_dir, src_dirs = spec
    rnd = random.Random(seed)
    cands = []
    for f, d in rec["diff"].items():
        if d["status"] == "D" or not is_src_path(f, src_dirs, tests_dir):
            continue
        text = (repo / f).read_text(encoding="utf-8", errors="replace")
        for m in candidate_mutants(text, set(d["new"])):
            m["file"] = f
            cands.append(m)
    rnd.shuffle(cands)
    # prefer mutants on different lines
    chosen, used = [], set()
    for m in cands:
        if (m["file"], m["line"]) not in used:
            chosen.append(m); used.add((m["file"], m["line"]))
        if len(chosen) == MUTANTS_PER_CHANGE:
            break
    run_, base_fail = snap["run"], set(snap["run"]["failing"])
    results = []
    env = test_env(repo, spec, workdir)
    for m in chosen:
        f, ln = m["file"], m["line"]
        imp = ln in set(run_["import_lines"].get(f, []))
        # only test files that executed the mutated file can detect the fault (for import-time lines this
        # undercounts detectors, which makes the fault-detection check stricter, not looser)
        targets = sorted(t for t, cov in run_["covered"].items() if f in cov)
        targets = [t for t in targets if (repo / t).exists()]
        res = {k: m[k] for k in ("file", "line", "op", "replacement")}
        res.update({"import_time": imp, "tests_run": len(targets)})
        if not targets:
            res.update({"status": "not_covered", "killers": []})
            results.append(res)
            continue
        orig = (repo / f).read_text(encoding="utf-8", errors="replace")
        junit = workdir / "mut.xml"
        if junit.exists():
            junit.unlink()
        (repo / f).write_text(m["text"], encoding="utf-8")
        tmo = max(120, 3 * sum(run_["durations"].get(t, 1) for t in targets) + 60)
        try:
            # a per-test timeout turns a hanging test into a failing one, so the detecting file is known
            per_test = int(max(60, 2 * max(run_["durations"].get(t, 1) for t in targets)))
            opts = [f"--timeout={per_test}"] if HAVE_TIMEOUT else []
            r = run([sys.executable, "-m", "pytest", *targets, *PYTEST_BASE, "-p", "no:cov", *opts, f"--junitxml={junit}"],
                    cwd=repo, timeout=tmo, env=env)
            _, failing, ran = parse_junit(junit, repo)
            if not ran:                         # pytest itself failed: no evidence either way
                res.update({"status": "error", "killers": [], "tail": (r.stdout + r.stderr)[-300:]})
            else:
                # collection errors appear as failing test cases of their file, so they count too
                killers = sorted({x.split("::")[0] for x in failing - base_fail})
                res.update({"status": "killed" if killers else "survived", "killers": killers})
        except subprocess.TimeoutExpired:
            res.update({"status": "timeout", "killers": []})
        finally:
            (repo / f).write_text(orig, encoding="utf-8")
        results.append(res)
    return results

# ---------------------------------------------------------------- snapshots
def snapshot(repo, spec, sha, timeout, work, snap_dir, name):
    target = snap_dir / f"{sha}.json"
    if target.exists():
        return json.loads(target.read_text())
    url, src_root, pkgs, tests_dir, src_dirs = spec
    git(repo, "checkout", "-q", "-f", sha)
    git(repo, "clean", "-q", "-fdx", "-e", ".coverage")
    s = {"sha": sha, "date": git(repo, "show", "-s", "--format=%cI", sha).strip(),
         "subject": git(repo, "show", "-s", "--format=%s", sha).strip()}
    s["tests_present"] = sorted(p.relative_to(repo).as_posix() for p in (repo / tests_dir).rglob("test_*.py")) \
        if (repo / tests_dir).exists() else []
    s["static"] = static_snapshot(repo, src_root, pkgs, src_dirs, tests_dir)
    s["loc"] = {f: sum(1 for _ in open(repo / f, encoding="utf-8", errors="replace")) for f in s["static"]}
    print(f"[{name}] {sha[:10]} running tests ...", flush=True)
    s["run"] = run_tests(repo, spec, timeout, work)
    print(f"[{name}]     done in {s['run']['wall']:.0f}s, rc={s['run']['returncode']}, "
          f"test files with coverage={len(s['run']['covered'])}", flush=True)
    if not s["run"]["covered"]:
        print(f"[{name}]     WARNING: no per-test coverage. Last output:\n{s['run']['tail']}", flush=True)
    target.write_text(json.dumps(s))
    return s

# extra dependencies of the NameRTS projects' test suites, installed once from the newest commit
EXTRAS = {"loguru": "dev", "pvlib": "test,optional", "seaborn": "dev,stats"}

def install(repo, name):
    if name in EXTRAS:
        r = run([sys.executable, "-m", "pip", "install", "-q", "-e", f"{repo}[{EXTRAS[name]}]"])
        print(f"[{name}] dependencies: {'ok' if r.returncode == 0 else r.stderr[-400:]}", flush=True)
        # the versions of the NameRTS replication environment, so that older commits still run
        run([sys.executable, "-m", "pip", "install", "-q", "pytest>=8,<9", "pytest-cov", "coverage>=7.6",
             "pandas==2.3.3", "numpy==2.3.5"])
    r = run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "-e", str(repo)])
    return r.returncode == 0

def collect(name, n, timeout, shard, pairs_file, mutants):
    spec = PROJECTS[name]
    url, src_root, pkgs, tests_dir, src_dirs = spec
    REPOS.mkdir(exist_ok=True)
    repo = REPOS / name
    if not repo.exists():
        print(f"[{name}] cloning {url}", flush=True)
        r = run(["git", "clone", "-q", url, str(repo)])
        if r.returncode:
            sys.exit(r.stderr)
    git(repo, "checkout", "-q", "-f", git(repo, "rev-parse", "--abbrev-ref", "origin/HEAD").strip().split("/", 1)[1])
    print(f"[{name}] editable install: {'ok' if install(repo, name) else 'failed (continuing)'}", flush=True)
    base = DATA / name
    (base / "commits").mkdir(parents=True, exist_ok=True)
    (base / "snap").mkdir(exist_ok=True)
    work = base / "_work"
    work.mkdir(exist_ok=True)

    if pairs_file:
        gt = [r for r in json.loads(Path(pairs_file).read_text()) if r.get("target")]
        changes = [(r["true_parent"], r["current"], sorted(r["tests_to_run"])) for r in gt]
        mode = "pairs"
    else:
        cs = pick_commits(repo, n, src_dirs, tests_dir)
        changes = [(a, b, None) for a, b in zip(cs, cs[1:])]
        mode = "history"
    head = changes[-1][1]
    history = []
    for line in git(repo, "log", "--first-parent", "--diff-merges=first-parent", "--name-only", "--format=@@%H %cI",
                    "-n", "6000", head).splitlines():
        if line.startswith("@@"):
            sha, date = line[2:].split()
            history.append({"sha": sha, "date": date, "files": []})
        elif line.strip() and history:
            history[-1]["files"].append(line.strip())
    meta = {"project": name, "url": url, "spec": spec, "mode": mode, "changes": [[a, b] for a, b, _ in changes],
            "history": history[::-1], "python": sys.version.split()[0]}
    if shard[0] == 0:
        (base / "meta.json").write_text(json.dumps(meta))

    k, i_sh = shard[1], shard[0]
    lo, hi = len(changes) * i_sh // k, len(changes) * (i_sh + 1) // k   # contiguous block: snapshots are shared
    for i, (parent, sha, gt_tests) in enumerate(changes):
        if not lo <= i < hi:
            continue
        target = base / "commits" / f"{i:03d}_{sha[:10]}.json"
        if target.exists():
            print(f"[{name}] change {i} already collected")
            continue
        try:
            ps = snapshot(repo, spec, parent, timeout, work, base / "snap", name)
            cs_ = snapshot(repo, spec, sha, timeout, work, base / "snap", name)
            git(repo, "checkout", "-q", "-f", sha)
            git(repo, "clean", "-q", "-fdx", "-e", ".coverage")
            rec = {"index": i, "sha": sha, "parent": parent, "date": cs_["date"], "subject": cs_["subject"],
                   "diff": diff_lines(repo, parent, sha), "namerts_gt": gt_tests}
            rec["mutants"] = run_mutants(repo, spec, rec, cs_, timeout, work, seed=int(sha[:8], 16)) \
                if mutants and cs_["run"]["covered"] else []
            km = sum(m["status"] == "killed" for m in rec["mutants"])
            print(f"[{name}] change {i} {sha[:10]}: {len(rec['mutants'])} mutants, {km} killed", flush=True)
            target.write_text(json.dumps(rec))
        except Exception as e:                    # one broken commit must not stop the shard
            print(f"[{name}] change {i} {sha[:10]} FAILED: {e}", flush=True)
    shutil.rmtree(work, ignore_errors=True)
    print(f"[{name}] shard {i_sh}/{k} finished", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--commits", type=int, default=250)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--pairs", default=None, help="NameRTS ground-truth file gt_<project>.json")
    ap.add_argument("--no-mutants", action="store_true")
    a = ap.parse_args()
    i, k = map(int, a.shard.split("/"))
    if a.project not in PROJECTS:
        sys.exit(f"unknown project {a.project}")
    collect(a.project, a.commits, a.timeout, (i, k), a.pairs, not a.no_mutants)

if __name__ == "__main__":
    main()
