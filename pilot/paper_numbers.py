#!/usr/bin/env python3
"""
CodeTwin AI -- fills the paper from the results.

Reads results/results.json and a LaTeX template whose placeholders look like <<KEY>>, and writes the
paper with every number about our study taken from the results (nothing typed by hand).
Usage: python paper_numbers.py ../paper/main.template.tex ../paper/main.tex
       python paper_numbers.py --list            (print every key and its value)
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results" / "results.json").read_text())
A, S = R["agg"], R["summary"]
HIST = [p for p in S if S[p]["mode"] == "history" and S[p]["changes"]]
NRTS = [p for p in S if S[p]["mode"] == "pairs" and S[p]["changes"]]
MAIN = str(R["protocol"]["main_alpha"])
ALPHAS = R["protocol"]["alphas"]

def m(x):                       # mean of a bootstrap triple or a plain number
    return x[0] if isinstance(x, list) else x

def pc(x, d=1):
    return "--" if x is None else f"{100 * m(x):.{d}f}"

def f(x, d=2):
    return "--" if x is None else f"{m(x):.{d}f}"

def ci(x, d=1):
    return f"{100 * x[1]:.{d}f}--{100 * x[2]:.{d}f}" if isinstance(x, list) else "--"

def miss(x, d=1):               # observed miss rate in % from a safe-rate triple
    return "--" if x is None else f"{100 * (1 - m(x)):.{d}f}"

K = {}
def put(k, v):
    K[k] = str(v)

# ------------------------------------------------------------ subjects
put("N_HIST_PROJ", len(HIST)); put("N_NRTS_PROJ", len(NRTS)); put("N_PROJ", len(HIST) + len(NRTS))
put("N_HIST_CHANGES", sum(S[p]["changes"] for p in HIST))
put("N_HIST_TEST", sum(S[p]["test"] for p in HIST)); put("N_HIST_CALIB", sum(S[p]["calib"] for p in HIST))
put("N_NRTS_CHANGES", sum(S[p]["changes"] for p in NRTS)); put("N_NRTS_TEST", sum(S[p]["test"] for p in NRTS))
put("N_CHANGES", sum(S[p]["changes"] for p in HIST + NRTS))
put("N_COLLECTED", sum(S[p]["changes_collected"] for p in HIST + NRTS))
put("N_MUTANTS", sum(S[p]["mutants_killed"] for p in HIST + NRTS))
put("N_TEST_MUTANTS_HIST", A[f"base:Retest-all"]["HIST"]["mut_total"])
put("N_TEST_MUTANTS_NRTS", A[f"base:Retest-all"].get("NRTS", {}).get("mut_total", 0))
put("CALIB_MIN", min(S[p]["calib"] for p in HIST)); put("CALIB_MAX", max(S[p]["calib"] for p in HIST))
put("KLOC_MIN", min(S[p]["kloc"] for p in HIST + NRTS)); put("KLOC_MAX", max(S[p]["kloc"] for p in HIST + NRTS))
put("NO_COV", sum(S[p]["skipped"].get("no coverage", 0) + S[p]["skipped"].get("missing snapshot", 0) for p in HIST + NRTS))
rows = []
for p in HIST + NRTS:
    s = S[p]
    tag = "" if p in HIST else "$^\\ast$"
    rows.append(f"{p}{tag} & {s['changes']} ({s['calib']}/{s['test']}) & {s['kloc']} & {s['test_files']:.0f} & "
                f"{s['suite_time']:.1f} & {s['avg_affected']:.1f} & {s['mutants_killed']} & {s['first'][:4]}--{s['last'][:4]} \\\\")
    if p == HIST[-1] and NRTS:
        rows.append("\\midrule")
put("TAB_SUBJECTS", "\n".join(rows))

# ------------------------------------------------------------ RQ1 table (history projects)
LAB = {"Retest-all": "Retest-all", "Name matching": "Name matching", "Static import": "Static import",
       "File coverage": "File coverage", "Function coverage": "Function coverage", "Line coverage": "Line coverage",
       "Hybrid": "Hybrid (static $\\cup$ file cov.)"}
def row(label, a, mut=True):
    r = f"{label} & {pc(a['test_red'])} & {pc(a['time_red'])} & {f(a['precision'])} & {f(a['recall'])} & {pc(a['safe_rate'])}"
    if mut:
        r += f" & {pc(a['mut_rate'])}"
    return r + " \\\\"
rq1 = [row(LAB[k], A[f"base:{k}"]["HIST"]) for k in LAB]
rq1.append("\\midrule")
rq1.append(row("CodeTwin, budget 25\\%", A["budget:0.25:CodeTwin"]["HIST"]))
rq1.append(row(f"CodeTwin, ACI $\\alpha$={MAIN}", A[f"aci:{MAIN}:plain"]["HIST"]))
rq1.append(row(f"\\quad + risk abstention", A[f"aci:{MAIN}:abstain-risk:filecov"]["HIST"]))
put("TAB_RQ1", "\n".join(rq1))
for k, key in (("Line coverage", "LINE"), ("File coverage", "FILE"), ("Function coverage", "FUNC"), ("Static import", "STATIC"),
               ("Name matching", "NAME"), ("Hybrid", "HYB"), ("Retest-all", "ALL")):
    a = A[f"base:{k}"]["HIST"]
    put(f"{key}_SAFE", pc(a["safe_rate"])); put(f"{key}_TIME", pc(a["time_red"])); put(f"{key}_RECALL", f(a["recall"]))
    put(f"{key}_PREC", f(a["precision"])); put(f"{key}_MUT", pc(a["mut_rate"])); put(f"{key}_SAFE_CI", ci(a["safe_rate"]))
    put(f"{key}_MISS", miss(a["safe_rate"])); put(f"{key}_FSAFE", pc(a["fault_safe"]))
    put(f"{key}_UNSAFE_N", round((1 - m(a["safe_rate"])) * a["n"]))

for b in R["protocol"]["budgets"]:
    bb = str(b); bk = str(int(b * 100))
    for n, key in (("CodeTwin", "CT"), ("Coverage-ranked", "CR"), ("Random", "RND")):
        a = A[f"budget:{bb}:{n}"]["HIST"]
        put(f"B{bk}_{key}_RECALL", f(a["recall"], 3)); put(f"B{bk}_{key}_SAFE", pc(a["safe_rate"]))
        put(f"B{bk}_{key}_MUT", pc(a["mut_rate"]))
    put(f"B{bk}_CT_TIME", pc(A[f"budget:{bb}:CodeTwin"]["HIST"]["time_red"]))
T = R["tests"]
def pv(p):
    return "<10^{-4}" if p < 1e-4 else (f"<{0.001}" if p < 0.001 else f"={p:.3f}" if p < 0.1 else f"={p:.2f}")
for b in R["protocol"]["budgets"]:
    bk = str(int(b * 100))
    put(f"P_B{bk}_CR", pv(T[f"recall@{b}: CodeTwin vs Coverage-ranked"]["p"]))
    put(f"P_B{bk}_RND", pv(T[f"recall@{b}: CodeTwin vs Random"]["p"]))
    put(f"D_B{bk}_CR", f"{T[f'recall@{b}: CodeTwin vs Coverage-ranked']['mean_diff']:+.3f}")
    put(f"D_B{bk}_RND", f"{T[f'recall@{b}: CodeTwin vs Random']['mean_diff']:+.3f}")

# ------------------------------------------------------------ RQ2 calibration
rq2 = []
for a in ALPHAS:
    sa = str(a)
    cells = [f"{a:.2f}"]
    for vn in ("crc", "win", "aci"):
        x = A[f"{vn}:{sa}:plain"]["HIST"]
        cells.append(f"{miss(x['safe_rate'])} & {pc(x['time_red'])}")
    rq2.append(" & ".join(cells) + " \\\\")
    for vn in ("crc", "win", "aci"):
        x = A[f"{vn}:{sa}:plain"]["HIST"]
        ak = str(int(round(a * 100)))
        put(f"{vn.upper()}{ak}_MISS", miss(x["safe_rate"])); put(f"{vn.upper()}{ak}_TIME", pc(x["time_red"]))
        put(f"{vn.upper()}{ak}_MUT", pc(x["mut_rate"])); put(f"{vn.upper()}{ak}_RECALL", f(x["recall"], 3))
        put(f"{vn.upper()}{ak}_MISS_CI", ci([1 - x["safe_rate"][0], 1 - x["safe_rate"][2], 1 - x["safe_rate"][1]]))
put("TAB_RQ2", "\n".join(rq2))
put("ACI_GAMMA", "0.02")
# feasibility of static calibration per project
inf = {a: [p for p in HIST if not R["calibration"][p][str(a)]["feasible"]] for a in ALPHAS}
put("INFEASIBLE_1", ", ".join(inf[0.01]) if inf[0.01] else "none")
put("N_INFEASIBLE_1", len(inf[0.01])); put("N_INFEASIBLE_5", len(inf[0.05]))
# per-project static vs aci at main alpha
pp = []
for p in HIST:
    c, w, ac = (A[f"{vn}:{MAIN}:plain"][p] for vn in ("crc", "win", "aci"))
    pp.append(f"{p} & {miss(c['safe_rate'])} & {miss(w['safe_rate'])} & {miss(ac['safe_rate'])} & {pc(ac['time_red'])} \\\\")
put("TAB_RQ2_PROJ", "\n".join(pp))
worst = max(HIST, key=lambda p: 1 - A[f"crc:{MAIN}:plain"][p]["safe_rate"])
put("WORST_STATIC_PROJ", worst); put("WORST_STATIC_MISS", miss(A[f"crc:{MAIN}:plain"][worst]["safe_rate"]))
put("WORST_STATIC_LAMBDA", f"{R['calibration'][worst][MAIN]['lambda']:.3f}")
# residual risk reliability
rr = R["residual_risk"]
for mode, key in (("budget25", "RB"), ("aci10", "RC"), ("crc10", "RS"), ("linecov", "RL")):
    x = rr.get(f"{mode}:HIST")
    if x:
        put(f"{key}_PRED", pc(x["mean_predicted"])); put(f"{key}_OBS", pc(x["observed_miss_rate"]))
        put(f"{key}_BRIER", f(x["brier"], 3)); put(f"{key}_BRIER0", f(x["brier_constant"], 3)); put(f"{key}_ECE", f(x["ece5"], 3))
        put(f"{key}_N", x["n"])
        low = x["bins"][0]
        put(f"{key}_LOW_N", low[2]); put(f"{key}_LOW_PRED", pc(low[3])); put(f"{key}_LOW_OBS", pc(low[4]))
        hi = x["bins"][4]
        put(f"{key}_HI_N", hi[2]); put(f"{key}_HI_PRED", pc(hi[3])); put(f"{key}_HI_OBS", pc(hi[4]))
        brow = [f"{b[0]:.1f}--{b[1]:.1f} & {b[2]} & {pc(b[3])} & {pc(b[4])} \\\\" for b in x["bins"] if b[2]]
        put(f"TAB_{key}_BINS", "\n".join(brow))

# ------------------------------------------------------------ RQ3 abstention
Tr = R["triggers"]
for lvl, key in (("file", "TF"), ("line", "TL"), ("risk", "TR")):
    tot = {k: sum(Tr[p][lvl][k] for p in HIST) for k in ("test", "unsafe", "flag_unsafe", "safe", "flag_safe")}
    put(f"{key}_UNSAFE", tot["unsafe"]); put(f"{key}_FLAG_UNSAFE", tot["flag_unsafe"]); put(f"{key}_SAFE", tot["safe"])
    put(f"{key}_FLAG_SAFE", tot["flag_safe"]); put(f"{key}_TEST", tot["test"])
    put(f"{key}_FIRE", pc((tot["flag_unsafe"] + tot["flag_safe"]) / tot["test"]))
    put(f"{key}_RECALL", pc(tot["flag_unsafe"] / tot["unsafe"]) if tot["unsafe"] else "--")
    put(f"{key}_FALSE", pc(tot["flag_safe"] / tot["safe"]) if tot["safe"] else "--")
    put(f"{key}_PRECISION", pc(tot["flag_unsafe"] / (tot["flag_unsafe"] + tot["flag_safe"])) if tot["flag_unsafe"] + tot["flag_safe"] else "--")
    pt = {}
    for p in HIST:
        for k2, v in Tr[p][lvl]["per_trigger"].items():
            pt[k2] = pt.get(k2, 0) + v
    for k2, v in pt.items():
        put(f"{key}_{k2.upper()}", v)
put("BASE_UNSAFE_RATE", pc(int(K["TF_UNSAFE"]) / int(K["TF_TEST"])))
rq3 = []
for lvl, lab in (("file", "File-level triggers"), ("line", "Line-level triggers"), ("risk", "Risk $r(c)>\\alpha$")):
    for fb, fl in (("full", "full suite"), ("filecov", "file coverage"), ("hybrid", "hybrid")):
        x = A[f"aci:{MAIN}:abstain-{lvl}:{fb}"]["HIST"]
        rate = A["abstain_rate"].get(f"{MAIN}:{lvl}:HIST") if lvl != "risk" else R["risk_abstain_rate"][f"aci:{MAIN}"]["HIST"]
        rq3.append(f"{lab} & {fl} & {pc(rate)} & {miss(x['safe_rate'])} & {pc(x['time_red'])} & {pc(x['mut_rate'])} \\\\")
    if lvl != "risk":
        rq3.append("\\midrule")
put("TAB_RQ3", "\n".join(rq3))
for lvl, key in (("file", "AF"), ("line", "AL"), ("risk", "AR")):
    rate = A["abstain_rate"].get(f"{MAIN}:{lvl}:HIST") if lvl != "risk" else R["risk_abstain_rate"][f"aci:{MAIN}"]["HIST"]
    put(f"{key}_RATE", pc(rate))
    for fb in ("full", "filecov", "hybrid"):
        x = A[f"aci:{MAIN}:abstain-{lvl}:{fb}"]["HIST"]
        put(f"{key}_{fb.upper()}_MISS", miss(x["safe_rate"])); put(f"{key}_{fb.upper()}_TIME", pc(x["time_red"]))
        put(f"{key}_{fb.upper()}_SAFE", pc(x["safe_rate"])); put(f"{key}_{fb.upper()}_MUT", pc(x["mut_rate"]))
x = A[f"aci:0.05:abstain-risk:filecov"]["HIST"]
put("AR5_FILECOV_MISS", miss(x["safe_rate"])); put("AR5_FILECOV_TIME", pc(x["time_red"]))
put("AR5_RATE", pc(R["risk_abstain_rate"]["aci:0.05"]["HIST"]))
x = A[f"crc:{MAIN}:abstain-file:full"]["HIST"]
put("V1_ABSTAIN_MISS", miss(x["safe_rate"])); put("V1_ABSTAIN_TIME", pc(x["time_red"]))

# ------------------------------------------------------------ RQ4 faults and NameRTS
gt = R["ground_truth_check"]
put("GT_KILLED", sum(v["killed_mutants"] for v in gt.values()))
put("GT_WITHIN", sum(v["killers_within_affected"] for v in gt.values()))
put("GT_WITHIN_PCT", pc(int(K["GT_WITHIN"]) / int(K["GT_KILLED"])) if int(K["GT_KILLED"]) else "--")
rq4 = []
if NRTS:
    names = ["Retest-all", "NameRTS", "Line coverage", "Function coverage", "File coverage", "Static import", "Name matching"]
    for n in names:
        a = A.get(f"base:{n}", {}).get("NRTS")
        if a:
            rq4.append(f"{LAB.get(n, n)} & {pc(a['time_red'])} & {pc(a['safe_rate'])} & {pc(a.get('n_safe'))} & {pc(a['mut_rate'])} \\\\")
    rq4.append("\\midrule")
    for key, lab in ((f"aci:{MAIN}:plain", f"CodeTwin, ACI $\\alpha$={MAIN}"), (f"aci:{MAIN}:abstain-risk:filecov", "\\quad + risk abstention"),
                     ("budget:0.25:CodeTwin", "CodeTwin, budget 25\\%")):
        a = A[key]["NRTS"]
        rq4.append(f"{lab} & {pc(a['time_red'])} & {pc(a['safe_rate'])} & {pc(a.get('n_safe'))} & {pc(a['mut_rate'])} \\\\")
    put("TAB_RQ4", "\n".join(rq4))
    for n, key in (("NameRTS", "NR"), ("Line coverage", "NLINE"), ("File coverage", "NFILE"), ("Retest-all", "NALL"),
                   ("Function coverage", "NFUNC"), ("Static import", "NSTATIC")):
        a = A.get(f"base:{n}", {}).get("NRTS")
        if a:
            put(f"{key}_TIME", pc(a["time_red"])); put(f"{key}_SAFE", pc(a["safe_rate"])); put(f"{key}_NSAFE", pc(a.get("n_safe")))
            put(f"{key}_MUT", pc(a["mut_rate"])); put(f"{key}_RECALL", f(a["recall"]))
    for key, k2 in ((f"aci:{MAIN}:plain", "NACI"), (f"aci:{MAIN}:abstain-risk:filecov", "NACIR"), ("budget:0.25:CodeTwin", "NB25")):
        a = A[key]["NRTS"]
        put(f"{k2}_TIME", pc(a["time_red"])); put(f"{k2}_SAFE", pc(a["safe_rate"])); put(f"{k2}_NSAFE", pc(a.get("n_safe")))
        put(f"{k2}_MUT", pc(a["mut_rate"]))
    put("NRTS_MUT_TOTAL", A["base:Retest-all"]["NRTS"]["mut_total"])
for k, key in (("Line coverage", "LINE"), ("Name matching", "NAME"), ("File coverage", "FILE")):
    a = A[f"base:{k}"]["HIST"]
    put(f"{key}_MUT_DET", a["mut_detected"]); put(f"{key}_MUT_TOT", a["mut_total"])
a = A["budget:0.25:CodeTwin"]["HIST"]; put("B25_CT_MUT_DET", a["mut_detected"]); put("B25_CT_MUT_TOT", a["mut_total"])
a = A["budget:0.1:CodeTwin"]["HIST"]; put("B10_CT_MUT_DET", a["mut_detected"])

# ------------------------------------------------------------ ablation and coefficients
abl = []
full = m(A["abl:Full model"]["HIST"]["recall"])
abl_keys = ["abl:Full model"] + sorted([k for k in A if k.startswith("abl:") and k != "abl:Full model"], key=lambda k: -m(A[k]["HIST"]["recall"]))
for k in abl_keys:
    a = A[k]["HIST"]
    d = "--" if k == "abl:Full model" else f"{m(a['recall']) - full:+.3f}"
    abl.append(f"{k[4:].replace('- ', '$-$ ')} & {f(a['recall'], 3)} & {pc(a['safe_rate'])} & {pc(a['mut_rate'])} & {d} \\\\")
    put("ABL_" + re.sub(r"[^A-Z]", "", k[4:].upper()), f(a["recall"], 3))
put("TAB_ABL", "\n".join(abl))
co = R["coefficients"]
for feat in R["features"]:
    vals = [co[p][feat] for p in HIST if p in co]
    put("COEF_" + feat.upper().replace("_", ""), f"{min(vals):.1f} to {max(vals):.1f}")

# ------------------------------------------------------------ misc
put("LOC_COLLECT", sum(1 for _ in open(HERE / "collect.py")))
put("LOC_ANALYZE", sum(1 for _ in open(HERE / "analyze.py")))
wf = (HERE.parent / ".github" / "workflows" / "study.yml")
put("N_SHARDS", wf.read_text().count("- {project:") if wf.exists() else "--")
put("ACI5_SAFE_PCT", pc(A["aci:0.05:plain"]["HIST"]["safe_rate"]))
put("NRTS_CALIB_MIN", min(S[p]["calib"] for p in NRTS) if NRTS else "--")
put("NRTS_CALIB_MAX", max(S[p]["calib"] for p in NRTS) if NRTS else "--")
put("HIST_TEST_MIN", min(S[p]["test"] for p in HIST)); put("HIST_TEST_MAX", max(S[p]["test"] for p in HIST))
put("DATEUTIL_CHANGES", S["dateutil"]["changes"] if "dateutil" in S else "--")

# ------------------------------------------------------------ failure cases
fc = R["failure_cases"]
put("N_FAIL_ACI_NOTE", sum(len(v) for p, v in fc.items() if p in HIST))

def fill(template):
    missing = set()
    def rep(mo):
        k = mo.group(1)
        if k not in K:
            missing.add(k); return "\\textbf{??}"
        return K[k]
    out = re.sub(r"<<([A-Z0-9_]+)>>", rep, template)
    return out, missing

if __name__ == "__main__":
    if sys.argv[1:] == ["--list"]:
        for k, v in K.items():
            print(f"{k} = {v if len(v) < 120 else v[:120] + '...'}")
        sys.exit()
    src, dst = sys.argv[1], sys.argv[2]
    out, missing = fill(Path(src).read_text())
    Path(dst).write_text(out)
    print(f"wrote {dst}; {len(K)} keys available" + (f"; MISSING: {sorted(missing)}" if missing else ""))
