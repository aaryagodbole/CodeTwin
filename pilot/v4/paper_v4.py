#!/usr/bin/env python3
"""Fills the multi-language part of the paper from the study v4 results (nothing typed by hand).

Reads results_by_language/results.json (analyze_v4.py --per-language) and results_by_language/v4_change.json
(run_v4_change.py) and replaces two generated blocks in the paper:

  %% v4-macros: begin ... %% v4-macros: end     \\newcommand definitions (\\vX), used in the text
  %% v4-table: begin  ... %% v4-table: end      Table "tab:v4"

Usage: python paper_v4.py ../../paper/sncs/main.tex          (edits the file in place)
       python paper_v4.py --list                             (print every macro and its value)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results_by_language"
R = json.loads((RES / "results.json").read_text())
C = json.loads((RES / "v4_change.json").read_text())
A, S = R["agg"], R["summary"]
HIST = [p for p in S if S[p]["mode"] == "history" and S[p]["changes"]]
SEP = [p for p in S if S[p]["mode"] == "pairs" and S[p]["changes"]]
ORDER = ["lang_go", "lang_rust", "lang_javascript"]
NAMES = {"lang_go": "Go", "lang_rust": "Rust", "lang_javascript": "JS/TS", "lang_java": "Java"}
assert set(ORDER) == set(HIST), (ORDER, HIST)


def m(x):
    return x[0] if isinstance(x, list) else x


def pc(x, d=1):
    return "--" if x is None else f"{100 * m(x):.{d}f}"


def miss(v):
    return "--" if not v else f"{100 * (1 - m(v['safe_rate'])):.1f}"


def saved(v):
    return "--" if not v else f"{100 * m(v['time_red']):.1f}"


K: dict[str, str] = {}


def put(name: str, value) -> None:
    assert re.fullmatch(r"[A-Za-z]+", name), name
    K[name] = str(value)


# ------------------------------------------------------------ subjects
data_dir = HERE / "data"
repos = {p: json.loads((data_dir / p / "meta.json").read_text())["repos"] for p in HIST + SEP}
put("Nrepos", sum(len(repos[p]) for p in HIST))
put("Nchanges", sum(S[p]["changes"] for p in HIST))
put("Ntest", sum(S[p]["test"] for p in HIST))
put("Ncalib", sum(S[p]["calib"] for p in HIST))
for p in ORDER:
    n = NAMES[p].replace("/", "")
    put(f"Repos{n}", len(repos[p]))
    put(f"Changes{n}", S[p]["changes"])
    put(f"Test{n}", S[p]["test"])
put("JavaRepos", sum(len(repos[p]) for p in SEP))
put("JavaChanges", sum(S[p]["changes"] for p in SEP))
put("JavaTest", sum(S[p]["test"] for p in SEP))
put("JavaCalib", sum(S[p]["calib"] for p in SEP))
put("MinChanges", 20)

# ------------------------------------------------------------ selection quality, pooled (HIST)
H = lambda k: A[k]["HIST"]  # noqa: E731
put("FileMiss", miss(H("base:File coverage")))
put("FileSaved", saved(H("base:File coverage")))
put("LineMiss", miss(H("base:Line coverage")))
put("LineSaved", saved(H("base:Line coverage")))
put("StaticMiss", miss(H("base:Static import")))
put("NameMiss", miss(H("base:Name matching")))
put("CrcStaticMiss", miss(H("crc:0.1:plain")))
put("CrcStaticSaved", saved(H("crc:0.1:plain")))
put("CrcStaticFiveMiss", miss(H("crc:0.05:plain")))
put("CrcStaticTwentyMiss", miss(H("crc:0.2:plain")))
put("MinLambdaTwenty", f"{min(R['calibration'][q]['0.2']['lambda'] for q in ORDER):.2f}")
put("CrcStaticTwentyTestRed", pc(H("crc:0.2:plain")["test_red"]))
for p_ in ORDER:
    put("CrcStaticTwentyMiss" + NAMES[p_].replace("/", ""), miss(A["crc:0.2:plain"][p_]))
for a, tag in ((0.05, "Five"), (0.1, "Ten"), (0.2, "Twenty")):
    put(f"Aci{tag}Miss", miss(H(f"aci:{a}:plain")))
    put(f"Aci{tag}Saved", saved(H(f"aci:{a}:plain")))
    put(f"Win{tag}Miss", miss(H(f"win:{a}:plain")))
put("RiskAbMiss", miss(H("aci:0.1:abstain-risk:filecov")))
put("RiskAbSaved", saved(H("aci:0.1:abstain-risk:filecov")))
put("RiskAbRate", pc(R["risk_abstain_rate"]["aci:0.1"]["HIST"]))
put("LineAbMiss", miss(H("aci:0.1:abstain-line:filecov")))
put("LineAbSaved", saved(H("aci:0.1:abstain-line:filecov")))
for p in ORDER:
    n = NAMES[p].replace("/", "")
    put(f"AciTenMiss{n}", miss(A["aci:0.1:plain"][p]))
    put(f"AciFiveMiss{n}", miss(A["aci:0.05:plain"][p]))
    put(f"AciTwentyMiss{n}", miss(A["aci:0.2:plain"][p]))
    put(f"LineUnsafeN{n}", round((1 - m(A["base:Line coverage"][p]["safe_rate"])) * S[p]["test"]))
    put(f"LineMiss{n}", miss(A["base:Line coverage"][p]))
    put(f"FileSaved{n}", saved(A["base:File coverage"][p]))
    put(f"StaticMiss{n}", miss(A["base:Static import"][p]))

# ------------------------------------------------------------ separate languages (too few changes)
SJ = SEP[0] if SEP else None
if SJ:
    put("JavaLineMiss", miss(A["base:Line coverage"][SJ]))
    put("JavaFileSaved", saved(A["base:File coverage"][SJ]))
    put("JavaLineSaved", saved(A["base:Line coverage"][SJ]))
    put("JavaFeasible", "no" if not any(v["feasible"] for v in R["calibration"][SJ].values()) else "yes")
    feas = sorted(float(a) for a, v in R["calibration"][SJ].items() if v["feasible"])
    assert feas == [0.2], f"Java text assumes a feasible threshold only at 0.20, got {feas}"
    put("JavaAciTwentyMiss", miss(A["aci:0.2:plain"][SJ]))
    put("JavaAciTwentySaved", saved(A["aci:0.2:plain"][SJ]))
    put("JavaAciTwentyMissN", round((1 - m(A["aci:0.2:plain"][SJ]["safe_rate"])) * S[SJ]["test"]))

# ------------------------------------------------------------ budget mode, learned vs coverage ranking
b = "0.25"
put("BudgetLearned", f"{m(H(f'budget:{b}:CodeTwin')['recall']):.3f}")
put("BudgetCoverage", f"{m(H(f'budget:{b}:Coverage-ranked')['recall']):.3f}")
put("BudgetP", f"{R['tests'][f'recall@{b}: CodeTwin vs Coverage-ranked']['p']:.2f}")
put("BudgetRandom", f"{m(H(f'budget:{b}:Random')['recall']):.3f}")

# ------------------------------------------------------------ triggers against line-coverage misses (pooled)
tr = {lvl: {k: sum(R["triggers"][p][lvl][k] for p in HIST) for k in ("unsafe", "safe", "flag_unsafe", "flag_safe")}
      for lvl in ("file", "line", "risk")}
put("Unsafe", tr["line"]["unsafe"])
put("Safe", tr["line"]["safe"])
for lvl, tag in (("file", "File"), ("line", "Line"), ("risk", "Risk")):
    put(f"Trig{tag}Flag", tr[lvl]["flag_unsafe"])
    put(f"Trig{tag}SafePct", f"{100 * tr[lvl]['flag_safe'] / tr[lvl]['safe']:.1f}")
for p in ORDER:
    n = NAMES[p].replace("/", "")
    put(f"Unsafe{n}", R["triggers"][p]["line"]["unsafe"])
    put(f"TrigRiskFlag{n}", R["triggers"][p]["risk"]["flag_unsafe"])

# ------------------------------------------------------------ why risk-based abstention missed (why_abstention.py)
D = json.loads((RES / "abstention_diag.json").read_text())
put("PyFileOnlyRate", pc(D["python"]["rate"]))
put("PyFileOnlyRateNoImport", pc(D["python"]["rate_without_import_time_changes"]))
for p_ in ORDER:
    put("FileOnlyRate" + NAMES[p_].replace("/", ""), pc(D["languages"][p_]["rate"]))
gr = [u for p_ in ("lang_go", "lang_rust") for u in D["languages"][p_]["unsafe"]]
assert all(u["missed_file_only"] for p_ in ORDER for u in D["languages"][p_]["unsafe"])
put("GoRustMaxMissedP", f"{max(x for u in gr for x in u['missed_p']):.3f}")
put("GoRustMaxR", f"{max(u['r'] for u in gr):.3f}")
put("JSMissedP", f"{max(x for u in D['languages']['lang_javascript']['unsafe'] for x in u['missed_p']):.3f}")
put("RustNoStaticPath", sum(1 for u in D["languages"]["lang_rust"]["unsafe"] if not u["missed_static_path"]))

# ------------------------------------------------------------ change-level risk q(c)
rk = C["risk"]["aci10:HIST"]
put("QObserved", pc(rk["observed"]))
put("QPredicted", pc(rk["change_level_mean"]))
put("ProdPredicted", pc(rk["product_mean"]))
put("QBrier", f"{rk['change_level_brier']:.3f}")
put("ProdBrier", f"{rk['product_brier']:.3f}")
put("ConstBrier", f"{rk['brier_constant']:.3f}")
for p in ORDER:
    n = NAMES[p].replace("/", "")
    r = C["risk"][f"aci10:{p}"]
    put(f"QPredicted{n}", pc(r["change_level_mean"]))
    put(f"ProdPredicted{n}", pc(r["product_mean"]))
    put(f"QObserved{n}", pc(r["observed"]))
for rule, tag in (("rprod", "R"), ("qrule", "Q"), ("selective", "Sel")):
    s = C["selective"][f"{rule}:sel0.1:t0.05:HIST"]
    put(f"{tag}RuleAbst", pc(s["abstain_rate"]))
    put(f"{tag}RuleMissProc", pc(s["miss_among_proceeded"]))
    put(f"{tag}RuleSaved", pc(s["time_red"]))
    worst = max((C["selective"][f"{rule}:sel0.1:t0.05:{p}"]["miss_among_proceeded"] or 0.0, NAMES[p]) for p in ORDER)
    put(f"{tag}RuleWorst", pc(worst[0]))
    put(f"{tag}RuleWorstLang", worst[1])

# ------------------------------------------------------------ table
ROWS = [("File coverage", "base:File coverage"), ("Line coverage", "base:Line coverage"),
        ("Static imports", "base:Static import"), ("Name matching", "base:Name matching"),
        (r"CRC, static, $\alpha$=0.10", "crc:0.1:plain"),
        (r"ACI, $\alpha$=0.05", "aci:0.05:plain"), (r"ACI, $\alpha$=0.10", "aci:0.1:plain"),
        (r"ACI, $\alpha$=0.20", "aci:0.2:plain"),
        (r"ACI 0.10 + risk abstention", "aci:0.1:abstain-risk:filecov"),
        (r"ACI 0.10 + line-trigger abstention", "aci:0.1:abstain-line:filecov")]
cols = ORDER + ["HIST"]
head = " & ".join([r"\textbf{Technique}"] + [rf"\textbf{{{NAMES.get(p, 'Pooled')}}}" for p in cols])
n_row = " & ".join(["Test changes"] + [str(S[p]["test"]) if p in S else str(sum(S[q]["test"] for q in HIST)) for p in cols])
lines = [r"\begin{table}[htbp]",
         r"\caption{Replication in Other Languages: Miss Rate / Test Time Saved (\%, Test Changes)}",
         r"\label{tab:v4}", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{2pt}",
         r"\begin{tabular}{@{}l" + "r" * len(cols) + "@{}}", r"\toprule", head + r" \\", r"\midrule",
         n_row + r" \\", r"\midrule"]
for label, key in ROWS:
    cells = [f"{miss(A[key].get(p))}/{saved(A[key].get(p))}" for p in cols]
    lines.append(" & ".join([label] + cells) + r" \\")
lines += [r"\bottomrule", r"\end{tabular}",
          r"\footnotetext{Abstention runs file coverage combined with the selection. Ground truth: tests whose "
          r"recorded coverage of the merged code includes a changed line, plus the tests the pull request adds or changes. JS/TS pools JavaScript and TypeScript, "
          r"which share one adapter.}",
          r"\end{table}"]
TABLE = "\n".join(lines)
MACROS = "\n".join(rf"\newcommand{{\v{k}}}{{{v}}}" for k, v in K.items())


def replace_block(text: str, tag: str, body: str) -> str:
    pat = re.compile(rf"(%% {tag}: begin\n).*?(%% {tag}: end)", re.S)
    if not pat.search(text):
        raise SystemExit(f"marker '%% {tag}: begin/end' not found")
    return pat.sub(lambda mo: mo.group(1) + body + "\n" + mo.group(2), text)


if __name__ == "__main__":
    if sys.argv[1:] == ["--list"]:
        for k, v in K.items():
            print(f"\\v{k} = {v}")
        print(TABLE)
        sys.exit(0)
    dst = Path(sys.argv[1])
    t = dst.read_text(encoding="utf-8")
    t = replace_block(t, "v4-macros", MACROS)
    t = replace_block(t, "v4-table", TABLE)
    used = set(re.findall(r"\\v([A-Za-z]+)\b", t)) - {"space", "box", "skip", "fill", "rule", "line", "adjust",
                                                       "center", "top", "bar"}
    missing = sorted(u for u in used if u not in K and f"\\newcommand{{\\v{u}}}" not in t)
    if missing:
        raise SystemExit(f"macros used but not generated: {missing}")
    dst.write_text(t, encoding="utf-8")
    print(f"wrote {dst}: {len(K)} macros, table tab:v4")
