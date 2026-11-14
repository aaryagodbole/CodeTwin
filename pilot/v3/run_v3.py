"""Study v3 extensions, computed on the v2 data with the v2 protocol (same model, splits and selections).

  B  change-level residual risk: a calibrated probability that a selection misses an affected test,
     learned leave-one-project-out from change-level features, instead of the product formula that
     assumes skipped tests are independent;
  A  selective (abstention-aware) adaptive calibration: the system proceeds only when the change-level
     risk q(c) is at most tau_t and updates tau_t online so that the miss rate AMONG PROCEEDED CHANGES
     tracks the target alpha (deterministic long-run bound, no exchangeability needed);
  N  semantic no-op changes (AST-identical after removing docstrings) and annotation-only changes;
  W  weak-check evidence: changes whose changed lines are executed by tests that do not detect a
     seeded fault there ("covered but unchecked").

Usage:  CT_PILOT=<dir with analyze.py and data/> CT_REPOS=<dir with bare clones> python run_v3.py
Writes  v3/results/v3.json.
"""
import ast
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

PILOT = Path(os.environ.get("CT_PILOT", Path(__file__).resolve().parent.parent))
REPOS = Path(os.environ.get("CT_REPOS", PILOT / "repos"))
sys.path.insert(0, str(PILOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as A            # noqa: E402
from noop import classify_change  # noqa: E402

PROJECTS = ["click", "dateutil", "itsdangerous", "marshmallow", "toolz", "loguru", "pvlib", "seaborn"]
REPO_DIR = {"pvlib": "pvlib-python"}
TARGETS = [0.05, 0.10]
SEL_ALPHAS = [0.10, 0.20]
GAMMA = A.ACI_GAMMA
CHANGE_FEATS = ["log_sum_p", "max_p", "r_prod", "n_skip_file", "n_skip_line", "trig_dyn", "trig_unt", "trig_mod",
                "log_universe"]


# ------------------------------------------------------------------ change-level features and model
def change_features(c, s, sel, recal):
    skipped = [t for t in c["universe"] if t not in sel]
    ps = [recal(s[t]) for t in skipped]
    keep = 1.0
    for p in ps:
        keep *= 1.0 - p
    R = c["rows"]
    tl = c["trig_line"]
    return {
        "log_sum_p": math.log1p(sum(ps)),
        "max_p": max(ps) if ps else 0.0,
        "r_prod": 1.0 - keep,
        "n_skip_file": math.log1p(sum(R[t]["cov_file"] for t in skipped)),
        "n_skip_line": math.log1p(sum(R[t]["cov_line"] for t in skipped)),
        "trig_dyn": float(tl["dynamic_call"]), "trig_unt": float(tl["untested_change"]),
        "trig_mod": float(tl["module_level_change"]),
        "log_universe": math.log(len(c["universe"])),
    }


def vec(z):
    return [z[k] for k in CHANGE_FEATS]


def operating_points(c, s, lam_by_alpha):
    """Selections used to TRAIN the change-level model (several budgets and calibration levels)."""
    for b in A.BUDGETS:
        yield A.budget_select(c, s, b)
    for lam in lam_by_alpha.values():
        yield A.calibrated_set(c, s, lam)


class ChangeRisk:
    def __init__(self, X, y):
        self.m = LogisticRegression(C=1.0, max_iter=5000).fit(np.array(X), np.array(y))

    def __call__(self, z):
        return float(self.m.predict_proba(np.array([vec(z)]))[0, 1])


# ------------------------------------------------------------------ selective adaptive calibration
def selective_online(q_list, miss_list, alpha, gamma=GAMMA, tau0=0.5):
    """Proceed iff q <= tau_t; after the outcome is known, tau_{t+1} = tau_t + gamma*(alpha - miss_t) on
    proceeded steps only. Summing the updates gives |#miss_proceeded - alpha*#proceeded| <= (tau range)/gamma,
    so the miss rate among proceeded changes converges to alpha for any sequence of changes."""
    tau, out = tau0, []
    for q, miss in zip(q_list, miss_list):
        proceed = q <= tau
        out.append(proceed)
        if proceed:
            tau = tau + gamma * (alpha - miss)
    return out


def warm_tau(q, miss, alpha):
    """Largest tau whose empirical miss rate among calibration changes with q <= tau (finite-sample
    corrected as in conformal risk control) is at most alpha; 0 if none."""
    pts = sorted(zip(q, miss))
    best, n = 0.0, len(pts)
    for i in range(1, n + 1):
        sub = [m for _, m in pts[:i]]
        if (sum(sub) + 1) / (len(sub) + 1) <= alpha:
            best = pts[i - 1][0]
    return best


# ------------------------------------------------------------------ weak-check evidence
_SIMPLE_SKIP = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If, ast.For, ast.AsyncFor,
                ast.While, ast.With, ast.AsyncWith, ast.Try)


def _executed_lines(run, f):
    """Lines of file f executed in the new version, by any test or at import time."""
    lines = set(run["import_lines"].get(f, []))
    for cov in run["covered"].values():
        lines |= set(cov.get(f, []))
    return lines


def _line_executed(repo, sha, f, line, ex, cache):
    """A line counts as executed if it, or the first line of the simple statement containing it, was executed
    (coverage.py records multi-line statements on their first line)."""
    if line in ex:
        return True
    if (sha, f) not in cache:
        try:
            cache[(sha, f)] = ast.parse(subprocess.run(["git", f"--git-dir={repo}", "show", f"{sha}:{f}"],
                                                       capture_output=True, text=True).stdout)
        except SyntaxError:
            cache[(sha, f)] = None
    tree = cache[(sha, f)]
    return tree is not None and any(
        isinstance(n, ast.stmt) and not isinstance(n, _SIMPLE_SKIP)
        and n.lineno <= line <= (n.end_lineno or n.lineno) and n.lineno in ex for n in ast.walk(tree))


def weak_check(rec, run, repo, cache):
    """Seeded faults on changed lines that some test executed in the new version and that were run against the
    tests (the test files that executed the mutated file). A surviving such fault = covered but unchecked.
    Faults on lines that no test executed are not counted: those lines were not covered at all."""
    ran = [m for m in rec.get("mutants", []) if m.get("tests_run", 0) > 0 and m["status"] in ("killed", "survived")]
    cov = [m for m in ran if _line_executed(repo, rec["sha"], m["file"], m["line"], _executed_lines(run, m["file"]), cache)]
    surv = [m for m in cov if m["status"] == "survived"]
    return {"ran": len(cov), "survived": len(surv), "unchecked": bool(surv), "all_unchecked": bool(cov) and len(surv) == len(cov),
            "ran_incl_uncovered": len(ran), "survived_on_uncovered_lines": sum(m["status"] == "survived" for m in ran) - len(surv)}


def ev_summary(evals):
    if not evals:
        return {}
    return {"n": len(evals), "miss": 1 - float(np.mean([e["safe"] for e in evals])),
            "time_red": float(np.mean([e["time_red"] for e in evals]))}


# ------------------------------------------------------------------ main
def main():
    data, kind, recs = {}, {}, {}
    for p in PROJECTS:
        meta, cs, _, _ = A.load_changes(p)
        data[p], kind[p] = cs, meta.get("mode", "history")
        _, rr = A.load_project(p)
        recs[p] = ({r["sha"]: r for r in rr}, meta)
    hist_p = [p for p in PROJECTS if kind[p] == "history"]
    pair_p = [p for p in PROJECTS if kind[p] == "pairs"]

    # test-level models (identical to analyze.main) and per-project calibration artefacts
    models, recals, lams = {}, {}, {}
    for p in hist_p + pair_p:
        calib, _ = A.split(data[p])
        models[p] = A.train([c for q in hist_p if q != p for c in data[q]])
        recals[p] = A.fit_recalibration(calib, models[p])
        lams[p] = {a: A.crc_threshold(calib, models[p], a) for a in A.ALPHAS}

    # change-level training rows per history project (all its changes, several operating points)
    rows = {}
    for p in hist_p:
        X, y = [], []
        for c in data[p]:
            s = A.scores_of(models[p], c)
            for sel in operating_points(c, s, lams[p]):
                X.append(vec(change_features(c, s, sel, recals[p])))
                y.append(0 if c["affected"] <= sel else 1)
        rows[p] = (X, y)

    allX = [x for q in hist_p for x in rows[q][0]]; ally = [v for q in hist_p for v in rows[q][1]]
    prior = ChangeRisk(allX, ally).m
    prior_out = {"features": CHANGE_FEATS, "coef": [float(v) for v in prior.coef_[0]],
                 "intercept": float(prior.intercept_[0]), "n_rows": len(ally), "positives": int(sum(ally))}
    R = {"prior_change_model": prior_out, "protocol": {"change_features": CHANGE_FEATS, "targets": TARGETS, "selection_alphas": SEL_ALPHAS,
                      "gamma": GAMMA, "tau0": 0.5,
                      "training": "change-level model leave-one-project-out over the history projects; its training rows come from test-level models that also exclude the evaluated project; NameRTS projects use all history projects"},
         "risk": {}, "selective": {}, "noop": {}, "weak": {}}
    RISK = defaultdict(list)                   # mode -> [(prod, change, observed)]
    SELE = defaultdict(list)                   # key -> per-change dicts (pooled later by group)

    # Rows used to evaluate q(c) on a history project p must not come from test-level models that saw p:
    # for each training project q, retrain the test-level model without both q and p.
    rows_excl = {}

    def rows_without(q, p):
        if (q, p) not in rows_excl:
            m = A.train([c for r in hist_p if r not in (q, p) for c in data[r]])
            calib_q, _ = A.split(data[q])
            rc = A.fit_recalibration(calib_q, m)
            lm = {a: A.crc_threshold(calib_q, m, a) for a in A.ALPHAS}
            X, y = [], []
            for c in data[q]:
                s = A.scores_of(m, c)
                for sel in operating_points(c, s, lm):
                    X.append(vec(change_features(c, s, sel, rc)))
                    y.append(0 if c["affected"] <= sel else 1)
            rows_excl[(q, p)] = (X, y)
        return rows_excl[(q, p)]

    for p in hist_p + pair_p:
        others = [q for q in hist_p if q != p]
        src = [rows_without(q, p) for q in others] if p in hist_p else [rows[q] for q in others]
        X = [x for r in src for x in r[0]]
        y = [v for r in src for v in r[1]]
        cr = ChangeRisk(X, y)
        calib, test = A.split(data[p])
        k = len(calib)
        model, recal = models[p], recals[p]
        grp = "HIST" if p in hist_p else "NRTS"

        # B: compare r_prod with the change-level risk on the same selections as the paper
        aci10 = A.crc_online(data[p], k, model, A.MAIN_ALPHA, window=k, gamma=A.ACI_GAMMA)
        for c, (sel_aci, _) in zip(test, aci10):
            s = A.scores_of(model, c)
            for mode, sel in (("budget25", A.budget_select(c, s, 0.25)), ("aci10", sel_aci),
                              ("linecov", A.baseline_sets(c)["Line coverage"])):
                z = change_features(c, s, sel, recal)
                RISK[f"{mode}:{grp}"].append((z["r_prod"], cr(z), 0.0 if c["affected"] <= sel else 1.0))

        # A: selective adaptive calibration on top of ACI selections, file-coverage fallback
        for a_sel in SEL_ALPHAS:
            sels = A.crc_online(data[p], k, model, a_sel, window=k, gamma=A.ACI_GAMMA)
            qs, misses, info = [], [], []
            for c, (sel, _) in zip(test, sels):
                s = A.scores_of(model, c)
                z = change_features(c, s, sel, recal)
                qs.append(cr(z)); misses.append(0.0 if c["affected"] <= sel else 1.0)
                info.append((c, sel, z))
            # calibration changes: static selection at a_sel, their change-level risk and outcome (for a warm start)
            lam_c = A.crc_threshold(calib, model, a_sel)
            cq, cm = [], []
            for c in calib:
                s = A.scores_of(model, c)
                sel = A.calibrated_set(c, s, lam_c)
                cq.append(cr(change_features(c, s, sel, recal))); cm.append(0.0 if c["affected"] <= sel else 1.0)
            for target in TARGETS:
                if target >= a_sel:
                    continue
                tau_w = warm_tau(cq, cm, target)
                rules = {"rprod": [z["r_prod"] <= target for (_, _, z) in info],
                         "qrule": [q <= target for q in qs],
                         "selective": selective_online(qs, misses, target),
                         "selective_warm": selective_online(qs, misses, target, tau0=tau_w),
                         "selective_warm_g05": selective_online(qs, misses, target, gamma=0.05, tau0=tau_w)}
                for rule, proceed in rules.items():
                    for (c, sel, z), go, miss in zip(info, proceed, misses):
                        fb = A.baseline_sets(c)["File coverage"] | sel
                        ev = A.evaluate_set(c, sel if go else fb)
                        SELE[f"{rule}:sel{a_sel}:t{target}:{grp}"].append(
                            {"project": p, "proceed": bool(go), "miss_if_proceed": miss, "safe": ev["safe"],
                             "time_red": ev["time_red"], "mut_n": ev["mut_n"], "mut_det": ev["mut_det"]})

        # N and W on every test change
        bysha, meta = recs[p]
        spec = meta["spec"]
        repo = str(REPOS / REPO_DIR.get(p, p))
        snaps_w, wcache = A.Snaps(p), {}
        for c in test:
            rec = bysha[c["sha"]]
            kind_, files = classify_change(repo, rec["parent"], rec["sha"], rec["diff"], lambda f: A.is_src(f, spec))
            fc = A.baseline_sets(c)["File coverage"]
            lc = A.baseline_sets(c)["Line coverage"]
            R["noop"].setdefault(p, []).append({"sha": c["sha"][:10], "kind": kind_, "files": files,
                                                "affected": len(c["affected"]), "killed_mutants": len(c["mutants"]),
                                                "forced": len(A.forced(c)),
                                                "time_skippable": A.evaluate_set(c, A.forced(c))["time_red"],
                                                "filecov_time_red": A.evaluate_set(c, fc)["time_red"]})
            wc = weak_check(rec, snaps_w.get(rec["sha"])["run"], repo, wcache)
            wc.update({"sha": c["sha"][:10], "linecov_safe": A.evaluate_set(c, lc)["safe"]})
            R["weak"].setdefault(p, []).append(wc)

    # ------------------------------------------------------------------ test outcome flips for no-op changes
    for p in PROJECTS:
        snaps = A.Snaps(p)
        bysha, _ = recs[p]
        for row in R["noop"].get(p, []):
            if row["kind"] not in ("noop", "annotation"):
                continue
            full = next(s for s in bysha if s.startswith(row["sha"]))
            rec = bysha[full]
            prev, cur = snaps.get(rec["parent"]), snaps.get(rec["sha"])
            po, co = prev["run"].get("outcomes", {}), cur["run"].get("outcomes", {})
            row["flips"] = sorted(t for t in co if po.get(t) is True and co[t] is False)

    # ------------------------------------------------------------------ pooled summaries
    out = {}
    for key, pts in RISK.items():
        pr = np.array([x[0] for x in pts]); cq = np.array([x[1] for x in pts]); ob = np.array([x[2] for x in pts])

        def stats(pred):
            bins = np.clip((pred * 5).astype(int), 0, 4)
            ece = sum(abs(pred[bins == b].mean() - ob[bins == b].mean()) * (bins == b).sum() for b in range(5) if (bins == b).any()) / len(ob)
            return {"mean": float(pred.mean()), "brier": float(np.mean((pred - ob) ** 2)), "ece5": float(ece)}
        out[key] = {"n": len(ob), "observed": float(ob.mean()), "brier_constant": float(np.mean((ob.mean() - ob) ** 2)),
                    "product": stats(pr), "change_level": stats(cq)}
    R["risk"] = out

    sel_out = {}
    for key, rows_ in SELE.items():
        pro = [r for r in rows_ if r["proceed"]]
        sel_out[key] = {"n": len(rows_), "abstain_rate": 1 - len(pro) / len(rows_),
                        "miss_among_proceeded": float(np.mean([r["miss_if_proceed"] for r in pro])) if pro else None,
                        "n_proceeded": len(pro),
                        "overall_miss": 1 - float(np.mean([r["safe"] for r in rows_])),
                        "time_red": float(np.mean([r["time_red"] for r in rows_])),
                        "mut_rate": (sum(r["mut_det"] for r in rows_) / max(1, sum(r["mut_n"] for r in rows_))),
                        "per_project_miss_proceeded": {q: float(np.mean([r["miss_if_proceed"] for r in pro if r["project"] == q]))
                                                       for q in sorted({r["project"] for r in pro})}}
    R["selective"] = sel_out

    nk = defaultdict(lambda: defaultdict(int)); nflip = defaultdict(int); nsave = defaultdict(list)
    for p, lst in R["noop"].items():
        g = "HIST" if p in hist_p else "NRTS"
        for r in lst:
            nk[g][r["kind"]] += 1
            if r["kind"] == "noop":
                nflip[g] += bool(r.get("flips"))
                nsave[g].append(r["time_skippable"] - r["filecov_time_red"])
    R["noop_summary"] = {g: {"kinds": dict(v), "noop_with_flip": nflip[g],
                             "extra_time_saved_vs_filecov_on_noop": float(np.mean(nsave[g])) if nsave[g] else None}
                         for g, v in nk.items()}
    wsum = {}
    for g, ps in (("HIST", hist_p), ("NRTS", pair_p)):
        lst = [r for q in ps for r in R["weak"].get(q, [])]
        withm = [r for r in lst if r["ran"]]
        safe_ = [r for r in withm if r["linecov_safe"]]
        wsum[g] = {"test_changes": len(lst), "with_executed_mutants": len(withm),
                   "unchecked": sum(r["unchecked"] for r in withm), "all_unchecked": sum(r["all_unchecked"] for r in withm),
                   "linecov_safe_with_mutants": len(safe_), "linecov_safe_but_unchecked": sum(r["unchecked"] for r in safe_),
                   "mutants_ran": sum(r["ran"] for r in withm), "mutants_survived": sum(r["survived"] for r in withm),
                   "survived_on_uncovered_lines_excluded": sum(r["survived_on_uncovered_lines"] for r in lst)}
    R["weak_summary"] = wsum

    outdir = Path(__file__).resolve().parent / "results"
    outdir.mkdir(exist_ok=True)
    (outdir / "v3.json").write_text(json.dumps(R, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))
    print(json.dumps({"risk": R["risk"], "selective": R["selective"], "noop": R["noop_summary"], "weak": R["weak_summary"]}, indent=1))


if __name__ == "__main__":
    main()
