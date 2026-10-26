#!/usr/bin/env python3
"""
CodeTwin AI -- pilot analysis.

Reads data/<project>/ produced by collect.py and evaluates:
  baselines : RetestAll, NameMatch, StaticImport, CoverageFile, CoverageLine, Hybrid, Random@budget
  CodeTwin  : learned risk ranking @budget, conformal-calibrated selection, + abstention triggers
  ablation  : risk model retrained with one evidence signal removed at a time
Writes results/results.json, results/tables_*.tex (rows for the paper tables), results/budget.pdf/.png
Usage: python analyze.py [project ...]     (default: every project in data/)
"""
import json, math, random, sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "results"
BUDGETS = [0.10, 0.25, 0.50]
ALPHAS = [0.05, 0.10, 0.20]
CALIB_FRAC = 0.4          # first 40% of each project's commits calibrate; the rest are test commits
FEATURES = ["cov_line", "cov_file", "static_inv_dist", "name_match", "cochange", "test_changed"]

# ------------------------------------------------------------------ loading
def load_project(name):
    meta = json.loads((DATA / name / "meta.json").read_text())
    recs = [json.loads(p.read_text()) for p in sorted((DATA / name / "commits").glob("*.json"))]
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
def import_graph(static, src_root, known_modules):
    """file -> set(module names it imports, resolved to known modules)."""
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
    """BFS from a test file over imports; distance (1 = direct import) to any changed module, or None."""
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
            # importing a package also loads parent packages' __init__; approximated by prefix match
        frontier = nxt - seen
        if not frontier:
            break
    return None

