#!/usr/bin/env python3
"""
CodeTwin AI -- analysis (study v2).

Reads data/<project>/ produced by collect.py and evaluates
  baselines : Retest-all, Name matching, Static import, File coverage, Function coverage,
              Line coverage, Hybrid, and (on the NameRTS commits) the published NameRTS selections
  CodeTwin  : learned risk ranking under a time budget; conformal-calibrated selection;
              abstention with file-level or line-level uncertainty triggers, falling back to the
              full suite or to a broader (hybrid) selection
  ablation  : risk model retrained with one evidence signal removed at a time
Ground truths: (1) coverage of the new version (affected tests), (2) seeded faults on changed
lines (mutants) and the tests that detect them, (3) on NameRTS commits, the NameRTS ground truth.
Writes results/results.json, results/stats.md, results/tables_*.tex and results/*.pdf/.png
Usage: python analyze.py [project ...]
"""
import json, math, random, sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "results"
NAMERTS = HERE / "namerts"
BUDGETS = [0.10, 0.25, 0.50]
ALPHAS = [0.01, 0.05, 0.10, 0.20]
CALIB_FRAC = 0.4
MAIN_ALPHA = 0.10
ABL_BUDGET = 0.25
FEATURES = ["cov_line", "cov_func", "cov_file", "static_inv_dist", "name_match", "cochange", "test_changed"]
B_RESAMPLES = 10_000
NAMERTS_KEYS = {"loguru": "LOG", "pvlib": "PVL", "seaborn": "SE"}

# ------------------------------------------------------------------ loading
class Snaps:
    """Lazy, cached access to data/<project>/snap/<sha>.json (snapshots are large)."""
    def __init__(self, name, keep=6):
        self.dir, self.cache, self.order, self.keep = DATA / name / "snap", {}, [], keep
    def get(self, sha):
        if sha not in self.cache:
            p = self.dir / f"{sha}.json"
            if not p.exists():
                return None
            self.cache[sha] = json.loads(p.read_text())
            self.order.append(sha)
            if len(self.order) > self.keep:
                self.cache.pop(self.order.pop(0), None)
        return self.cache[sha]

def load_project(name):
    meta = json.loads((DATA / name / "meta.json").read_text())
    recs = [json.loads(p.read_text()) for p in sorted((DATA / name / "commits").glob("*.json"))]
    recs.sort(key=lambda r: (r["date"], r["index"]))          # chronological order
    return meta, recs

def module_of(path, src_root):
    p = path[len(src_root) + 1:] if src_root not in (".", "") and path.startswith(src_root + "/") else path
    p = p[:-3]
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    return p.replace("/", ".")

def is_src(path, spec):
    _, _, _, tests_dir, src_dirs = spec
    name = path.rsplit("/", 1)[-1]
    is_test = path.startswith(tests_dir.rstrip("/") + "/") or name.startswith("test_")
    return path.endswith(".py") and not is_test and any(path.startswith(d.rstrip("/") + "/") for d in src_dirs)

# ------------------------------------------------------------------ static graph
def import_graph(static, known_modules):
    g = {}
    for f, info in static.items():
        targets = set()
        for imp in info["imports"]:
            parts = imp.split(".")
            for k in range(len(parts), 0, -1):
                cand = ".".join(parts[:k])
                if cand in known_modules:
                    targets.add(cand)
                    break
        g[f] = targets
    return g

def static_distance(test, changed_mods, graph, mod_to_file, max_depth=6):
    frontier, seen = set(graph.get(test, ())), set()
    for d in range(1, max_depth + 1):
        if frontier & changed_mods:
            return d
        seen |= frontier
        nxt = set()
        for m in frontier:
            f = mod_to_file.get(m)
            if f:
                nxt |= graph.get(f, set())
        frontier = nxt - seen
        if not frontier:
            break
    return None

def innermost(defs, line):
    """Innermost function [start, end, body_start] containing a line, or None."""
    best = None
    for d in defs:
        if d[0] <= line <= d[1] and (best is None or d[0] >= best[0]):
            best = d
    return best

