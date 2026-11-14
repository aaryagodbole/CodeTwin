"""Study v3, part S: are tests written together with a change independent evidence for it?

For every test change of the history projects that adds or modifies test files together with source code,
we run those test files twice:
  * on the new version (the change itself), and
  * on the parent version with only the co-changed test files replaced by their new content.
A co-changed test file is *fail-on-base* if it fails (or cannot be imported) on the parent: it encodes
behaviour that the change introduced. It is *pass-on-base* if it passes on the parent as well: it would
have passed without the change, so its passing says little about the change (a "self-confirming" test).
Files that do not pass on the new version are excluded (broken or flaky there).

The seeded faults of the study (rec["mutants"], with the test files that detected each one) are then
split by whether a fail-on-base or only pass-on-base co-changed tests detected them.

No look-ahead question arises: this measures the evidence value of tests, it does not make a selection.

Usage: CT_PILOT=<pilot dir> CT_REPOS=<bare clones> CT_PY=<python with pytest> python selfconfirm.py
Writes v3/results/selfconfirm.json.
"""
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

PILOT = Path(os.environ["CT_PILOT"])
REPOS = Path(os.environ["CT_REPOS"])
PY = os.environ.get("CT_PY", sys.executable)
sys.path.insert(0, str(PILOT))
import analyze as A  # noqa: E402

SPEC = {  # PYTHONPATH dir, tests dir (from collect.py)
    "click": ("src", "tests"), "marshmallow": ("src", "tests"), "toolz": (".", "toolz/tests"),
    "itsdangerous": ("src", "tests"), "dateutil": ("src", "tests"),
}
HIST = ["click", "dateutil", "itsdangerous", "marshmallow", "toolz"]
TIMEOUT = 90


def extract(repo, sha, dest):
    dest.mkdir(parents=True, exist_ok=True)
    a = subprocess.run(["git", f"--git-dir={repo}", "archive", sha], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=a.stdout, check=True)