# ------------------------------------------------------------------ per-commit records
def build_commit(meta, rec, prev, hist_index):
    spec = meta["spec"]
    url, src_root, pkgs, tests_dir, src_dirs = spec
    run, prun = rec["run"], prev["run"]
    durations = run["durations"]
    universe = sorted(t for t in durations if t in set(rec["tests_present"]) or t.startswith(tests_dir))
    if not universe:
        return None

    changed_src = {f: d for f, d in rec["diff"].items() if is_src(f, spec) and d["status"] != "D"}
    deleted_src = {f: d for f, d in rec["diff"].items() if is_src(f, spec) and d["status"] == "D"}
    changed_tests = {f for f, d in rec["diff"].items() if not is_src(f, spec) and d["status"] in ("A", "M", "R") and f in durations}
    if not changed_src and not deleted_src:
        return None

    # ---------- ground truth (coverage of the NEW version)
    cov = run["covered"]
    imp_lines = {f: set(v) for f, v in run.get("import_lines", {}).items()}
    affected = set(changed_tests)
    module_level_change = False
    for f, d in changed_src.items():
        new = set(d["new"])
        for t in universe:
            if new & set(cov.get(t, {}).get(f, [])):
                affected.add(t)
        if new & imp_lines.get(f, set()):
            module_level_change = True
            for t in universe:
                if f in cov.get(t, {}):
                    affected.add(t)
    for f, d in deleted_src.items():   # deleted module: tests that executed it before
        for t in universe:
            if f in prun["covered"].get(t, {}):
                affected.add(t)

    # ---------- evidence available BEFORE running tests (previous commit's coverage + static at c)
    pcov = prun["covered"]
    pimp = {f: set(v) for f, v in prun.get("import_lines", {}).items()}
    known = {module_of(f, src_root): f for f in rec["static"] if is_src(f, spec)}
    graph = import_graph(rec["static"], src_root, set(known))
    changed_mods = {module_of(f, src_root) for f in list(changed_src) + list(deleted_src)}
    stems = {f.rsplit("/", 1)[-1][:-3] for f in list(changed_src) + list(deleted_src)} - {"__init__"}

    # co-change: past commits (before this one) touching a changed src file
    past = hist_index["before"](rec["sha"])
    co = defaultdict(int); base = 0
    for h in past[-300:]:
        fs = set(h["files"])
        if fs & (set(changed_src) | set(deleted_src)):
            base += 1
            for t in fs:
                co[t] += 1

    rows = {}
    uncovered_change = False
    for f, d in list(changed_src.items()) + list(deleted_src.items()):
        oldp = d.get("old_path", f)
        old = set(d["old"])
        hit_any = any(old & set(pcov.get(t, {}).get(oldp, [])) for t in pcov)
        if d["status"] == "A" or (old and not hit_any and not (old & pimp.get(oldp, set()))):
            uncovered_change = True
    for t in universe:
        cl = cf = 0
        for f, d in list(changed_src.items()) + list(deleted_src.items()):
            oldp = d.get("old_path", f)
            lines = set(pcov.get(t, {}).get(oldp, []))
            if lines:
                cf = 1
                if set(d["old"]) & lines or (set(d["old"]) & pimp.get(oldp, set())):
                    cl = 1
        dist = static_distance(t, changed_mods, graph, known)
        name = t.rsplit("/", 1)[-1]
        rows[t] = {
            "cov_line": cl, "cov_file": cf,
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

    # ---------- uncertainty triggers (commit level)
    dyn = any(rec["static"].get(f, {}).get("dynamic") for f in changed_src)
    hidden = any(r["cov_file"] and not r["static_reach"] for r in rows.values())
    triggers = {
        "dynamic_call": dyn,
        "untested_change": uncovered_change,
        "static_runtime_conflict": hidden,
        "module_level_change": module_level_change,
    }
    return {"sha": rec["sha"], "index": rec["index"], "rows": rows, "affected": affected,
            "universe": universe, "triggers": triggers, "changed_src": sorted(changed_src) + sorted(deleted_src)}

def hist_lookup(meta):
    order = {h["sha"]: i for i, h in enumerate(meta["history"])}
    def before(sha):
        i = order.get(sha)
        return meta["history"][:i] if i is not None else meta["history"]
    return {"before": before}

# ------------------------------------------------------------------ metrics
def evaluate_set(c, sel):
    U, A = set(c["universe"]), c["affected"]
    t_all = sum(c["rows"][t]["time_true"] for t in U) or 1e-9
    t_sel = sum(c["rows"][t]["time_true"] for t in sel if t in U)
    return {
        "safe": A <= set(sel),
        "recall": (len(A & set(sel)) / len(A)) if A else 1.0,
        "precision": (len(A & set(sel)) / len(sel)) if sel else (1.0 if not A else 0.0),
        "test_red": 1 - len(set(sel) & U) / len(U),
        "time_red": 1 - t_sel / t_all,
        "has_affected": bool(A),
    }

def forced(c):
    return {t for t, r in c["rows"].items() if r["test_changed"] or r["new_test"]}

def baseline_sets(c):
    R = c["rows"]; F = forced(c)
    return {
        "RetestAll": set(c["universe"]),
        "NameMatch": F | {t for t, r in R.items() if r["name_match"]},
        "StaticImport": F | {t for t, r in R.items() if r["static_reach"]},
        "CoverageFile": F | {t for t, r in R.items() if r["cov_file"]},
        "CoverageLine": F | {t for t, r in R.items() if r["cov_line"]},
        "Hybrid(Static+CovFile)": F | {t for t, r in R.items() if r["static_reach"] or r["cov_file"]},
    }

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

def X_of(c, feats=None):
    feats = feats or FEATURES
    ts = c["universe"]
    return ts, np.array([[c["rows"][t][k] for k in feats] for t in ts], dtype=float), \
        np.array([c["rows"][t]["label"] for t in ts])

def train(commits, feats=None):
    """Logistic-regression risk model; remembers its feature list so scoring uses the same one."""
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
    feats = getattr(model, "feats_", FEATURES)
    ts, X, _ = X_of(c, feats)
    p = model.predict_proba(X)[:, 1] if model is not None else np.ones(len(ts))
    return dict(zip(ts, p))

def aggregate(evals):
    """Mean of per-commit metrics. Recall and precision are averaged only over commits that
    have at least one affected test (undefined otherwise); the other metrics over all commits."""
    if not evals:
        return {}
    out = {"n_commits": len(evals)}
    with_a = [e for e in evals if e["has_affected"]]
    for m in ("recall", "precision"):
        out[m] = float(np.mean([e[m] for e in with_a])) if with_a else None
    out["safe_rate"] = float(np.mean([e["safe"] for e in evals]))
    out["test_red"] = float(np.mean([e["test_red"] for e in evals]))
    out["time_red"] = float(np.mean([e["time_red"] for e in evals]))
    return out

def crc_threshold(calib, model, alpha):
    """Conformal risk control: largest lambda with n/(n+1) R_n(lambda) + 1/(n+1) <= alpha.
    Loss per commit = 1 if an affected (non-forced) test has p < lambda."""
    n = len(calib)
    if n == 0:
        return -1.0
    mins = []   # for each commit, smallest p among affected non-forced tests (loss=1 iff lambda > that)
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
    return best   # -1 means infeasible -> select everything

# ------------------------------------------------------------------ main
ABLATIONS = [("line coverage", ["cov_line"]), ("file coverage", ["cov_file"]),
             ("static import", ["static_inv_dist"]), ("name match", ["name_match"]),
             ("co-change", ["cochange"]), ("test changed", ["test_changed"]),
             ("all coverage", ["cov_line", "cov_file"])]
ABL_BUDGET = 0.25     # budget used for the ablation and for the CodeTwin row of the RQ1 table
MAIN_ALPHA = 0.10     # alpha used for the calibrated CodeTwin row of the RQ1 table

def split(cs):
    """Time-ordered split: first CALIB_FRAC of commits calibrate/train, the rest are test commits."""
    k = max(1, int(len(cs) * CALIB_FRAC))
    return cs[:k], cs[k:]

def main(projects):
    OUT.mkdir(exist_ok=True)
    data = {}
    summary = {}
    for p in projects:
        meta, recs = load_project(p)
        hi = hist_lookup(meta)
        cs = []
        for prev, rec in zip(recs, recs[1:]):
            if not prev["run"]["covered"] or not rec["run"]["covered"]:
                continue
            c = build_commit(meta, rec, prev, hi)
            if c:
                cs.append(c)
        data[p] = cs
        last = recs[-1]
        spec = meta["spec"]
        summary[p] = {
            "commits": len(cs),
            "test_commits": len(split(cs)[1]) if cs else 0,
            "kloc": round(sum(n for f, n in last["loc"].items() if is_src(f, spec)) / 1000, 1),
            "test_files": max((len(r["run"]["covered"]) for r in recs), default=0),
            "collected": len(recs) - 1, "with_coverage": sum(1 for r in recs[1:] if r["run"]["covered"]),
            "suite_time": round(float(np.mean([sum(r["run"]["durations"].values()) for r in recs])), 1),
            "avg_affected": round(float(np.mean([len(c["affected"]) for c in cs])) if cs else 0, 1),
            "python": meta.get("python"),
        }
        print(p, summary[p])

    single = len(projects) == 1
    # per-commit evaluations, kept so we can aggregate per project AND pooled over all projects
    E = {"baselines": defaultdict(lambda: defaultdict(list)),
         "budget": defaultdict(lambda: defaultdict(lambda: defaultdict(list))),
         "crc": defaultdict(lambda: defaultdict(lambda: defaultdict(list))),
         "ablation": defaultdict(lambda: defaultdict(list))}
    results = {"summary": summary, "features": FEATURES,
               "protocol": {"calib_frac": CALIB_FRAC, "budgets": BUDGETS, "alphas": ALPHAS,
                            "random_seeds": 20, "ablation_budget": ABL_BUDGET,
                            "training": "first half of own calibration commits" if single else "leave-one-project-out (other projects only)",
                            "calibration": "first 40% of each project's commits (not used for training)"},
               "calibration": {}, "triggers": {}, "coefficients": {}}

    for p in projects:
        calib_own, test = split(data[p])
        others = [c for q in projects if q != p for c in data[q]]
        # Conformal risk control needs calibration data that the model was NOT trained on:
        #   train  = all other projects (leave-one-project-out)
        #   calib  = first CALIB_FRAC of this project's commits
        #   test   = the remaining, later commits of this project
        # With a single project, its calibration commits are split in half (train | calibrate).
        if single:
            h = max(1, len(calib_own) // 2)
            train_set, cal_set = calib_own[:h], (calib_own[h:] or calib_own)
        else:
            train_set, cal_set = others, calib_own
        model = train(train_set)

        # ---- RQ1: unbudgeted baselines
        for c in test:
            for name, sel in baseline_sets(c).items():
                E["baselines"][p][name].append(evaluate_set(c, sel))

        # ---- RQ1: budgeted ranking (CodeTwin vs coverage-ranked vs random)
        for b in BUDGETS:
            for c in test:
                s = scores_of(model, c)
                E["budget"][p][b]["CodeTwin"].append(evaluate_set(c, budget_select(c, s, b)))
                covs = {t: 2 * c["rows"][t]["cov_line"] + c["rows"][t]["cov_file"] + 0.5 * c["rows"][t]["static_inv_dist"] for t in c["universe"]}
                E["budget"][p][b]["CoverageRanked"].append(evaluate_set(c, budget_select(c, covs, b)))
                rr = []
                for seed in range(20):
                    rnd = random.Random(seed * 7919 + c["index"])
                    rs = {t: rnd.random() for t in c["universe"]}
                    rr.append(evaluate_set(c, budget_select(c, rs, b)))
                avg = {m: float(np.mean([x[m] for x in rr])) for m in ("recall", "precision", "test_red", "time_red", "safe")}
                avg["has_affected"] = rr[0]["has_affected"]
                E["budget"][p][b]["Random"].append(avg)

        # ---- RQ2: calibrated selection, with and without abstention
        cres = {}
        for a in ALPHAS:
            lam = crc_threshold(cal_set, model, a)
            n_abst = 0
            for c in test:
                s = scores_of(model, c)
                sel = (forced(c) | {t for t in c["universe"] if s[t] >= lam}) if lam >= 0 else set(c["universe"])
                fired = any(c["triggers"].values())
                n_abst += fired
                E["crc"][p][a]["plain"].append(evaluate_set(c, sel))
                E["crc"][p][a]["abstain"].append(evaluate_set(c, set(c["universe"]) if fired else sel))
            cres[str(a)] = {"lambda": float(lam), "n_train": len(train_set), "n_calib": len(cal_set), "n_test": len(test),
                            "feasible": bool(lam >= 0),
                            "abstain_rate": n_abst / len(test) if test else None}
        results["calibration"][p] = cres

        # ---- RQ3: trigger usefulness (against the line-coverage baseline)
        unsafe = [c for c in test if not evaluate_set(c, baseline_sets(c)["CoverageLine"])["safe"]]
        safe_ = [c for c in test if evaluate_set(c, baseline_sets(c)["CoverageLine"])["safe"]]
        tk = list(test[0]["triggers"]) if test else []
        results["triggers"][p] = {
            "test_commits": len(test), "baseline_unsafe": len(unsafe), "baseline_safe": len(safe_),
            "flagged_unsafe": sum(any(c["triggers"].values()) for c in unsafe),
            "flagged_safe": sum(any(c["triggers"].values()) for c in safe_),
            "per_trigger": {k: sum(c["triggers"][k] for c in test) for k in tk},
            "per_trigger_on_unsafe": {k: sum(c["triggers"][k] for c in unsafe) for k in tk},
        }
        if model is not None:
            results["coefficients"][p] = dict(zip(model.feats_, map(float, model.coef_[0])))

        # ---- Ablation: retrain without one evidence signal at a time, same split and budget
        variants = [("Full model", FEATURES)] + [("- " + n, [f for f in FEATURES if f not in drop]) for n, drop in ABLATIONS]
        for name, feats in variants:
            m = train(train_set, feats)
            for c in test:
                E["ablation"][p][name].append(evaluate_set(c, budget_select(c, scores_of(m, c), ABL_BUDGET)))

    # ---------------- aggregate per project and pooled over all test commits ("ALL")
    keys = list(projects) + ["ALL"]
    def block(get):
        return {k: aggregate(get(k) if k != "ALL" else [e for q in projects for e in get(q)]) for k in keys}

    names_b = list(E["baselines"][projects[0]].keys()) if projects else []
    results["baselines"] = {n: block(lambda q, n=n: E["baselines"][q][n]) for n in names_b}
    results["budget"] = {str(b): {n: block(lambda q, b=b, n=n: E["budget"][q][b][n])
                                  for n in ("CodeTwin", "CoverageRanked", "Random")} for b in BUDGETS}
    results["crc"] = {}
    for a in ALPHAS:
        tot = sum(len(E["crc"][q][a]["plain"]) for q in projects)
        n_ab = sum(results["calibration"][q][str(a)]["abstain_rate"] * len(E["crc"][q][a]["plain"])
                   for q in projects if E["crc"][q][a]["plain"])
        results["crc"][str(a)] = {v: block(lambda q, a=a, v=v: E["crc"][q][a][v]) for v in ("plain", "abstain")}
        results["crc"][str(a)]["abstain_rate_ALL"] = n_ab / tot if tot else None
    abl_names = ["Full model"] + ["- " + n for n, _ in ABLATIONS]
    results["ablation"] = {n: block(lambda q, n=n: E["ablation"][q][n]) for n in abl_names}

    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=_jsonable))
    write_tex(results, projects)
    write_plot(results)
    print("wrote results/results.json, results/tables_*.tex, results/budget.pdf/.png")
    return results

