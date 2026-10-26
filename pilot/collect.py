#!/usr/bin/env python3
"""
CodeTwin AI -- pilot data collector.

Runs ON YOUR LAPTOP. For each recent commit of an open-source Python
project it records the evidence CodeTwin needs:
  * per-test-file coverage of source lines (coverage.py dynamic contexts)
  * per-test-file run time and outcome (pytest junit xml)
  * the git diff (changed source / test files and line numbers)
  * a static import graph (Python ast) and dynamic-call markers
  * commit history (for co-change)
Everything is written as JSON under data/<project>/ . Nothing is uploaded.

Usage (from the folder that contains this file):
    python collect.py --project click
    python collect.py --project all          # every project in PROJECTS (except the test-only 'toy')
Options: --commits N (default 40), --timeout S (default 900 per run)
"""
import argparse, ast, json, os, re, shutil, sqlite3, subprocess, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOS = HERE / "repos"
DATA = HERE / "data"

# name: (git url, PYTHONPATH dir, [packages for --cov], tests dir, package source dirs)
PROJECTS = {
    "toy":          (str(Path(os.environ.get("TOY_REPO", "/nonexistent"))), "src", ["toypkg"], "tests", ["src/toypkg"]),
    "click":        ("https://github.com/pallets/click",              "src", ["click"],          "tests",       ["src/click"]),
    "marshmallow":  ("https://github.com/marshmallow-code/marshmallow", "src", ["marshmallow"], "tests",       ["src/marshmallow"]),
    "toolz":        ("https://github.com/pytoolz/toolz",               ".",   ["toolz"],          "toolz/tests", ["toolz"]),
    "itsdangerous": ("https://github.com/pallets/itsdangerous",        "src", ["itsdangerous"],   "tests",       ["src/itsdangerous"]),
    "dateutil":     ("https://github.com/dateutil/dateutil",           "src", ["dateutil"],       "tests",       ["src/dateutil"]),
}

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
def pick_commits(repo, n, src_dirs, tests_dir):
    """Last n commits on the first-parent (mainline) history that change at least one source
    .py file, oldest first, plus the commit just before the first one (baseline).
    Merge commits are included: on GitHub-style projects most changes land as PR merges, and
    their diff against the first parent is exactly the change that entered the main branch."""
    log = git(repo, "log", "--first-parent", "--format=%H %P", "-n", "3000", "HEAD").splitlines()
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
    return chosen  # chosen[0] is the baseline, chosen[1:] are evaluated

# ---------------------------------------------------------------- diff
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
def diff_lines(repo, a, b):
    """{path: {'old': [...], 'new': [...], 'status': 'M'|'A'|'D'|'R'}} for .py files between a and b."""
    out = {}
    status = git(repo, "diff", "--name-status", "-M", a, b)
    for line in status.splitlines():
        parts = line.split("\t")
        st = parts[0][0]
        path = parts[-1]
        if path.endswith(".py"):
            out[path] = {"old": [], "new": [], "status": st, "old_path": parts[1] if st == "R" else path}
    raw = git(repo, "diff", "-U0", "-M", a, b, "--", "*.py")
    cur = None
    for line in raw.splitlines():
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
    """imports (absolute module names within pkgs) and dynamic markers for one .py file."""
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return {"imports": [], "dynamic": ["unparsed"]}
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    mod_parts = rel[:-3].split("/")
    imports, dyn = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                base = mod_parts[:-1] if not rel.endswith("__init__.py") else mod_parts[:-1]
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                prefix = ".".join(base)
                modname = prefix + ("." + node.module if node.module else "")
            else:
                modname = node.module or ""
            imports.add(modname)
            for a in node.names:
                imports.add(modname + "." + a.name)
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if name in DYN_CALLS:
                dyn.add(name)
            if name in ("getattr", "setattr", "hasattr") and len(node.args) >= 2 and not isinstance(node.args[1], ast.Constant):
                dyn.add("getattr-dynamic")
    keep = sorted(i for i in imports if i and any(i == p or i.startswith(p + ".") for p in pkgs))
    return {"imports": keep, "dynamic": sorted(dyn)}