# ------------------------------------------------------------------ per-change records
def build_change(meta, rec, prev, cur, hist):
    spec = meta["spec"]
    url, src_root, pkgs, tests_dir, src_dirs = spec
    run, prun = cur["run"], prev["run"]
    durations = run["durations"]
    present = set(cur["tests_present"])
    universe = sorted(t for t in durations if t in present or t.startswith(tests_dir))
    if not universe:
        return None
    changed_src = {f: d for f, d in rec["diff"].items() if is_src(f, spec) and d["status"] != "D"}
    deleted_src = {f: d for f, d in rec["diff"].items() if is_src(f, spec) and d["status"] == "D"}
    changed_tests = {f for f, d in rec["diff"].items() if not is_src(f, spec) and d["status"] in ("A", "M", "R") and f in durations}
    if not changed_src and not deleted_src:
        return None
    all_changed = list(changed_src.items()) + list(deleted_src.items())

    # ---------- ground truth 1: coverage of the NEW version
    cov = run["covered"]
    imp_lines = {f: set(v) for f, v in run.get("import_lines", {}).items()}
    affected = set(changed_tests)
    for f, d in changed_src.items():
        new = set(d["new"])
        for t in universe:
            if new & set(cov.get(t, {}).get(f, [])):
                affected.add(t)
        if new & imp_lines.get(f, set()):
            for t in universe:
                if f in cov.get(t, {}):
                    affected.add(t)
    for f, d in deleted_src.items():
        for t in universe:
            if f in prun["covered"].get(t, {}):
                affected.add(t)

    # ---------- ground truth 2: seeded faults (killed mutants; killers restricted to the universe)
    U = set(universe)
    mutants = [{"file": m["file"], "line": m["line"], "op": m["op"], "killers": sorted(set(m["killers"]) & U)}
               for m in rec.get("mutants", []) if m["status"] == "killed" and set(m["killers"]) & U]

    # ---------- evidence available BEFORE running the tests of this change
    pcov = prun["covered"]
    pimp = {f: set(v) for f, v in prun.get("import_lines", {}).items()}
    pstatic, cstatic = prev["static"], cur["static"]
    known = {module_of(f, src_root): f for f in cstatic if is_src(f, spec)}
    graph = import_graph(cstatic, set(known))
    changed_mods = {module_of(f, src_root) for f, _ in all_changed}
    stems = {f.rsplit("/", 1)[-1][:-3] for f, _ in all_changed} - {"__init__"}

    past = hist(rec["sha"])
    co = defaultdict(int); base = 0
    for h in past[-300:]:
        fs = set(h["files"])
        if fs & {f for f, _ in all_changed}:
            base += 1
            for t in fs:
                co[t] += 1

    # function bodies (old version) that enclose a changed line or insertion point
    func_lines = {}            # old path -> set of lines of enclosing functions' bodies
    outside = {}               # old path -> changed old lines that are not inside a function
    for f, d in all_changed:
        oldp = d.get("old_path", f)
        defs = pstatic.get(oldp, {}).get("defs", [])
        fl, out_ = set(), set()
        for l in d["old"]:
            D = innermost(defs, l)
            if D:
                fl.update(range(D[2], D[1] + 1))
            else:
                out_.add(l)
        func_lines[oldp], outside[oldp] = fl, out_

    rows = {}
    for t in universe:
        cl = cf = cfn = 0
        for f, d in all_changed:
            oldp = d.get("old_path", f)
            lines = set(pcov.get(t, {}).get(oldp, []))
            if not lines:
                continue
            cf = 1
            old = set(d["old"])
            if old & lines or old & pimp.get(oldp, set()):
                cl = 1
            if func_lines[oldp] & lines or outside[oldp] & (lines | pimp.get(oldp, set())):
                cfn = 1
        dist = static_distance(t, changed_mods, graph, known)
        name = t.rsplit("/", 1)[-1]
        rows[t] = {
            "cov_line": cl, "cov_func": cfn, "cov_file": cf,
            "static_inv_dist": 0.0 if dist is None else 1.0 / dist,
            "static_reach": dist is not None,
            "name_match": int(any(s and s in name for s in stems)),
            "cochange": (co.get(t, 0) / base) if base else 0.0,
            "test_changed": int(t in changed_tests),
            "new_test": int(t not in prun["durations"]),
            "time_plan": prun["durations"].get(t, None),
            "time_true": durations.get(t, 0.0),
            "label": int(t in affected),
        }
    med = float(np.median([r["time_plan"] for r in rows.values() if r["time_plan"] is not None] or [0.01]))
    for r in rows.values():
        if r["time_plan"] is None:
            r["time_plan"] = med
        r["time_plan"] = max(r["time_plan"], 1e-3)

    # ---------- uncertainty triggers
    # file level (study v1): coarse; module-level uses the NEW run's import-time lines
    uncovered_file = False
    for f, d in all_changed:
        oldp = d.get("old_path", f)
        old = set(d["old"])
        hit_any = any(old & set(pcov.get(t, {}).get(oldp, [])) for t in pcov)
        if d["status"] == "A" or (old and not hit_any and not (old & pimp.get(oldp, set()))):
            uncovered_file = True
    file_trig = {
        "dynamic_call": any(cstatic.get(f, {}).get("dynamic") for f in changed_src),
        "untested_change": uncovered_file,
        "static_runtime_conflict": any(r["cov_file"] and not r["static_reach"] for r in rows.values()),
        "module_level_change": any(set(d["new"]) & imp_lines.get(f, set()) for f, d in changed_src.items()),
    }
    # line level (study v2): only the changed lines and their enclosing functions; static facts of
    # the new version and dynamic evidence of the previous version, nothing from the new run
    dyn_l = mod_l = unt_l = False
    for f, d in changed_src.items():
        st = cstatic.get(f, {})
        defs, dynl, modl = st.get("defs", []), set(st.get("dyn_lines", [])), set(st.get("mod_lines", []))
        for l in d["new"]:
            D = innermost(defs, l)
            if (D and any(D[0] <= x <= D[1] for x in dynl)) or l in dynl:
                dyn_l = True
            if l in modl:
                mod_l = True
    for f, d in all_changed:
        oldp = d.get("old_path", f)
        if d["status"] == "A":
            # a new module is untested unless a test added or changed in this commit imports it
            if not any(rows[t]["static_reach"] and (rows[t]["test_changed"] or rows[t]["new_test"]) for t in rows):
                unt_l = True
            continue
        if set(d["old"]) & set(pstatic.get(oldp, {}).get("mod_lines", [])):
            mod_l = True                       # a deleted or edited import-time statement
        executed = set().union(*[set(pcov.get(t, {}).get(oldp, [])) for t in pcov]) if pcov else set()
        if func_lines[oldp] and not (func_lines[oldp] & executed):
            unt_l = True
        if outside[oldp] and not (outside[oldp] & (executed | pimp.get(oldp, set()))) \
                and outside[oldp] & set(pstatic.get(oldp, {}).get("mod_lines", [])):
            unt_l = True
    line_trig = {
        "dynamic_call": dyn_l,
        "untested_change": unt_l,
        "static_runtime_conflict": any(r["cov_line"] and not r["static_reach"] for r in rows.values()),
        "module_level_change": mod_l,
    }
    return {"sha": rec["sha"], "index": rec["index"], "date": rec["date"], "subject": rec.get("subject", ""),
            "rows": rows, "affected": affected, "universe": universe, "mutants": mutants,
            "trig_file": file_trig, "trig_line": line_trig, "namerts_gt": rec.get("namerts_gt"),
            "changed_src": sorted(f for f, _ in all_changed)}

def hist_lookup(meta):
    order = {h["sha"]: i for i, h in enumerate(meta["history"])}
    def before(sha):
        i = order.get(sha)
        return meta["history"][:i] if i is not None else meta["history"]
    return before

def load_changes(name):
    meta, recs = load_project(name)
    snaps = Snaps(name)
    hist = hist_lookup(meta)
    cs, skipped = [], defaultdict(int)
    for rec in recs:
        prev, cur = snaps.get(rec["parent"]), snaps.get(rec["sha"])
        if not prev or not cur:
            skipped["missing snapshot"] += 1; continue
        if not prev["run"]["covered"] or not cur["run"]["covered"]:
            skipped["no coverage"] += 1; continue
        c = build_change(meta, rec, prev, cur, hist)
        if c:
            c["loc"] = sum(n for f, n in cur["loc"].items() if is_src(f, meta["spec"]))
            c["suite_time"] = sum(cur["run"]["durations"].values())
            cs.append(c)
        else:
            skipped["no source change / no tests"] += 1
    return meta, cs, dict(skipped), len(recs)

# ------------------------------------------------------------------ selection and metrics
def forced(c):
    return {t for t, r in c["rows"].items() if r["test_changed"] or r["new_test"]}

