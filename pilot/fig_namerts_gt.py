"""Figure for RQ4: share of safe changes on the NameRTS commits under the two ground truths.

Usage: python3 fig_namerts_gt.py <results.json of the study run> <output dir>
Reads only results.json (agg[...]["NRTS"]), the same data as Table tab:rq4.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = json.loads(Path(sys.argv[1]).read_text())
OUT = Path(sys.argv[2])
A = R["agg"]
m = lambda x: x[0] if isinstance(x, list) else x

rows = [("NameRTS", "base:NameRTS"),
        ("Line coverage", "base:Line coverage"),
        ("Function coverage", "base:Function coverage"),
        ("File coverage", "base:File coverage"),
        ("Static import", "base:Static import"),
        ("Name matching", "base:Name matching"),
        ("CodeTwin, ACI $\\alpha$=0.10", "aci:0.1:plain"),
        ("  + risk abstention", "aci:0.1:abstain-risk:filecov"),
        ("CodeTwin, budget 25%", "budget:0.25:CodeTwin")]

plt.rcParams.update({"font.size": 7})
fig, ax = plt.subplots(figsize=(3.5, 2.9))
n = len(rows)
for i, (lab, k) in enumerate(rows):
    a = A[k]["NRTS"]
    y = n - 1 - i
    cov, nam, tim = 100 * m(a["safe_rate"]), 100 * m(a["n_safe"]), 100 * m(a["time_red"])
    ax.plot([cov, nam], [y, y], color="0.55", lw=1.2, zorder=1)
    ax.scatter(cov, y, s=18, color="black", zorder=4, label="coverage ground truth" if i == 0 else None)
    ax.scatter(nam, y, s=38, facecolors="white", edgecolors="black", lw=0.9, zorder=3,
               label="NameRTS ground truth" if i == 0 else None)
    ax.text(103, y, f"{tim:.1f}", va="center", ha="left", fontsize=6.5)
ax.text(103, n - 0.45, "time\nsaved %", va="bottom", ha="left", fontsize=6)
ax.set_yticks(range(n))
ax.set_yticklabels([r[0] for r in rows][::-1])
ax.set_xlim(30, 101)
ax.set_ylim(-0.6, n - 0.4)
ax.set_xlabel("Changes on which the selection was safe (%)")
ax.grid(axis="x", alpha=0.3, lw=0.5)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(loc="lower right", bbox_to_anchor=(0.84, 1.0), ncol=2, fontsize=6, frameon=False, handletextpad=0.3, columnspacing=1.0)
fig.tight_layout()
fig.savefig(OUT / "namerts_gt.pdf")
fig.savefig(OUT / "namerts_gt.png", dpi=200)
print("wrote", OUT / "namerts_gt.pdf")