def show(repo, sha, path):
    r = subprocess.run(["git", f"--git-dir={repo}", "show", f"{sha}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def run_files(root, src_root, files):
    """Return {test_file: True (all passed) / False (any failure or error)}."""
    junit = root / "_junit.xml"
    env = dict(os.environ, PYTHONPATH=str(root / src_root), PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg")
    cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-o", "junit_family=xunit1",
           f"--junitxml={junit}", *files]
    try:
        r = subprocess.run(cmd, cwd=root, env=env, capture_output=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {f: False for f in files}, "timeout"
    res = {f: None for f in files}
    if junit.exists():
        for tc in ET.parse(junit).getroot().iter("testcase"):
            f = tc.get("file") or ""
            if not f:
                cn = tc.get("classname", "")
                f = cn.split(".")[0].replace(".", "/")
            hit = next((x for x in files if f and (x == f or x.endswith(f) or f.endswith(x))), None)
            if hit is None:
                cn = tc.get("classname", "").replace(".", "/")
                hit = next((x for x in files if cn.startswith(x[:-3])), None)
            if hit is None:
                continue
            bad = any(ch.tag in ("failure", "error") for ch in tc)
            res[hit] = (res[hit] is not False) and not bad
    # a file with no collected test case: collection error => failure
    for f in files:
        if res[f] is None:
            res[f] = False if r.returncode != 0 else True
    return res, r.returncode


CACHE = Path(os.environ.get("CT_CACHE", "/tmp/sc_cache"))


def present_files(repo, sha, co):
    r = subprocess.run(["git", f"--git-dir={repo}", "ls-tree", "-r", "--name-only", sha], capture_output=True, text=True)
    names = set(r.stdout.split())
    return [f for f in co if f in names]


def finish_row(rec, sha, present, kinds):
    muts = []
    fob = {f for f, v in kinds.items() if v == "fail-on-base"}
    pob = {f for f, v in kinds.items() if v == "pass-on-base"}
    for m in rec.get("mutants", []):
        if m.get("status") != "killed":
            continue
        k = set(m.get("killers", []))
        muts.append({"killers": sorted(k), "by_fob": bool(k & fob), "by_pob": bool(k & pob),
                     "by_other": bool(k - set(present))})
    return {"sha": sha[:10], "co_changed": present, "excluded_not_passing_on_new": sorted(set(present) - set(kinds)),
            "kinds": kinds, "mutants": muts}


def process(task):
    p, sha, parent, co = task
    src_root, _ = SPEC[p]
    repo = REPOS / p
    with tempfile.TemporaryDirectory() as tmp:
        new_root, base_root = Path(tmp) / "new", Path(tmp) / "base"
        extract(repo, sha, new_root)
        extract(repo, parent, base_root)
        present = [f for f in co if (new_root / f).exists()]
        if not present:
            return p, sha, present, {}
        for f in present:
            (base_root / f).parent.mkdir(parents=True, exist_ok=True)
            (base_root / f).write_bytes(show(repo, sha, f))
        on_new, _ = run_files(new_root, src_root, present)
        on_base, _ = run_files(base_root, src_root, present)
    kinds = {f: ("pass-on-base" if on_base[f] else "fail-on-base") for f in present if on_new[f]}
    return p, sha, present, kinds


def main():
    import ast
    from concurrent.futures import ProcessPoolExecutor, as_completed
    CACHE.mkdir(parents=True, exist_ok=True)
    seed = Path(os.environ.get("CT_SEED_LOG", "/nonexistent"))
    seeded = {}
    if seed.exists():
        for line in seed.read_text().splitlines():
            parts = line.split(" ", 2)
            if len(parts) == 3 and parts[0] in HIST and parts[2].startswith("{"):
                seeded[(parts[0], parts[1])] = ast.literal_eval(parts[2])
    out = {"changes": {}, "summary": {}}
    tasks, recs_of = [], {}
    for p in HIST:
        meta, cs, _, _ = A.load_changes(p)
        _, recs = A.load_project(p)
        bysha = {r["sha"]: r for r in recs}
        _, test = A.split(cs)
        for c in test:
            co = sorted(A.forced(c))
            if not co:
                continue
            rec = bysha[c["sha"]]
            recs_of[(p, c["sha"])] = rec
            cf = CACHE / f"{p}_{c['sha'][:10]}.json"
            if not cf.exists() and (p, c["sha"][:10]) in seeded:
                present = present_files(REPOS / p, c["sha"], co)
                cf.write_text(json.dumps({"present": present, "kinds": seeded[(p, c["sha"][:10])], "seeded": True}))
            if not cf.exists():
                tasks.append((p, c["sha"], rec["parent"], co))
    print(f"{len(recs_of)} changes with co-changed tests, {len(tasks)} still to run", flush=True)
    with ProcessPoolExecutor(max_workers=int(os.environ.get("CT_WORKERS", "2"))) as ex:
        futs = [ex.submit(process, t) for t in tasks]
        for n, f in enumerate(as_completed(futs), 1):
            p, sha, present, kinds = f.result()
            (CACHE / f"{p}_{sha[:10]}.json").write_text(json.dumps({"present": present, "kinds": kinds}))
            print(f"[{n}/{len(tasks)}]", p, sha[:10], kinds, flush=True)
    for (p, sha), rec in recs_of.items():
        d = json.loads((CACHE / f"{p}_{sha[:10]}.json").read_text())
        if d["present"]:
            out["changes"].setdefault(p, []).append(finish_row(rec, sha, d["present"], d["kinds"]))

    # summary
    files = defaultdict(int); ch = defaultdict(int); mut = defaultdict(int)
    for p, rows in out["changes"].items():
        for r in rows:
            ch["with_co_changed_tests"] += 1
            if not r["kinds"]:
                ch["no_valid_co_changed"] += 1; continue
            ch["evaluated"] += 1
            v = list(r["kinds"].values())
            for x in v:
                files[x] += 1
            files["excluded_not_passing_on_new"] += len(r["excluded_not_passing_on_new"])
            if all(x == "pass-on-base" for x in v):
                ch["only_pass_on_base"] += 1
            elif all(x == "fail-on-base" for x in v):
                ch["only_fail_on_base"] += 1
            else:
                ch["mixed"] += 1
            for m in r["mutants"]:
                mut["detected"] += 1
                if m["by_fob"]:
                    mut["by_fail_on_base"] += 1
                if m["by_pob"]:
                    mut["by_pass_on_base"] += 1
                if m["by_pob"] and not m["by_fob"] and not m["by_other"]:
                    mut["only_by_pass_on_base"] += 1
                if (m["by_fob"] or m["by_pob"]) and not m["by_other"]:
                    mut["only_by_co_changed"] += 1
    out["summary"] = {"changes": dict(ch), "test_files": dict(files), "mutants": dict(mut),
                      "python": subprocess.run([PY, "--version"], capture_output=True, text=True).stdout.strip()}
    dest = Path(__file__).resolve().parent / "results" / "selfconfirm.json"
    dest.write_text(json.dumps(out, indent=1))
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