def baseline_sets(c):
    R = c["rows"]; F = forced(c)
    out = {
        "Retest-all": set(c["universe"]),
        "Name matching": F | {t for t, r in R.items() if r["name_match"]},
        "Static import": F | {t for t, r in R.items() if r["static_reach"]},
        "File coverage": F | {t for t, r in R.items() if r["cov_file"]},
        "Function coverage": F | {t for t, r in R.items() if r["cov_func"]},
        "Line coverage": F | {t for t, r in R.items() if r["cov_line"]},
        "Hybrid": F | {t for t, r in R.items() if r["static_reach"] or r["cov_file"]},
    }
    return out

def evaluate_set(c, sel):
    U, A = set(c["universe"]), c["affected"]
    sel = set(sel) & U
    t_all = sum(c["rows"][t]["time_true"] for t in U) or 1e-9
    t_sel = sum(c["rows"][t]["time_true"] for t in sel)
    ms = c["mutants"]
    det = [bool(sel & set(m["killers"])) for m in ms]
    e = {
        "safe": A <= sel,
        "recall": (len(A & sel) / len(A)) if A else 1.0,
        "precision": (len(A & sel) / len(sel)) if sel else (1.0 if not A else 0.0),
        "test_red": 1 - len(sel) / len(U),
        "time_red": 1 - t_sel / t_all,
        "has_affected": bool(A),
        "mut_n": len(ms), "mut_det": sum(det), "fault_safe": all(det),
    }
    if c.get("namerts_gt") is not None:
        G = set(c["namerts_gt"]) & U
        e["n_safe"] = G <= sel
        e["n_recall"] = (len(G & sel) / len(G)) if G else 1.0
        e["n_has"] = bool(G)
    return e

def budget_select(c, scores, b):
    R = c["rows"]
    total = sum(R[t]["time_plan"] for t in c["universe"])
    order = sorted(c["universe"], key=lambda t: (-(scores[t] / R[t]["time_plan"]), t))
    sel, used = [], 0.0
    for t in sorted(forced(c)):
        sel.append(t); used += R[t]["time_plan"]
    for t in order:
        if t in sel:
            continue
        if used + R[t]["time_plan"] <= b * total:
            sel.append(t); used += R[t]["time_plan"]
    return set(sel)

def X_of(c, feats):
    ts = c["universe"]
    return ts, np.array([[c["rows"][t][k] for k in feats] for t in ts], dtype=float), \
        np.array([c["rows"][t]["label"] for t in ts])

def train(commits, feats=None):
    feats = feats or FEATURES
    Xs, ys = [], []
    for c in commits:
        _, X, y = X_of(c, feats)
        Xs.append(X); ys.append(y)
    if not Xs:
        return None
    X, y = np.vstack(Xs), np.concatenate(ys)
    if len(set(y)) < 2:
        return None
    m = LogisticRegression(class_weight="balanced", max_iter=2000)
    m.fit(X, y)
    m.feats_ = list(feats)
    return m

def scores_of(model, c):
    """Test scores of one change; cached on the model object (ids of discarded models can be reused)."""
    if model is None:
        return {t: 1.0 for t in c["universe"]}
    cache = model.__dict__.setdefault("score_cache_", {})
    key = c["sha"] + ":" + str(c["index"])
    if key not in cache:
        ts, X, _ = X_of(c, model.feats_)
        cache[key] = dict(zip(ts, model.predict_proba(X)[:, 1]))
    return cache[key]

def crc_threshold(calib, model, alpha):
    """Conformal risk control: largest lambda with n/(n+1) R_n(lambda) + 1/(n+1) <= alpha, where the
    loss of a calibration change is 1 if an affected (non-forced) test scores below lambda."""
    n = len(calib)
    if n == 0:
        return -1.0
    mins = []
    for c in calib:
        s = scores_of(model, c)
        F = forced(c)
        ps = [s[t] for t in c["affected"] if t not in F and t in s]
        mins.append(min(ps) if ps else math.inf)
    cands = sorted(set([0.0] + [m for m in mins if m != math.inf] + [1.0]))
    best = -1.0
    for lam in cands:
        risk = sum(1 for m in mins if lam > m) / n
        if n / (n + 1) * risk + 1 / (n + 1) <= alpha:
            best = max(best, lam)
    return best

def fit_recalibration(calib, model):
    """Isotonic recalibration of test-level probabilities on the calibration changes (non-forced tests)."""
    from sklearn.isotonic import IsotonicRegression
    xs, ys = [], []
    for c in calib:
        s, F = scores_of(model, c), forced(c)
        for t in c["universe"]:
            if t not in F:
                xs.append(s[t]); ys.append(c["rows"][t]["label"])
    if len(set(ys)) < 2:
        return lambda p: p
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(xs, ys)
    return lambda p: float(iso.predict([p])[0])

def residual_risk(c, s, sel, recal):
    """Estimated probability that the selection misses an affected test: 1 - prod over skipped tests of (1 - p)."""
    keep = 1.0
    for t in c["universe"]:
        if t not in sel:
            keep *= 1.0 - recal(s[t])
    return 1.0 - keep

ACI_GAMMA = 0.02

def crc_online(cs, k, model, alpha, window, gamma=None):
    """Time-aware calibration for the test changes cs[k:]. Each change is calibrated on the `window`
    most recent earlier changes (whose ground truth is known by then, e.g. from post-merge full runs).
    With gamma, adaptive conformal inference (Gibbs and Candes, 2021) also updates the level online:
    alpha_t+1 = alpha_t + gamma * (alpha - err_t), so the long-run miss rate tracks alpha under drift."""
    a_t, out = alpha, []
    for j in range(k, len(cs)):
        cal = cs[max(0, j - window): j]
        lam = crc_threshold(cal, model, min(a_t, 1.0)) if a_t > 0 else -1.0
        c = cs[j]
        sel = calibrated_set(c, scores_of(model, c), lam)
        err = 0.0 if c["affected"] <= sel else 1.0
        out.append((sel, lam))
        if gamma:
            a_t = a_t + gamma * (alpha - err)
    return out

def calibrated_set(c, s, lam):
    return (forced(c) | {t for t in c["universe"] if s[t] >= lam}) if lam >= 0 else set(c["universe"])

def split(cs):
    k = max(1, int(len(cs) * CALIB_FRAC))
    return cs[:k], cs[k:]

# ------------------------------------------------------------------ aggregation and statistics
rng = np.random.default_rng(0)

