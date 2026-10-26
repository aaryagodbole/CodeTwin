#!/usr/bin/env python3
"""
CodeTwin AI -- statistics and failure cases for the paper.

Re-uses analyze.py (same data, same split, same models) and adds:
  * 95% bootstrap confidence intervals (10,000 resamples over test commits)
  * paired Wilcoxon signed-rank tests on per-commit recall / time reduction
  * exact McNemar tests on per-commit safety (all affected tests selected or not)
  * concrete failure cases (missed tests, unnecessary abstentions)
Writes results/stats.json and results/stats.md
Usage: python stats.py            (after collect.py; analyze.py not required)
"""
import json, random
from collections import defaultdict

import numpy as np
from scipy.stats import wilcoxon, binomtest

import analyze as A

B_RESAMPLES = 10_000
rng = np.random.default_rng(0)


def boot_ci(x):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return None
    idx = rng.integers(0, len(x), size=(B_RESAMPLES, len(x)))
    means = x[idx].mean(axis=1)
    return [float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def wilcox(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    if np.all(d == 0):
        return {"n": len(d), "nonzero": 0, "p": 1.0, "mean_diff": 0.0}
    r = wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
    return {"n": len(d), "nonzero": int(np.sum(d != 0)), "p": float(r.pvalue), "mean_diff": float(d.mean())}


def mcnemar(a_safe, b_safe):
    """exact McNemar: discordant pairs b01 (a safe, b not) vs b10 (b safe, a not)."""
    b01 = sum(1 for x, y in zip(a_safe, b_safe) if x and not y)
    b10 = sum(1 for x, y in zip(a_safe, b_safe) if y and not x)
    p = binomtest(b01, b01 + b10, 0.5).pvalue if b01 + b10 else 1.0
    return {"a_only_safe": b01, "b_only_safe": b10, "p": float(p)}


def main():
    projects = sorted(p.name for p in A.DATA.iterdir() if (p / "meta.json").exists())
    data = {}
    for p in projects:
        meta, recs = A.load_project(p)
        hi = A.hist_lookup(meta)
        cs = []
        for prev, rec in zip(recs, recs[1:]):
            if prev["run"]["covered"] and rec["run"]["covered"]:
                c = A.build_commit(meta, rec, prev, hi)
                if c:
                    c["project"] = p
                    c["subject"] = rec.get("subject", "")
                    c["date"] = rec.get("date", "")
                    cs.append(c)
        data[p] = cs

    single = len(projects) == 1
    ev = defaultdict(list)          # technique -> list of per-commit evals (same commit order)
    failures, needless = [], []
    for p in projects:
        calib_own, test = A.split(data[p])
        others = [c for q in projects if q != p for c in data[q]]
        if single:
            h = max(1, len(calib_own) // 2)
            train_set, cal_set = calib_own[:h], (calib_own[h:] or calib_own)
        else:
            train_set, cal_set = others, calib_own
        model = A.train(train_set)
        lam = {a: A.crc_threshold(cal_set, model, a) for a in A.ALPHAS}
        for c in test:
            s = A.scores_of(model, c)
            for name, sel in A.baseline_sets(c).items():
                ev[name].append(A.evaluate_set(c, sel))
            covs = {t: 2 * c["rows"][t]["cov_line"] + c["rows"][t]["cov_file"] + 0.5 * c["rows"][t]["static_inv_dist"] for t in c["universe"]}
            for b in A.BUDGETS:
                ev[f"CodeTwin@{b}"].append(A.evaluate_set(c, A.budget_select(c, s, b)))
                ev[f"CoverageRanked@{b}"].append(A.evaluate_set(c, A.budget_select(c, covs, b)))
                rr = []
                for seed in range(20):
                    rnd = random.Random(seed * 7919 + c["index"])
                    rr.append(A.evaluate_set(c, A.budget_select(c, {t: rnd.random() for t in c["universe"]}, b)))
                ev[f"Random@{b}"].append({"recall": float(np.mean([x["recall"] for x in rr])),
                                          "safe": float(np.mean([x["safe"] for x in rr])),
                                          "time_red": float(np.mean([x["time_red"] for x in rr])),
                                          "has_affected": rr[0]["has_affected"]})
            fired = [k for k, v in c["triggers"].items() if v]
            for a in A.ALPHAS:
                l = lam[a]
                sel = (A.forced(c) | {t for t in c["universe"] if s[t] >= l}) if l >= 0 else set(c["universe"])
                e = A.evaluate_set(c, sel)
                ev[f"CRC@{a}"].append(e)
                ev[f"CRC+abstain@{a}"].append(A.evaluate_set(c, set(c["universe"]) if fired else sel))
                if a == 0.10 and l >= 0:
                    if not e["safe"]:
                        missed = sorted(c["affected"] - sel)
                        failures.append({
                            "project": p, "sha": c["sha"][:10], "date": c["date"][:10], "subject": c["subject"][:90],
                            "changed": c["changed_src"], "affected": len(c["affected"]), "selected": len(sel),
                            "missed": [{"test": t, "p": round(float(s[t]), 3),
                                        **{k: c["rows"][t][k] for k in ("cov_line", "cov_file", "static_inv_dist", "name_match")}}
                                       for t in missed],
                            "lambda": round(float(l), 3), "triggers_fired": fired})
                    elif fired:
                        needless.append({"project": p, "sha": c["sha"][:10], "subject": c["subject"][:90],
                                         "changed": c["changed_src"], "triggers_fired": fired,
                                         "time_saved_lost": round(e["time_red"], 3)})

    with_a = lambda name, m: [e[m] for e in ev[name] if e["has_affected"]]
    allc = lambda name, m: [float(e[m]) for e in ev[name]]
    out = {"n_test_commits": len(ev["RetestAll"]),
           "n_with_affected": sum(e["has_affected"] for e in ev["RetestAll"]),
           "ci": {}, "tests": {}, "failures_crc_0.10": failures,
           "needless_abstentions_crc_0.10": needless[:10], "n_needless_abstentions_crc_0.10": len(needless)}

    for name in ["NameMatch", "StaticImport", "CoverageFile", "CoverageLine", "Hybrid(Static+CovFile)",
                 "CRC@0.1", "CRC@0.2", "CRC+abstain@0.1"]:
        out["ci"][name] = {"recall": boot_ci(with_a(name, "recall")), "safe": boot_ci(allc(name, "safe")),
                           "time_red": boot_ci(allc(name, "time_red"))}
    for b in A.BUDGETS:
        for t in ("CodeTwin", "CoverageRanked", "Random"):
            out["ci"][f"{t}@{b}"] = {"recall": boot_ci(with_a(f"{t}@{b}", "recall"))}
        out["tests"][f"recall CodeTwin vs CoverageRanked @{b}"] = wilcox(with_a(f"CodeTwin@{b}", "recall"), with_a(f"CoverageRanked@{b}", "recall"))
        out["tests"][f"recall CodeTwin vs Random @{b}"] = wilcox(with_a(f"CodeTwin@{b}", "recall"), with_a(f"Random@{b}", "recall"))
    for base in ("CoverageLine", "CoverageFile"):
        out["tests"][f"safe CRC@0.1 vs {base} (McNemar)"] = mcnemar(allc("CRC@0.1", "safe"), allc(base, "safe"))
        out["tests"][f"time_red CRC@0.1 vs {base}"] = wilcox(allc("CRC@0.1", "time_red"), allc(base, "time_red"))

    A.OUT.mkdir(exist_ok=True)
    (A.OUT / "stats.json").write_text(json.dumps(out, indent=1))
    lines = [f"# Statistics ({out['n_test_commits']} test commits, {out['n_with_affected']} with affected tests)", "",
             "## 95% bootstrap CIs (mean [low, high])"]
    for k, v in out["ci"].items():
        lines.append(f"- {k}: " + "; ".join(f"{m} {x[0]:.3f} [{x[1]:.3f}, {x[2]:.3f}]" for m, x in v.items() if x))
    lines += ["", "## Paired tests"]
    for k, v in out["tests"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", f"## CRC alpha=0.10 misses ({len(failures)})"] + [f"- {json.dumps(f)}" for f in failures]
    lines += ["", f"## Unnecessary abstentions at alpha=0.10: {len(needless)} (first 10)"] + [f"- {json.dumps(n)}" for n in needless[:10]]
    (A.OUT / "stats.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