def static_snapshot(repo, src_root, pkgs, src_dirs, tests_dir):
    files = {}
    for d in list(src_dirs) + [tests_dir]:
        base = repo / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            rel = p.relative_to(repo).as_posix()
            root = repo / src_root if src_root != "." else repo
            files[rel] = analyse_file(p, root if not is_test_path(rel, tests_dir) else root, pkgs)
    return files

# ---------------------------------------------------------------- test run
def run_tests(repo, spec, timeout, workdir):
    url, src_root, pkgs, tests_dir, src_dirs = spec
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / src_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["COVERAGE_CORE"] = "ctrace"          # per-test contexts need the ctrace core
    env["COVERAGE_FILE"] = str(workdir / ".coverage")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    junit = workdir / "junit.xml"
    covrc = workdir / "coveragerc"
    covrc.write_text("[run]\nbranch = False\nparallel = False\n")   # ignore the project's own coverage config
    for f in (workdir / ".coverage", junit):
        if f.exists():
            f.unlink()
    # -o filterwarnings=default: some projects turn every warning into an error; a deprecation
    # warning from a newer tool version must not abort test collection.
    cmd = [sys.executable, "-m", "pytest", tests_dir, "-q", "-p", "no:cacheprovider", "--no-header",
           "-o", "junit_family=xunit1", "-o", "filterwarnings=default",
           f"--cov-config={covrc}", "--cov-context=test", "--cov-report=", f"--junitxml={junit}"] + [f"--cov={p}" for p in pkgs]
    t0 = time.time()
    try:
        r = run(cmd, cwd=repo, timeout=timeout, env=env)
        rc, tail = r.returncode, (r.stdout + r.stderr)[-800:]
    except subprocess.TimeoutExpired:
        rc, tail = "timeout", ""
    wall = time.time() - t0

    # per-test-file durations and outcomes from junit xml
    durations, outcomes = {}, {}
    if junit.exists():
        try:
            for tc in ET.parse(junit).getroot().iter("testcase"):
                f = tc.get("file")
                if not f:
                    cls = tc.get("classname", "")
                    f = cls.replace(".", "/")
                    parts = f.split("/")
                    for k in range(len(parts), 0, -1):
                        cand = "/".join(parts[:k]) + ".py"
                        if (repo / cand).exists():
                            f = cand
                            break
                f = f.replace(os.sep, "/")
                durations[f] = durations.get(f, 0.0) + float(tc.get("time", 0) or 0)
                bad = any(ch.tag in ("failure", "error") for ch in tc)
                outcomes[f] = outcomes.get(f, True) and not bad
        except ET.ParseError:
            pass

    # per-test-file covered lines from coverage contexts
    covered = {}
    covfile = workdir / ".coverage"
    if covfile.exists():
        con = sqlite3.connect(covfile)
        ctx = dict(con.execute("select id, context from context"))
        files = dict(con.execute("select id, path from file"))
        rows = con.execute("select file_id, context_id, numbits from line_bits").fetchall()
        from coverage.numbits import numbits_to_nums, nums_to_numbits
        if not rows:   # branch coverage stores arcs instead of lines
            arcs = {}
            for fid, cid, a, b in con.execute("select file_id, context_id, fromno, tono from arc"):
                arcs.setdefault((fid, cid), set()).update(x for x in (a, b) if x > 0)
            rows = [(fid, cid, nums_to_numbits(sorted(v))) for (fid, cid), v in arcs.items()]
        con.close()
        import_lines = {}
        for fid, cid, bits in rows:
            c = ctx.get(cid, "")
            src = os.path.relpath(files[fid], repo).replace(os.sep, "/")
            if not c or "::" not in c:
                # lines run outside any test (module import time)
                import_lines.setdefault(src, set()).update(numbits_to_nums(bits))
                continue
            testfile = c.split("::")[0].replace(os.sep, "/")
            covered.setdefault(testfile, {}).setdefault(src, set()).update(numbits_to_nums(bits))
        covered = {t: {s: sorted(l) for s, l in d.items()} for t, d in covered.items()}
        import_lines = {s: sorted(l) for s, l in import_lines.items()}
    else:
        import_lines = {}
    return {"returncode": rc, "wall": wall, "durations": durations, "outcomes": outcomes,
            "covered": covered, "import_lines": import_lines, "tail": tail}