def boot(x):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return None
    idx = rng.integers(0, len(x), size=(B_RESAMPLES, len(x)))
    means = x[idx].mean(axis=1)
    return [float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]

def aggregate(evals, ci=False):
    if not evals:
        return {}
    out = {"n": len(evals)}
    wa = [e for e in evals if e["has_affected"]]
    f = boot if ci else (lambda x: float(np.mean(x)) if len(x) else None)
    out["recall"] = f([e["recall"] for e in wa])
    out["precision"] = f([e["precision"] for e in wa])
    out["safe_rate"] = f([e["safe"] for e in evals])
    out["test_red"] = f([e["test_red"] for e in evals])
    out["time_red"] = f([e["time_red"] for e in evals])
    mut = [e for e in evals if e["mut_n"]]
    out["mut_changes"] = len(mut)
    out["mut_total"] = int(sum(e["mut_n"] for e in mut))
    out["mut_detected"] = int(sum(e["mut_det"] for e in mut))
    out["mut_rate"] = (out["mut_detected"] / out["mut_total"]) if out["mut_total"] else None
    out["fault_safe"] = f([e["fault_safe"] for e in mut]) if mut else None
    nr = [e for e in evals if "n_safe" in e]
    if nr:
        out["n_safe"] = f([e["n_safe"] for e in nr])
        out["n_recall"] = f([e["n_recall"] for e in nr if e["n_has"]])
    return out

def wilcox(a, b):
    from scipy.stats import wilcoxon
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    if np.all(d == 0):
        return {"n": len(d), "nonzero": 0, "p": 1.0, "mean_diff": 0.0}
    r = wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
    return {"n": len(d), "nonzero": int(np.sum(d != 0)), "p": float(r.pvalue), "mean_diff": float(d.mean())}

def mcnemar(a, b):
    from scipy.stats import binomtest
    b01 = sum(1 for x, y in zip(a, b) if x and not y)
    b10 = sum(1 for x, y in zip(a, b) if y and not x)
    p = binomtest(b01, b01 + b10, 0.5).pvalue if b01 + b10 else 1.0
    return {"a_only": b01, "b_only": b10, "p": float(p)}

# ------------------------------------------------------------------ main
ABLATIONS = [("line coverage", ["cov_line"]), ("function coverage", ["cov_func"]), ("file coverage", ["cov_file"]),
             ("static import", ["static_inv_dist"]), ("name match", ["name_match"]), ("co-change", ["cochange"]),
             ("test changed", ["test_changed"]), ("all coverage", ["cov_line", "cov_func", "cov_file"])]

