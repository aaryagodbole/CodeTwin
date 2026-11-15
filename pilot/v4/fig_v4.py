#!/usr/bin/env python3
"""Figure for the multi-language replication: observed miss rate against the target alpha, for a threshold
calibrated once (static CRC) and for adaptive calibration (ACI), per language.

Python: the history projects of the main study (results.json of branch study-v2-results, pooled "HIST").
Go, Rust, JS/TS: results_by_language/results.json of study v4.

Usage: python fig_v4.py <python results.json> <output.pdf>
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ALPHAS = [0.05, 0.1, 0.2]
# categorical slots 1-4 of the reference palette, fixed order; markers are the secondary encoding
SERIES = [("Python", "#2a78d6", "o"), ("Go", "#eb6834", "s"), ("Rust", "#1baf7a", "^"), ("JS/TS", "#eda100", "D")]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def m(x):
    return x[0] if isinstance(x, list) else x


def series(results: dict, group: str, variant: str) -> list[float]:
    return [100 * (1 - m(results["agg"][f"{variant}:{a}:plain"][group]["safe_rate"])) for a in ALPHAS]


def main() -> None:
    py = json.loads(Path(sys.argv[1]).read_text())
    v4 = json.loads((HERE / "results_by_language" / "results.json").read_text())
    src = {"Python": (py, "HIST"), "Go": (v4, "lang_go"), "Rust": (v4, "lang_rust"), "JS/TS": (v4, "lang_javascript")}
    plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "font.family": "DejaVu Sans"})
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.1), sharey=True)
    xs = [100 * a for a in ALPHAS]
    YMAX = 5 * (int(max(v for name, _, _ in SERIES for var in ("crc", "aci")
                         for v in series(*src[name], var)) / 5) + 1)
    for ax, variant, title in ((axes[0], "crc", "Calibrated once (static)"), (axes[1], "aci", "Adaptive (ACI)")):
        ax.plot([0, 22], [0, 22], ls=(0, (4, 3)), lw=1, color=MUTED, zorder=1, label="Target (observed = $\\alpha$)")
        ends = []
        for name, color, marker in SERIES:
            res, grp = src[name]
            ys = series(res, grp, variant)
            ax.plot(xs, ys, color=color, lw=2, marker=marker, ms=6, mec="white", mew=1.2, zorder=3, label=name)
            ends.append([ys[-1], name])
        # direct labels at the right end, nudged apart so they never overlap
        ends.sort()
        for i in range(1, len(ends)):
            ends[i][0] = max(ends[i][0], ends[i - 1][0] + 0.05 * YMAX)
        for y, name in ends:
            ax.text(21.0, y, name, color=INK, fontsize=7, va="center", ha="left")
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xticks(xs, [f"{x:g}%" for x in xs])
        ax.set_xlim(3, 25)
        ax.set_ylim(0, YMAX)
        ax.set_xlabel("Target miss rate $\\alpha$")
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Observed miss rate (% of changes)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False, fontsize=7.5, handlelength=2.2)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(sys.argv[2])
    fig.savefig(Path(sys.argv[2]).with_suffix(".png"), dpi=200)
    print("wrote", sys.argv[2])


if __name__ == "__main__":
    main()