# ---------------------------------------------------------------- main
def collect(name, n, timeout):
    spec = PROJECTS[name]
    url, src_root, pkgs, tests_dir, src_dirs = spec
    REPOS.mkdir(exist_ok=True)
    repo = REPOS / name
    if not repo.exists():
        print(f"[{name}] cloning {url}")
        r = run(["git", "clone", "-q", url, str(repo)])
        if r.returncode:
            sys.exit(r.stderr)
    git(repo, "checkout", "-q", "-f", git(repo, "rev-parse", "--abbrev-ref", "origin/HEAD").strip().split("/", 1)[1])
    out = DATA / name / "commits"
    out.mkdir(parents=True, exist_ok=True)
    work = DATA / name / "_work"
    work.mkdir(exist_ok=True)

    commits = pick_commits(repo, n, src_dirs, tests_dir)
    history = []
    for line in git(repo, "log", "--first-parent", "--diff-merges=first-parent", "--name-only", "--format=@@%H", "-n", "3000", commits[-1]).splitlines():
        if line.startswith("@@"):
            history.append({"sha": line[2:], "files": []})
        elif line.strip() and history:
            history[-1]["files"].append(line.strip())
    meta = {"project": name, "url": url, "spec": spec, "commits": commits, "history": history[::-1],
            "python": sys.version.split()[0]}
    (DATA / name / "meta.json").write_text(json.dumps(meta))

    prev = None
    for i, sha in enumerate(commits):
        target = out / f"{i:03d}_{sha[:10]}.json"
        if target.exists():
            prev = sha
            print(f"[{name}] {i}/{len(commits)-1} {sha[:10]} already collected")
            continue
        git(repo, "checkout", "-q", "-f", sha)
        git(repo, "clean", "-q", "-fdx", "-e", ".coverage")
        rec = {"index": i, "sha": sha, "parent_eval": prev,
               "date": git(repo, "show", "-s", "--format=%cI", sha).strip(),
               "subject": git(repo, "show", "-s", "--format=%s", sha).strip()}
        rec["diff"] = diff_lines(repo, prev, sha) if prev else {}
        rec["tests_present"] = sorted(p.relative_to(repo).as_posix() for p in (repo / tests_dir).rglob("test_*.py")) if (repo / tests_dir).exists() else []
        rec["static"] = static_snapshot(repo, src_root, pkgs, src_dirs, tests_dir)
        rec["loc"] = {f: sum(1 for _ in open(repo / f, encoding="utf-8", errors="replace")) for f in rec["static"]}
        print(f"[{name}] {i}/{len(commits)-1} {sha[:10]} running tests ...", flush=True)
        rec["run"] = run_tests(repo, spec, timeout, work)
        print(f"[{name}]     done in {rec['run']['wall']:.0f}s, rc={rec['run']['returncode']}, "
              f"test files with coverage={len(rec['run']['covered'])}", flush=True)
        if not rec["run"]["covered"]:
            print(f"[{name}]     WARNING: no per-test coverage recorded. Last output:\n{rec['run']['tail']}", flush=True)
        target.write_text(json.dumps(rec))
        prev = sha
    shutil.rmtree(work, ignore_errors=True)
    git(repo, "checkout", "-q", "-f", "-")
    print(f"[{name}] finished: {DATA / name}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="project name or 'all'")
    ap.add_argument("--commits", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    names = [p for p in PROJECTS if p != "toy"] if a.project == "all" else [a.project]
    failed = []
    for nme in names:
        if nme not in PROJECTS:
            sys.exit(f"unknown project {nme}; choose from {[p for p in PROJECTS if p != 'toy']}")
        try:
            collect(nme, a.commits, a.timeout)
        except (Exception, SystemExit) as e:      # one broken project must not stop the others
            print(f"[{nme}] FAILED: {e}", flush=True)
            failed.append(nme)
    print("\nAll done." if not failed else f"\nDone, but these projects failed: {failed}. "
          "Run the same command again (finished commits are skipped) or send the error message.")

if __name__ == "__main__":
    main()