def main(projects):
    OUT.mkdir(exist_ok=True)
    data, summary, kind = {}, {}, {}
    for p in projects:
        meta, cs, skipped, n_recs = load_changes(p)
        data[p], kind[p] = cs, meta.get("mode", "history")
        summary[p] = {
            "mode": kind[p], "changes_collected": n_recs, "changes": len(cs), "skipped": skipped,
            "calib": len(split(cs)[0]) if cs else 0, "test": len(split(cs)[1]) if cs else 0,
            "kloc": round(cs[-1]["loc"] / 1000, 1) if cs else None,
            "test_files": round(float(np.mean([len(c["universe"]) for c in cs])), 1) if cs else None,
            "suite_time": round(float(np.mean([c["suite_time"] for c in cs])), 1) if cs else None,
            "avg_affected": round(float(np.mean([len(c["affected"]) for c in cs])), 1) if cs else None,
            "first": cs[0]["date"][:10] if cs else None, "last": cs[-1]["date"][:10] if cs else None,
            "mutants_killed": sum(len(c["mutants"]) for c in cs),
            "python": meta.get("python"),
        }
        print(p, summary[p], flush=True)

    hist_p = [p for p in projects if kind[p] == "history" and data[p]]
    pair_p = [p for p in projects if kind[p] == "pairs" and data[p]]

    # per-change evaluations: E[key][project] = list of eval dicts (same change order everywhere)
    E = defaultdict(lambda: defaultdict(list))
    per_change = defaultdict(list)          # for failure cases
    results = {"summary": summary, "features": FEATURES, "calibration": {}, "triggers": {}, "coefficients": {},
               "protocol": {"calib_frac": CALIB_FRAC, "budgets": BUDGETS, "alphas": ALPHAS, "random_seeds": 20,
                            "ablation_budget": ABL_BUDGET, "main_alpha": MAIN_ALPHA,
                            "training": "leave-one-project-out over the history projects; NameRTS projects use a model trained on all history projects",
                            "calibration": "first 40% of each project's changes in time order (never used for training)"}}
    ground_truth_check = defaultdict(lambda: [0, 0])     # killers within coverage-affected set
    RISK = defaultdict(lambda: defaultdict(list))        # mode -> project -> [(predicted r(c), observed miss)]
    RISKAB = defaultdict(lambda: defaultdict(list))      # calibration variant -> project -> [r(c) > alpha]

    for p in hist_p + pair_p:
        calib, test = split(data[p])
        train_set = [c for q in hist_p if q != p for c in data[q]]
        model = train(train_set)
        if model is not None:
            results["coefficients"][p] = dict(zip(model.feats_, map(float, model.coef_[0])))
        for c in test:
            for m in c["mutants"]:
                ground_truth_check[p][0] += 1
                ground_truth_check[p][1] += set(m["killers"]) <= c["affected"]

        # baselines (+ published NameRTS selections on the NameRTS commits)
        nsel = {}
        if p in NAMERTS_KEYS:
            f = NAMERTS / f"NameBDP_RTSTest_{NAMERTS_KEYS[p]}.json"
            if f.exists():
                nsel = {r["current"]: set(r["tests_to_run"]) for r in json.loads(f.read_text())}
        for c in test:
            sets = baseline_sets(c)
            if c["sha"] in nsel:
                sets["NameRTS"] = forced(c) | nsel[c["sha"]]
            for name, sel in sets.items():
                E["base:" + name][p].append(evaluate_set(c, sel))

        # budget mode
        for b in BUDGETS:
            for c in test:
                s = scores_of(model, c)
                E[f"budget:{b}:CodeTwin"][p].append(evaluate_set(c, budget_select(c, s, b)))
                covs = {t: 3 * c["rows"][t]["cov_line"] + 2 * c["rows"][t]["cov_func"] + c["rows"][t]["cov_file"]
                        + 0.5 * c["rows"][t]["static_inv_dist"] for t in c["universe"]}
                E[f"budget:{b}:Coverage-ranked"][p].append(evaluate_set(c, budget_select(c, covs, b)))
                rr = []
                for seed in range(20):
                    rnd = random.Random(seed * 7919 + c["index"])
                    rr.append(evaluate_set(c, budget_select(c, {t: rnd.random() for t in c["universe"]}, b)))
                avg = {k: float(np.mean([x[k] for x in rr])) for k in ("recall", "precision", "test_red", "time_red", "safe",
                                                                        "mut_det", "fault_safe")}
                avg.update({"has_affected": rr[0]["has_affected"], "mut_n": rr[0]["mut_n"]})
                E[f"budget:{b}:Random"][p].append(avg)

        # per-change residual-risk estimate r(c) and the observed outcome
        recal = fit_recalibration(calib, model)
        for c in test:
            s = scores_of(model, c)
            for mode, sel in (("budget25", budget_select(c, s, 0.25)), ("crc10", calibrated_set(c, s, crc_threshold(calib, model, MAIN_ALPHA))),
                              ("linecov", baseline_sets(c)["Line coverage"])):
                RISK[mode][p].append((residual_risk(c, s, sel, recal), 0.0 if c["affected"] <= sel else 1.0))

        # calibrated selection with and without abstention
        cres = {}
        k = len(calib)
        for a in ALPHAS:
            lam = crc_threshold(calib, model, a)
            variants = {"crc": [(calibrated_set(c, scores_of(model, c), lam), lam) for c in test],
                        "win": crc_online(data[p], k, model, a, window=k),
                        "aci": crc_online(data[p], k, model, a, window=k, gamma=ACI_GAMMA)}
            for vname, sels in variants.items():
                for c, (sel, _) in zip(test, sels):
                    E[f"{vname}:{a}:plain"][p].append(evaluate_set(c, sel))
                    bs = baseline_sets(c)
                    hyb = bs["Hybrid"] | sel
                    fcov = bs["File coverage"] | sel
                    rc_ = residual_risk(c, scores_of(model, c), sel, recal)
                    risky = rc_ > a
                    if vname == "aci" and a == MAIN_ALPHA:
                        RISK["aci10"][p].append((rc_, 0.0 if c["affected"] <= sel else 1.0))
                    RISKAB[f"{vname}:{a}"][p].append(risky)
                    for lvl in ("file", "line", "risk"):
                        fired = risky if lvl == "risk" else any(c["trig_" + lvl].values())
                        E[f"{vname}:{a}:abstain-{lvl}:full"][p].append(evaluate_set(c, set(c["universe"]) if fired else sel))
                        E[f"{vname}:{a}:abstain-{lvl}:hybrid"][p].append(evaluate_set(c, hyb if fired else sel))
                        E[f"{vname}:{a}:abstain-{lvl}:filecov"][p].append(evaluate_set(c, fcov if fired else sel))
            n_ab = {lvl: sum(any(c["trig_" + lvl].values()) for c in test) for lvl in ("file", "line")}
            for c in test:
                s = scores_of(model, c)
                sel = calibrated_set(c, s, lam)
                if a == MAIN_ALPHA:
                    ev = evaluate_set(c, sel)
                    per_change[p].append({"sha": c["sha"][:7], "subject": c["subject"][:80], "safe": ev["safe"],
                                          "time_red": ev["time_red"], "missed": sorted(c["affected"] - sel),
                                          "missed_scores": [round(float(s[t]), 3) for t in sorted(c["affected"] - sel)],
                                          "trig_line": [k for k, v in c["trig_line"].items() if v],
                                          "trig_file": [k for k, v in c["trig_file"].items() if v],
                                          "fault_safe": ev["fault_safe"], "mut_n": ev["mut_n"]})
            cres[str(a)] = {"lambda": float(lam), "n_calib": len(calib), "n_test": len(test), "feasible": bool(lam >= 0),
                            "abstain_file": n_ab["file"] / len(test) if test else None,
                            "abstain_line": n_ab["line"] / len(test) if test else None}
        results["calibration"][p] = cres

        # triggers against the line-coverage baseline
        for c in test:
            c["trig_risk"] = {"r(c) > 0.1": residual_risk(c, scores_of(model, c), baseline_sets(c)["Line coverage"], recal) > MAIN_ALPHA}
        tr = {}
        for lvl in ("file", "line", "risk"):
            unsafe = [c for c in test if not evaluate_set(c, baseline_sets(c)["Line coverage"])["safe"]]
            safe_ = [c for c in test if evaluate_set(c, baseline_sets(c)["Line coverage"])["safe"]]
            keys = list(test[0]["trig_" + lvl]) if test else []
            tr[lvl] = {"test": len(test), "unsafe": len(unsafe), "safe": len(safe_),
                       "flag_unsafe": sum(any(c["trig_" + lvl].values()) for c in unsafe),
                       "flag_safe": sum(any(c["trig_" + lvl].values()) for c in safe_),
                       "per_trigger": {k: sum(c["trig_" + lvl][k] for c in test) for k in keys},
                       "per_trigger_unsafe": {k: sum(c["trig_" + lvl][k] for c in unsafe) for k in keys}}
        results["triggers"][p] = tr

        # ablation (budget mode)
        variants = [("Full model", FEATURES)] + [("- " + n, [f for f in FEATURES if f not in drop]) for n, drop in ABLATIONS]
        for name, feats in variants:
            m = train(train_set, feats)
            for c in test:
                E["abl:" + name][p].append(evaluate_set(c, budget_select(c, scores_of(m, c), ABL_BUDGET)))

    rr = {}
    for mode, d in RISK.items():
        for grp, ps in (("HIST", hist_p), ("NRTS", pair_p)):
            pts = [x for q in ps for x in d[q]]
            if not pts:
                continue
            pr, ob = np.array([x[0] for x in pts]), np.array([x[1] for x in pts])
            bins = np.clip((pr * 5).astype(int), 0, 4)
            ece = sum(abs(pr[bins == b].mean() - ob[bins == b].mean()) * (bins == b).sum() for b in range(5) if (bins == b).any()) / len(pr)
            rr[f"{mode}:{grp}"] = {"n": len(pts), "mean_predicted": float(pr.mean()), "observed_miss_rate": float(ob.mean()),
                                   "brier": float(np.mean((pr - ob) ** 2)), "brier_constant": float(np.mean((ob.mean() - ob) ** 2)),
                                   "ece5": float(ece),
                                   "bins": [[b / 5, (b + 1) / 5, int((bins == b).sum()), float(pr[bins == b].mean()) if (bins == b).any() else None,
                                             float(ob[bins == b].mean()) if (bins == b).any() else None] for b in range(5)]}
    results["residual_risk"] = rr
    results["ground_truth_check"] = {p: {"killed_mutants": v[0], "killers_within_affected": v[1]} for p, v in ground_truth_check.items()}

    # ---------------- aggregate: per project, pooled over history projects ("HIST"), over NameRTS projects ("NRTS")
    def block(key, ci=False):
        d = {p: aggregate(E[key][p]) for p in hist_p + pair_p if E[key][p]}
        d["HIST"] = aggregate([e for p in hist_p for e in E[key][p]], ci=ci)
        if pair_p:
            d["NRTS"] = aggregate([e for p in pair_p for e in E[key][p]], ci=ci)
        return d
    results["agg"] = {k: block(k, ci=True) for k in sorted(E)}
    results["risk_abstain_rate"] = {k: {grp: (float(np.mean([x for q in ps for x in d[q]])) if any(d[q] for q in ps) else None)
                                        for grp, ps in (("HIST", hist_p), ("NRTS", pair_p))} for k, d in RISKAB.items()}
    for a in ALPHAS:
        for lvl in ("file", "line"):
            for grp, ps in (("HIST", hist_p), ("NRTS", pair_p)):
                n = sum(len(E[f"crc:{a}:plain"][p]) for p in ps)
                fired = sum((results["calibration"][p][str(a)]["abstain_" + lvl] or 0) * len(E[f"crc:{a}:plain"][p]) for p in ps)
                results["agg"].setdefault("abstain_rate", {})[f"{a}:{lvl}:{grp}"] = fired / n if n else None

    # ---------------- paired tests (pooled history projects)
    def pooled(key, metric, only_aff=False):
        return [e[metric] for p in hist_p for e in E[key][p] if (e["has_affected"] or not only_aff)]
    T = {}
    for b in BUDGETS:
        T[f"recall@{b}: CodeTwin vs Coverage-ranked"] = wilcox(pooled(f"budget:{b}:CodeTwin", "recall", True), pooled(f"budget:{b}:Coverage-ranked", "recall", True))
        T[f"recall@{b}: CodeTwin vs Random"] = wilcox(pooled(f"budget:{b}:CodeTwin", "recall", True), pooled(f"budget:{b}:Random", "recall", True))
    ck = f"crc:{MAIN_ALPHA}:plain"
    for base in ("Line coverage", "Function coverage", "File coverage"):
        T[f"safety: CRC(alpha={MAIN_ALPHA}) vs {base}"] = mcnemar(pooled(ck, "safe"), pooled("base:" + base, "safe"))
        T[f"time_red: CRC(alpha={MAIN_ALPHA}) vs {base}"] = wilcox(pooled(ck, "time_red"), pooled("base:" + base, "time_red"))
    results["tests"] = T
    results["failure_cases"] = {p: [x for x in v if not x["safe"]] for p, v in per_change.items()}
    # tests missed by line coverage: did they execute the changed file in the old version?
    missed = [c["rows"][t]["cov_file"] for p in hist_p for c in split(data[p])[1]
              for t in c["affected"] - baseline_sets(c)["Line coverage"]]
    results["line_missed_tests"] = len(missed)
    results["line_missed_with_file_cov"] = int(sum(missed))

    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=_jsonable))
    write_report(results, hist_p, pair_p)
    write_plots(results, hist_p, pair_p)
    write_extra_plots(results, hist_p, pair_p)
    print("wrote results/", flush=True)
    return results

