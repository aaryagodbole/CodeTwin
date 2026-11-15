"""Independent check of Table tab:v4 from the raw data, without analyze.py: changes, test changes and the
miss rate of line- and file-coverage selection per language. Ground truth as in the paper: tests whose coverage
of the new version includes a changed line, plus test files the change adds or modifies and test files with no
result on the base commit (both always run). Usage: python recount_check.py"""
import glob
import json
import re
from pathlib import Path

D = Path("/home/claude/codetwin/pilot/v4/data")
TESTY = re.compile(r"(^|/)(test|tests|spec|specs|__tests__|testdata|e2e)(/|$)|(^|/)test_[^/]*$|(\.test\.|\.spec\.|_test\.|_spec\.|Test\.|Tests\.|TestCase\.)")
groups = {}
for p in sorted(D.iterdir()):
    if p.name.startswith("lang_") or not (p / "lang.json").exists():
        continue
    lang = json.loads((p / "lang.json").read_text())["language"]
    groups.setdefault(lang, []).append(p)

def snap(p, sha):
    f = p / "snap" / f"{sha}.json"
    return json.loads(f.read_text()) if f.exists() else None

for lang, projs in groups.items():
    recs = []
    for p in projs:
        ext = tuple(json.loads((p / "lang.json").read_text())["extensions"])
        for f in sorted((p / "commits").glob("*.json")):
            r = json.loads(f.read_text())
            if r.get("log", {}).get("tests_used", 1) == 0:
                continue
            b, n = snap(p, r["parent"]), snap(p, r["sha"])
            if not b or not n:
                continue
            recs.append((b.get("date") or r["date"], r["index"], p, r, b, n, ext))
    recs.sort(key=lambda x: (x[0], x[1]))
    k = int(0.4 * len(recs))         # analyze.py split: first 40% calibrate
    test = recs[k:]
    lmiss = fmiss = unsafe_tests = 0
    for _, _, p, r, b, n, ext in test:
        tests_now = set(n["tests_present"])
        bt = set(b["tests_present"])
        universe = sorted(set(b["run"]["durations"]) | (set(n["run"]["durations"]) & tests_now))
        tests_all = bt | tests_now
        src = {f: d for f, d in r["diff"].items() if f.endswith(ext) and f not in tests_all and not TESTY.search(f)}
        changed_tests = {f for f in r["diff"] if f in tests_all}
        affected = set(t for t in universe if t in changed_tests or t not in b["run"]["durations"])
        for f, d in src.items():
            new = set(d.get("new", []))
            for t in universe:
                if new & set(n["run"]["covered"].get(t, {}).get(f, [])):
                    affected.add(t)
        forced = {t for t in universe if t in changed_tests or t not in b["run"]["durations"]}
        line = set(forced); filec = set(forced)
        for f, d in src.items():
            old = set(d.get("old", []))
            for t in universe:
                cov = b["run"]["covered"].get(t, {}).get(d.get("old_path", f), [])
                if cov:
                    filec.add(t)
                if old & set(cov):
                    line.add(t)
        lmiss += not (affected <= line)
        fmiss += not (affected <= filec)
    print(f"{lang:10s} changes {len(recs):3d}  test changes {len(test):3d}  line-cov unsafe {lmiss:2d} ({100*lmiss/max(1,len(test)):.1f}%)  file-cov unsafe {fmiss}")
