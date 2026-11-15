#!/usr/bin/env python3
"""Why risk-based abstention caught few unsafe changes outside Python (numbers for the paper's RQ6 text).

Every test that line coverage misses executed the changed file before the change, but not the changed lines
("file-only" tests). The rule r(c) > alpha flags a change only if those skipped tests have a high estimated
probability of being affected, which the model learns from history. This script measures:
  * how often file-only tests were affected, in the Python history projects and per other language;
  * the same in Python without changes to import-time code (Python-specific ground-truth rule);
  * the recalibrated probability and r(c) of the changes on which line coverage was unsafe (other languages).

Usage: python why_abstention.py <dir with the Python study data: click/, dateutil/, ...>
Writes results_by_language/abstention_diag.json
"""
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_v4 as V  # noqa: E402

PY = ["click", "dateutil", "itsdangerous", "marshmallow", "toolz"]
LANGS = ["lang_go", "lang_rust", "lang_javascript"]


def file_only_rate(A, projects):
    n = k = n_nomod = k_nomod = 0
    for p in projects:
        _, cs, _, _ = A.load_changes(p)
        for c in cs:
            F = A.forced(c)
            fo = [t for t in c["universe"] if t not in F and c["rows"][t]["cov_file"] and not c["rows"][t]["cov_line"]]
            aff = sum(c["rows"][t]["label"] for t in fo)
            n, k = n + len(fo), k + aff
            if not c["trig_line"].get("module_level_change"):
                n_nomod, k_nomod = n_nomod + len(fo), k_nomod + aff
    return {"tests": n, "affected": k, "rate": k / n if n else None,
            "rate_without_import_time_changes": k_nomod / n_nomod if n_nomod else None}


def main() -> None:
    src = (HERE.parent / "analyze.py").read_text(encoding="utf-8")
    py = types.ModuleType("analyze_py")
    py.__file__ = str(HERE.parent / "analyze.py")
    exec(compile(src, py.__file__, "exec"), py.__dict__)
    py.DATA = Path(sys.argv[1])
    out = {"python": file_only_rate(py, PY), "languages": {}}
    A = V.an
    for p in LANGS:
        V._lang_of(p)
    hist = LANGS
    data = {p: A.load_changes(p)[1] for p in hist}
    for p in hist:
        calib, test = A.split(data[p])
        model = A.train([c for q in hist if q != p for c in data[q]])
        recal = A.fit_recalibration(calib, model)
        unsafe = []
        for c in test:
            line = A.baseline_sets(c)["Line coverage"]
            if c["affected"] <= line:
                continue
            s = A.scores_of(model, c)
            missed = sorted(c["affected"] - line)
            unsafe.append({"r": A.residual_risk(c, s, line, recal),
                           "missed_p": [recal(s[t]) for t in missed],
                           "missed_file_only": all(c["rows"][t]["cov_file"] and not c["rows"][t]["cov_line"] for t in missed),
                           "missed_static_path": any(c["rows"][t]["static_inv_dist"] > 0 for t in missed)})
        out["languages"][p] = {**file_only_rate(A, [p]), "unsafe": unsafe}
    dst = HERE / "results_by_language" / "abstention_diag.json"
    dst.write_text(json.dumps(out, indent=1))
    print("wrote", dst)


if __name__ == "__main__":
    main()