def _jsonable(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, (set, np.ndarray)):
        return list(o.tolist() if isinstance(o, np.ndarray) else sorted(o))
    raise TypeError(f"not JSON serializable: {type(o).__name__}")

# ------------------------------------------------------------------ report
def v(x, pct=True, d=1):
    if x is None:
        return "--"
    if isinstance(x, list):
        x = x[0]
    return f"{100 * x:.{d}f}" if pct else f"{x:.{d}f}"

def ci(x, pct=True, d=1):
    if not isinstance(x, list):
        return v(x, pct, d)
    f = (lambda y: f"{100 * y:.{d}f}") if pct else (lambda y: f"{y:.{d}f}")
    return f"{f(x[0])} [{f(x[1])}, {f(x[2])}]"

def write_report(R, hist_p, pair_p):
    A, S = R["agg"], R["summary"]
    L = ["# CodeTwin AI study v2 -- results", "", "## Subjects", "",
         "| Project | Mode | Changes | Calib | Test | KLoC | Test files | Suite (s) | Affected | Killed mutants | Period |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in hist_p + pair_p:
        s = S[p]
        L.append(f"| {p} | {s['mode']} | {s['changes']} | {s['calib']} | {s['test']} | {s['kloc']} | {s['test_files']} | "
                 f"{s['suite_time']} | {s['avg_affected']} | {s['mutants_killed']} | {s['first']} to {s['last']} |")
    L += ["", "Skipped changes: " + json.dumps({p: S[p]["skipped"] for p in S}), ""]
    for grp in ("HIST", "NRTS"):
        if grp == "NRTS" and not pair_p:
            continue
        L += [f"## Selection quality ({grp})", "",
              "| Technique | Test red % | Time red % | Precision | Recall | Safe % | Mutants detected % | Fault-safe % | NameRTS-GT safe % |",
              "|---|---|---|---|---|---|---|---|---|"]
        keys = [k for k in A if k.startswith("base:")] + [f"budget:{ABL_BUDGET}:CodeTwin"] + \
               [f"{vn}:{a}:plain" for vn in ("crc", "win", "aci") for a in ALPHAS] + \
               [f"{vn}:{a}:abstain-{lv}:{fb}" for vn in ("crc", "aci") for lv in ("risk", "line", "file") for fb in ("filecov", "hybrid", "full") for a in ALPHAS]
        for k in keys:
            a = A.get(k, {}).get(grp)
            if not a:
                continue
            L.append(f"| {k} | {ci(a['test_red'])} | {ci(a['time_red'])} | {v(a['precision'], False, 2)} | {v(a['recall'], False, 3)} | "
                     f"{ci(a['safe_rate'])} | {v(a['mut_rate'])} ({a['mut_detected']}/{a['mut_total']}) | {v(a.get('fault_safe'))} | "
                     f"{v(a.get('n_safe'))} |")
        L.append("")
    L += ["## Budget mode (HIST, recall)", "", "| Budget | CodeTwin | Coverage-ranked | Random |", "|---|---|---|---|"]
    for b in BUDGETS:
        L.append(f"| {b} | " + " | ".join(ci(A[f'budget:{b}:{n}']['HIST']['recall'], False, 3)
                                         for n in ("CodeTwin", "Coverage-ranked", "Random")) + " |")
    L += ["", "## Calibration per project", "", "| Project | alpha | lambda | feasible | n calib | abstain file | abstain line |",
          "|---|---|---|---|---|---|---|"]
    for p, cr in R["calibration"].items():
        for a, x in cr.items():
            L.append(f"| {p} | {a} | {x['lambda']:.3f} | {x['feasible']} | {x['n_calib']} | {v(x['abstain_file'])} | {v(x['abstain_line'])} |")
    L += ["", "## Abstention rates (pooled)", "", "```", json.dumps(A["abstain_rate"], indent=1), "```",
          "", "## Risk-based abstention rates (r(c) > alpha)", "", "```", json.dumps(R["risk_abstain_rate"], indent=1), "```"]
    L += ["", "## Triggers vs line-coverage misses", "", "```", json.dumps(R["triggers"], indent=1), "```"]
    L += ["", "## Ablation (HIST, 25% budget)", "", "| Model | Recall | Safe % | Mutants detected % |", "|---|---|---|---|"]
    for k in [k for k in A if k.startswith("abl:")]:
        a = A[k]["HIST"]
        L.append(f"| {k[4:]} | {v(a['recall'], False, 3)} | {v(a['safe_rate'])} | {v(a['mut_rate'])} |")
    L += ["", "## Per-project (CRC alpha=0.1 plain / line-abstain hybrid)", ""]
    for p in hist_p + pair_p:
        a1, a2 = A[f"crc:{MAIN_ALPHA}:plain"].get(p, {}), A[f"crc:{MAIN_ALPHA}:abstain-line:hybrid"].get(p, {})
        L.append(f"- {p}: plain safe {v(a1.get('safe_rate'))}, time red {v(a1.get('time_red'))}; "
                 f"line-abstain+hybrid safe {v(a2.get('safe_rate'))}, time red {v(a2.get('time_red'))}; "
                 f"line cov safe {v(A['base:Line coverage'].get(p, {}).get('safe_rate'))}, "
                 f"time red {v(A['base:Line coverage'].get(p, {}).get('time_red'))}")
    L += ["", "## Per-change residual-risk estimate r(c) vs observed misses", "", "```", json.dumps(R["residual_risk"], indent=1), "```"]
    L += ["", "## Paired tests (HIST)", "", "```", json.dumps(R["tests"], indent=1), "```",
          "", "## Ground-truth check: killers of killed mutants inside the coverage-affected set", "", "```",
          json.dumps(R["ground_truth_check"], indent=1), "```", "", "## Coefficients", "", "```",
          json.dumps(R["coefficients"], indent=1), "```", "", "## Failure cases (CRC alpha=0.1, unsafe)", "", "```",
          json.dumps(R["failure_cases"], indent=1), "```"]
    (OUT / "stats.md").write_text("\n".join(L) + "\n")

def write_plots(R, hist_p, pair_p):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    A = R["agg"]
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    xs = [int(b * 100) for b in BUDGETS]
    for n, st, lab in (("CodeTwin", "-o", "CodeTwin AI"), ("Coverage-ranked", "--s", "Coverage-ranked"), ("Random", ":^", "Random (20 seeds)")):
        ys = [A[f"budget:{b}:{n}"]["HIST"]["recall"][0] for b in BUDGETS]
        ax.plot(xs, ys, st, color="black", lw=1, ms=4, label=lab)
    ax.set_xlabel("Budget (% of full-suite time)", fontsize=8); ax.set_ylabel("Recall of affected tests", fontsize=8)
    ax.set_xticks(xs); ax.set_ylim(0, 1.02); ax.tick_params(labelsize=7); ax.grid(alpha=0.3, lw=0.5)
    ax.legend(fontsize=7, frameon=False); fig.tight_layout()
    fig.savefig(OUT / "budget.pdf"); fig.savefig(OUT / "budget.png", dpi=200); plt.close(fig)

    # calibration plot: observed miss rate vs target alpha (plain CRC), per group
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.plot([0, 0.32], [0, 0.32], color="grey", lw=0.8, ls=":", label="observed = target")
    for vn, mk, lab in (("crc", "o-", "Static calibration"), ("win", "s--", "Sliding window"), ("aci", "^-.", "Adaptive (ACI)")):
        if any("safe_rate" not in A[f"{vn}:{a}:plain"].get("HIST", {}) for a in ALPHAS):
            continue
        ys = [1 - A[f"{vn}:{a}:plain"]["HIST"]["safe_rate"][0] for a in ALPHAS]
        ax.plot(ALPHAS, ys, mk, color="black", lw=1, ms=4, label=lab)
    ax.set_xlabel(r"Target miss rate $\alpha$", fontsize=8); ax.set_ylabel("Observed miss rate", fontsize=8)
    ax.set_xlim(0, 0.22); ax.set_ylim(0, 0.32); ax.set_xticks(ALPHAS); ax.set_xticklabels([f"{a:.2f}" for a in ALPHAS]); ax.tick_params(labelsize=7); ax.grid(alpha=0.3, lw=0.5)
    ax.legend(fontsize=7, frameon=False); fig.tight_layout()
    fig.savefig(OUT / "calibration.pdf"); fig.savefig(OUT / "calibration.png", dpi=200); plt.close(fig)

def write_extra_plots(R, hist_p, pair_p):
    """Figures for the paper beyond the budget and calibration curves (all from results.json)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    A = R["agg"]
    m = lambda x: x[0] if isinstance(x, list) else x
    plt.rcParams.update({"font.size": 7})

    # 1) trade-off: time saved vs observed miss rate (history projects)
    pts = [("Retest-all", "base:Retest-all", "o"), ("Name matching", "base:Name matching", "o"),
           ("Static import", "base:Static import", "o"), ("Hybrid", "base:Hybrid", "o"),
           ("File coverage", "base:File coverage", "o"), ("Function coverage", "base:Function coverage", "o"),
           ("Line coverage", "base:Line coverage", "o"), ("Budget 25%", "budget:0.25:CodeTwin", "s"),
           ("Static CRC 0.10", "crc:0.1:plain", "v"), ("ACI 0.05", "aci:0.05:plain", "^"),
           ("ACI 0.10", "aci:0.1:plain", "^"), ("ACI 0.20", "aci:0.2:plain", "^"),
           ("ACI 0.10 + risk abst.", "aci:0.1:abstain-risk:filecov", "D"),
           ("ACI 0.05 + risk abst.", "aci:0.05:abstain-risk:filecov", "D")]
    off = {"Name matching": (-4, 5, "right"), "Budget 25%": (-5, -3, "right"), "ACI 0.20": (4, 3, "left"),
           "Static CRC 0.10": (5, -5, "left"), "Function coverage": (-5, 1, "right"), "ACI 0.10": (-5, 1, "right"),
           "Line coverage": (5, -2, "left"), "Retest-all": (0, 7, "left"), "Hybrid": (2, -9, "left"),
           "File coverage": (5, -2, "left")}
    fig, ax = plt.subplots(figsize=(3.5, 2.9))
    for lab, k, mk in pts:
        a = A[k]["HIST"]
        x, y = 100 * m(a["time_red"]), 100 * (1 - m(a["safe_rate"]))
        filled = mk in ("^", "D")
        ax.scatter(x, y, marker=mk, s=22, facecolors="black" if filled else "white", edgecolors="black", lw=0.8, zorder=3)
        dx, dy, ha = off.get(lab, (4, 2, "left"))
        ax.annotate(lab, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=5.5, ha=ha)
    ax.set_ylim(-0.6, 100)
    ax.set_xlabel("Test time saved (%)"); ax.set_ylabel("Changes with a missed affected test (%)")
    ax.set_yscale("symlog", linthresh=5); ax.set_yticks([0, 2, 5, 10, 20, 40, 70]); ax.set_yticklabels(["0", "2", "5", "10", "20", "40", "70"])
    ax.set_xlim(-3, 88); ax.grid(alpha=0.3, lw=0.5)
    fig.tight_layout(); fig.savefig(OUT / "tradeoff.pdf"); fig.savefig(OUT / "tradeoff.png", dpi=200); plt.close(fig)

    # 2) per-project miss rate at alpha = 0.10 for the three calibration variants
    projs = [p for p in hist_p + pair_p if p in A["crc:0.1:plain"]]
    fig, ax = plt.subplots(figsize=(3.5, 2.2))
    w = 0.26
    for j, (vn, lab, col) in enumerate((("crc", "Static", "white"), ("win", "Sliding window", "0.65"), ("aci", "Adaptive (ACI)", "black"))):
        ys = [100 * (1 - m(A[f"{vn}:0.1:plain"][p]["safe_rate"])) for p in projs]
        ax.bar([i + (j - 1) * w for i in range(len(projs))], ys, w, color=col, edgecolor="black", lw=0.6, label=lab)
    ax.axhline(10, color="black", ls="--", lw=0.8, label="target 10%")
    ax.set_xticks(range(len(projs))); ax.set_xticklabels([p + ("*" if p in pair_p else "") for p in projs], rotation=30, ha="right")
    ax.set_ylabel("Missed changes (%)"); ax.legend(frameon=False, fontsize=6, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_ylim(0, max(32, ax.get_ylim()[1])); ax.grid(axis="y", alpha=0.3, lw=0.5)
    fig.tight_layout(); fig.savefig(OUT / "per_project.pdf"); fig.savefig(OUT / "per_project.png", dpi=200); plt.close(fig)

    # 3) abstention rules: share of unsafe and of safe changes they flag (vs line coverage misses)
    T = R["triggers"]
    labels, unsafe, safe = [], [], []
    for lvl, lab in (("file", "File-level\ntriggers"), ("line", "Line-level\ntriggers"), ("risk", "Risk\n$r(c)>\\alpha$")):
        tu = sum(T[p][lvl]["unsafe"] for p in hist_p); fu = sum(T[p][lvl]["flag_unsafe"] for p in hist_p)
        ts = sum(T[p][lvl]["safe"] for p in hist_p); fs = sum(T[p][lvl]["flag_safe"] for p in hist_p)
        labels.append(lab.replace("\\n", "\n")); unsafe.append(100 * fu / tu if tu else 0); safe.append(100 * fs / ts if ts else 0)
    fig, ax = plt.subplots(figsize=(3.5, 2.1))
    x = range(len(labels))
    b1 = ax.bar([i - 0.18 for i in x], unsafe, 0.36, color="black", label="unsafe changes flagged")
    b2 = ax.bar([i + 0.18 for i in x], safe, 0.36, color="white", edgecolor="black", lw=0.6, label="safe changes flagged")
    for b in list(b1) + list(b2):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.0f}", ha="center", fontsize=6)
    ax.set_xticks(list(x)); ax.set_xticklabels(labels); ax.set_ylim(0, 110); ax.set_ylabel("Changes flagged (%)")
    ax.legend(frameon=False, fontsize=6, loc="upper right"); ax.grid(axis="y", alpha=0.3, lw=0.5)
    fig.tight_layout(); fig.savefig(OUT / "triggers.pdf"); fig.savefig(OUT / "triggers.png", dpi=200); plt.close(fig)

    # 4) reliability diagram of r(c) (ACI selections at alpha = 0.10 and budget 25%)
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    ax.plot([0, 1], [0, 1], ls=":", color="grey", lw=0.8, label="perfect calibration")
    for key, mk, lab in (("aci10:HIST", "o-", "ACI, $\\alpha$=0.10"), ("budget25:HIST", "s--", "Budget 25%")):
        rr = R["residual_risk"].get(key)
        if not rr:
            continue
        bs = [b for b in rr["bins"] if b[2]]
        ax.plot([b[3] for b in bs], [b[4] for b in bs], mk, color="black", lw=1, ms=4, label=lab.replace("\\\\", "\\"))
        for b in bs:
            ax.annotate(str(b[2]), (b[3], b[4]), xytext=(4, -8) if mk.startswith("o") else (-10, 5), textcoords="offset points", fontsize=5)
    ax.set_xlabel("Estimated residual risk $r(c)$ (bin mean)"); ax.set_ylabel("Observed miss rate")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.grid(alpha=0.3, lw=0.5); ax.legend(frameon=False, fontsize=6, loc="upper left")
    fig.tight_layout(); fig.savefig(OUT / "reliability.pdf"); fig.savefig(OUT / "reliability.png", dpi=200); plt.close(fig)

if __name__ == "__main__":
    projs = sys.argv[1:] or sorted(p.name for p in DATA.iterdir() if (p / "meta.json").exists())
    main(projs)