def _jsonable(o):
    """numpy scalars/arrays and sets -> plain JSON types."""
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, (set, np.ndarray)):
        return list(o.tolist() if isinstance(o, np.ndarray) else sorted(o))
    raise TypeError(f"not JSON serializable: {type(o).__name__}")

# ------------------------------------------------------------------ paper outputs
def pct(x):
    return "--" if x is None else f"{100 * x:.1f}"

def num(x, d=2):
    return "--" if x is None else f"{x:.{d}f}"

def write_tex(R, projects):
    """Writes the ROWS of each paper table (paste between \\midrule and \\bottomrule)."""
    S = R["summary"]
    L = [f"{p} & {S[p]['commits']} & {S[p]['kloc']} & {S[p]['test_files']} & {S[p]['suite_time']} & {S[p]['avg_affected']} \\\\"
         for p in projects]
    mean = lambda k: round(float(np.mean([S[p][k] for p in projects])), 1)
    L += ["\\midrule", f"\\textbf{{Total/mean}} & {sum(S[p]['commits'] for p in projects)} & {mean('kloc')} & "
          f"{mean('test_files')} & {mean('suite_time')} & {mean('avg_affected')} \\\\"]
    (OUT / "tables_subjects.tex").write_text("\n".join(L) + "\n")

    label = {"RetestAll": "Retest-all", "NameMatch": "Name matching", "StaticImport": "Static import",
             "CoverageFile": "File coverage", "CoverageLine": "Line coverage", "Hybrid(Static+CovFile)": "Hybrid"}
    def row(name, a):
        return (f"{name} & {pct(a.get('test_red'))} & {pct(a.get('time_red'))} & {num(a.get('precision'))} & "
                f"{num(a.get('recall'))} & {pct(a.get('safe_rate'))} \\\\")
    L = [row(label.get(k, k), v["ALL"]) for k, v in R["baselines"].items()]
    L.append(row(f"\\textbf{{CodeTwin AI}} ({int(ABL_BUDGET * 100)}\\% budget)", R["budget"][str(ABL_BUDGET)]["CodeTwin"]["ALL"]))
    L.append(row(f"\\textbf{{CodeTwin AI}} (CRC, $\\alpha={MAIN_ALPHA}$)", R["crc"][str(MAIN_ALPHA)]["plain"]["ALL"]))
    (OUT / "tables_rq1.tex").write_text("\n".join(L) + "\n")

    L = []
    for a in ALPHAS:
        c = R["crc"][str(a)]
        L.append(f"{a:.2f} & {num(1 - c['plain']['ALL']['safe_rate'], 3)} & {num(1 - c['abstain']['ALL']['safe_rate'], 3)} & "
                 f"{pct(c['abstain_rate_ALL'])} \\\\")
    (OUT / "tables_rq2.tex").write_text("\n".join(L) + "\n")

    T = R["triggers"]
    L = [f"{p} & {T[p]['test_commits']} & {T[p]['baseline_unsafe']} & {T[p]['flagged_unsafe']} & "
         f"{T[p]['flagged_safe']}/{T[p]['baseline_safe']} \\\\" for p in projects]
    tot = lambda k: sum(T[p][k] for p in projects)
    L += ["\\midrule", f"\\textbf{{Total}} & {tot('test_commits')} & {tot('baseline_unsafe')} & {tot('flagged_unsafe')} & "
          f"{tot('flagged_safe')}/{tot('baseline_safe')} \\\\"]
    (OUT / "tables_rq3.tex").write_text("\n".join(L) + "\n")

    full = R["ablation"]["Full model"]["ALL"].get("recall")
    L = []
    for n, v in R["ablation"].items():
        a = v["ALL"]
        d = "--" if n == "Full model" or a.get("recall") is None or full is None else f"{a['recall'] - full:+.3f}"
        L.append(f"{n.replace('- ', '$-$ ')} & {num(a.get('recall'), 3)} & {pct(a.get('safe_rate'))} & {d} \\\\")
    (OUT / "tables_ablation.tex").write_text("\n".join(L) + "\n")

def write_plot(R):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: plot skipped")
        return
    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    style = {"CodeTwin": ("-o", "CodeTwin AI"), "CoverageRanked": ("--s", "Coverage-ranked"),
             "Random": (":^", "Random (20 seeds)")}
    xs = [int(b * 100) for b in BUDGETS]
    for n, (st, lab) in style.items():
        ys = [R["budget"][str(b)][n]["ALL"].get("recall") for b in BUDGETS]
        ax.plot(xs, [float("nan") if y is None else y for y in ys], st, color="black", lw=1, ms=4, label=lab)
    ax.set_xlabel("Budget (% of full-suite time)", fontsize=8)
    ax.set_ylabel("Recall of affected tests", fontsize=8)
    ax.set_xticks(xs); ax.set_ylim(0, 1.02); ax.tick_params(labelsize=7)
    ax.grid(alpha=0.3, lw=0.5); ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "budget.pdf"); fig.savefig(OUT / "budget.png", dpi=200)
    plt.close(fig)

if __name__ == "__main__":
    projs = sys.argv[1:] or sorted(p.name for p in DATA.iterdir() if (p / "meta.json").exists())
    main(projs)
