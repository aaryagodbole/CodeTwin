"""Study v4: the change-level risk model q(c) and the abstention rules of study v3 (pilot/v3/run_v3.py,
parts B and A) on the per-language Multi-SWE-bench data. Parts N (semantic no-ops) and W (weak checks) need
the Python AST and seeded faults and are not repeated here.

Same protocol as v3: test-level models leave-one-project-out, change-level model leave-one-project-out with
training rows from test-level models that also exclude the evaluated project; languages with fewer than
MIN_CHANGES changes ("pairs" mode) use all history languages and are reported separately.

Usage: python run_v4_change.py        (after analyze_v4.py --per-language; writes results_by_language/v4_change.json)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_v4 as V  # noqa: E402

sys.modules["analyze"] = V.an
sys.path.insert(0, str(HERE.parent / "v3"))
import run_v3 as R3  # noqa: E402

A = V.an


def main() -> None:
    projects = sorted(p.name for p in V.DATA.iterdir() if p.name.startswith("lang_"))
    V.SMALL.update(p for p in projects if len(list((V.DATA / p / "commits").glob("*.json"))) < V.MIN_CHANGES)
    data, kind = {}, {}
    for p in projects:
        meta, cs, _, _ = A.load_changes(p)
        data[p], kind[p] = cs, meta.get("mode", "history")
    hist_p = [p for p in projects if kind[p] == "history" and data[p]]
    pair_p = [p for p in projects if kind[p] == "pairs" and data[p]]

    models, recals, lams = {}, {}, {}
    for p in hist_p + pair_p:
        calib, _ = A.split(data[p])
        models[p] = A.train([c for q in hist_p if q != p for c in data[q]])
        recals[p] = A.fit_recalibration(calib, models[p])
        lams[p] = {a: A.crc_threshold(calib, models[p], a) for a in A.ALPHAS}

    def change_rows(q, m, rc, lm):
        X, y = [], []
        for c in data[q]:
            s = A.scores_of(m, c)
            for sel in R3.operating_points(c, s, lm):
                X.append(R3.vec(R3.change_features(c, s, sel, rc)))
                y.append(0 if c["affected"] <= sel else 1)
        return X, y

    rows = {p: change_rows(p, models[p], recals[p], lams[p]) for p in hist_p}
    rows_excl: dict = {}

    def rows_without(q, p):
        if (q, p) not in rows_excl:
            m = A.train([c for r in hist_p if r not in (q, p) for c in data[r]])
            calib_q, _ = A.split(data[q])
            rc = A.fit_recalibration(calib_q, m)
            lm = {a: A.crc_threshold(calib_q, m, a) for a in A.ALPHAS}
            rows_excl[(q, p)] = change_rows(q, m, rc, lm)
        return rows_excl[(q, p)]

    RISK: dict = defaultdict(list)
    SELE: dict = defaultdict(list)
    for p in hist_p + pair_p:
        others = [q for q in hist_p if q != p]
        src = [rows_without(q, p) for q in others] if p in hist_p else [rows[q] for q in others]
        X = [x for r in src for x in r[0]]
        y = [v for r in src for v in r[1]]
        cr = R3.ChangeRisk(X, y)
        calib, test = A.split(data[p])
        k, model, recal = len(calib), models[p], recals[p]
        grp = "HIST" if p in hist_p else "NRTS"
        aci10 = A.crc_online(data[p], k, model, A.MAIN_ALPHA, window=k, gamma=A.ACI_GAMMA)
        for c, (sel_aci, _) in zip(test, aci10):
            s = A.scores_of(model, c)
            for mode, sel in (("budget25", A.budget_select(c, s, 0.25)), ("aci10", sel_aci),
                              ("linecov", A.baseline_sets(c)["Line coverage"])):
                z = R3.change_features(c, s, sel, recal)
                obs = 0.0 if c["affected"] <= sel else 1.0
                RISK[f"{mode}:{grp}"].append((z["r_prod"], cr(z), obs))
                RISK[f"{mode}:{p}"].append((z["r_prod"], cr(z), obs))
        for a_sel in R3.SEL_ALPHAS:
            sels = A.crc_online(data[p], k, model, a_sel, window=k, gamma=A.ACI_GAMMA)
            qs, misses, info = [], [], []
            for c, (sel, _) in zip(test, sels):
                s = A.scores_of(model, c)
                z = R3.change_features(c, s, sel, recal)
                qs.append(cr(z))
                misses.append(0.0 if c["affected"] <= sel else 1.0)
                info.append((c, sel, z))
            for target in R3.TARGETS:
                if target >= a_sel:
                    continue
                rules = {"rprod": [z["r_prod"] <= target for (_, _, z) in info],
                         "qrule": [q <= target for q in qs],
                         "selective": R3.selective_online(qs, misses, target)}
                for rule, proceed in rules.items():
                    for (c, sel, z), go, miss in zip(info, proceed, misses):
                        fb = A.baseline_sets(c)["File coverage"] | sel
                        ev = A.evaluate_set(c, sel if go else fb)
                        rec = {"project": p, "proceed": bool(go), "miss_if_proceed": miss, "safe": ev["safe"],
                               "time_red": ev["time_red"]}
                        SELE[f"{rule}:sel{a_sel}:t{target}:{grp}"].append(rec)
                        SELE[f"{rule}:sel{a_sel}:t{target}:{p}"].append(rec)

    out: dict = {"protocol": {"projects": hist_p + pair_p, "history": hist_p, "separate": pair_p,
                              "change_features": R3.CHANGE_FEATS, "targets": R3.TARGETS,
                              "selection_alphas": R3.SEL_ALPHAS}, "risk": {}, "selective": {}}
    for key, pts in RISK.items():
        pr = np.array([x[0] for x in pts]); cq = np.array([x[1] for x in pts]); ob = np.array([x[2] for x in pts])
        out["risk"][key] = {"n": len(ob), "observed": float(ob.mean()),
                            "product_mean": float(pr.mean()), "change_level_mean": float(cq.mean()),
                            "product_brier": float(np.mean((pr - ob) ** 2)),
                            "change_level_brier": float(np.mean((cq - ob) ** 2)),
                            "brier_constant": float(np.mean((ob.mean() - ob) ** 2))}
    for key, rs in SELE.items():
        pro = [r for r in rs if r["proceed"]]
        out["selective"][key] = {"n": len(rs), "abstain_rate": 1 - len(pro) / len(rs), "n_proceeded": len(pro),
                                 "miss_among_proceeded": float(np.mean([r["miss_if_proceed"] for r in pro])) if pro else None,
                                 "overall_miss": 1 - float(np.mean([r["safe"] for r in rs])),
                                 "time_red": float(np.mean([r["time_red"] for r in rs]))}
    dst = HERE / "results_by_language" / "v4_change.json"
    dst.write_text(json.dumps(out, indent=1))
    print("wrote", dst)


if __name__ == "__main__":
    main()
