"""Study v4 analysis: the v2/v3 analysis (pilot/analyze.py) on the Multi-SWE-bench data of pilot/v4/data.

Differences from the Python study, all handled here without changing analyze.py:
  * source vs test files come from each project's language (lang.json + the recorded test lists);
  * the static graph uses file-level dependencies (`deps`) resolved by the language adapters;
  * co-change history is stored per change (each PR has its own base commit);
  * the real pull request's fail-to-pass test files are the third ground truth (stored in the field
    analyze.py uses for NameRTS's ground truth, so its `n_safe` / `n_recall` metrics report them);
  * every project is treated as a history project: leave-one-project-out training across languages and
    chronological calibration per project.

Usage: python analyze_v4.py [project ...]      (writes pilot/v4/results/)
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent
DATA = HERE / "data"

# ---- load analyze.py as a module with two one-line source patches (file stems, pairs-mode table key)
src = (PILOT / "analyze.py").read_text(encoding="utf-8")
src = src.replace('stems = {f.rsplit("/", 1)[-1][:-3] for f, _ in all_changed} - {"__init__"}',
                  'stems = {f.rsplit("/", 1)[-1].split(".")[0] for f, _ in all_changed} - {"__init__", "index", "mod", "lib", "main"}')
assert 'split(".")[0]' in src
an = types.ModuleType("analyze")
an.__file__ = str(PILOT / "analyze.py")
exec(compile(src, str(PILOT / "analyze.py"), "exec"), an.__dict__)
an.DATA = DATA
an.OUT = HERE / "results"
an.NAMERTS_KEYS = {}

LANG: dict[str, dict] = {}          # project -> {"extensions": [...], "tests": set(...)}
HIST: dict[str, list] = {}          # change sha -> co-change history (commits before its base)
TESTY = re.compile(r"(^|/)(test|tests|spec|specs|__tests__|testdata|e2e)(/|$)|(^|/)test_[^/]*$|(\.test\.|\.spec\.|_test\.|_spec\.|Test\.|Tests\.|TestCase\.)")


def _lang_of(name: str) -> dict:
    if name not in LANG:
        info = json.loads((DATA / name / "lang.json").read_text()) if (DATA / name / "lang.json").exists() else {}
        tests: set[str] = set()
        for p in (DATA / name / "snap").glob("*.json"):
            tests.update(json.loads(p.read_text()).get("tests_present", []))
        LANG[name] = {"extensions": tuple(info.get("extensions", [])), "tests": tests, "language": info.get("language")}
    return LANG[name]


URL2NAME: dict[str, str] = {}
SMALL: set[str] = set()             # projects reported separately (fewer than MIN_CHANGES changes)
MIN_CHANGES = 20


def is_src(path: str, spec) -> bool:
    L = _lang_of(URL2NAME[spec[0]])
    if not path.endswith(L["extensions"]) or path in L["tests"]:
        return False
    return not TESTY.search(path)


def module_of(path: str, src_root: str) -> str:
    return path


def import_graph(static, known_modules):
    return {f: {d for d in info.get("deps", []) if d in known_modules} for f, info in static.items()}


_orig_load_project = an.load_project


def _base_date(name: str, sha: str) -> str | None:
    p = DATA / name / "snap" / f"{sha}.json"
    if not p.exists():
        return None
    head = p.read_text(encoding="utf-8")[:400]           # "date" is near the start of the snapshot
    m = re.search(r'"date": "([^"]+)"', head)
    return m.group(1) if m else None


def load_project(name: str):
    meta, recs = _orig_load_project(name)
    for r in recs:                                        # order PRs by their base commit's date
        r["date"] = _base_date(name, r["parent"]) or r["date"]
    recs.sort(key=lambda r: (r["date"], r["index"]))
    # Languages with too few changes for per-project calibration are evaluated like the NameRTS projects of the
    # Python study: model trained on all other projects, reported separately and not pooled (group "NRTS").
    meta["mode"] = "pairs" if name in SMALL else "history"
    meta["spec"] = list(meta["spec"][:5])
    URL2NAME[meta["spec"][0]] = name
    meta["language"] = _lang_of(name)["language"] or meta.get("language")
    meta["history"] = []
    kept = []
    for r in recs:
        HIST[r["sha"]] = r.get("history", [])
        r["namerts_gt"] = r.get("f2p") or []
        if r.get("log", {}).get("tests_used", 1) == 0:
            continue
        kept.append(r)
    return meta, kept


def hist_lookup(meta):
    return lambda sha: HIST.get(sha, [])


an.is_src, an.module_of, an.import_graph, an.load_project, an.hist_lookup = is_src, module_of, import_graph, load_project, hist_lookup


def _np(o):
    import numpy as np
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o).__name__)


an.json = types.SimpleNamespace(dumps=lambda o, **k: json.dumps(o, **{"default": _np, **k}),
                                dump=lambda o, f, **k: json.dump(o, f, **{"default": _np, **k}), loads=json.loads, load=json.load)

def merge_by_language() -> list[str]:
    """Virtual projects `lang_<language>` that pool the repositories of one language (symlinks), so that
    calibration has enough changes: per repository there are only 5-9 calibration changes."""
    groups: dict[str, list[str]] = {}
    for p in sorted(DATA.iterdir()):
        if p.name.startswith("lang_") or not (p / "lang.json").exists() or not any((p / "commits").glob("*.json")):
            continue
        lang = json.loads((p / "lang.json").read_text())["language"]
        groups.setdefault(lang, []).append(p.name)
    out = []
    for lang, names in groups.items():
        d = DATA / f"lang_{lang}"
        if d.exists():
            import shutil
            shutil.rmtree(d)
        (d / "commits").mkdir(parents=True)
        (d / "snap").mkdir()
        for n in names:
            for f in (DATA / n / "commits").glob("*.json"):
                (d / "commits" / f"{n}__{f.name}").symlink_to(f.resolve())
            for f in (DATA / n / "snap").glob("*.json"):
                (d / "snap" / f.name).symlink_to(f.resolve())
        meta = json.loads((DATA / names[0] / "meta.json").read_text())
        meta.update(project=f"lang_{lang}", url=f"lang:{lang}", repos=names)
        meta["spec"] = [f"lang:{lang}", ".", [], ".", ["."], {"language": lang}]
        (d / "meta.json").write_text(json.dumps(meta))
        (d / "lang.json").write_text((DATA / names[0] / "lang.json").read_text())
        out.append(d.name)
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--per-language"]:
        projects = merge_by_language()
        an.OUT = HERE / "results_by_language"
        SMALL.update(p for p in projects if len(list((DATA / p / "commits").glob("*.json"))) < MIN_CHANGES)
        print("reported separately (fewer than", MIN_CHANGES, "changes):", sorted(SMALL))
    else:
        projects = sys.argv[1:] or sorted(p.name for p in DATA.iterdir() if not p.name.startswith("lang_")
                                          and (p / "meta.json").exists() and any((p / "commits").glob("*.json")))
    print("projects:", projects)
    an.main(projects)
