"""Change-level residual risk q(c): a calibrated probability that a selection misses an affected test.

The product formula r(c) = 1 - prod(1 - p~(i)) treats skipped tests as independent and, in the study,
overestimated the risk of calibrated selections (12.7% predicted vs 9.3% observed). q(c) is a logistic
model over change-level features of the selection; its prior weights were fitted on the five history
projects of study v3 (pilot/v3/run_v3.py, `prior_change_model`). Once enough labelled changes exist in
this repository, `fit()` refits it on them.

Only pre-change evidence is used (no look-ahead): the recorded run at the base commit, the diff and the
static facts of the new code.
"""
from __future__ import annotations

import math

FEATURES = ["log_sum_p", "max_p", "r_prod", "n_skip_file", "n_skip_line", "trig_dyn", "trig_unt", "trig_mod",
            "log_universe"]
# study v3, all history projects (3857 selection outcomes, 1313 misses)
PRIOR_COEF = [-1.2311, 6.6149, 0.0831, 1.3677, 0.5691, -0.1143, -0.4428, 0.9570, 0.1929]
PRIOR_INTERCEPT = -5.0510
MIN_LABELLED = 40


def _innermost(defs: list[list[int]], line: int) -> list[int] | None:
    best = None
    for d in defs:
        if d[0] <= line <= d[1] and (best is None or d[0] >= best[0]):
            best = d
    return best


def triggers(diff, prev_run, prev_static, now_static, is_source) -> dict[str, bool]:
    """Line-level uncertainty triggers of the paper (Table 3): dynamic call, untested change, module-level change."""
    dyn = mod = unt = False
    executed: dict[str, set[int]] = {}
    for files in prev_run.covered.values():
        for f, lines in files.items():
            executed.setdefault(f, set()).update(lines)
    for f, d in diff.items():
        if not is_source(f):
            continue
        if d.status == "A":
            unt = True
            continue
        st = now_static.get(f)
        if st is not None:
            dynl, modl = set(st.dyn_lines), set(st.mod_lines)
            for line in d.new:
                fn = _innermost(st.defs, line)
                if line in dynl or (fn and any(fn[0] <= x <= fn[1] for x in dynl)):
                    dyn = True
                if line in modl:
                    mod = True
        pst = prev_static.get(d.old_path or f)
        if pst is not None:
            if set(d.old) & set(pst.mod_lines):
                mod = True
            for line in d.old:
                fn = _innermost(pst.defs, line)
                if fn and not (set(range(fn[2], fn[1] + 1)) & executed.get(d.old_path or f, set())):
                    unt = True
    return {"dynamic_call": dyn, "untested_change": unt, "module_level_change": mod}


def features(rows: dict[str, dict], scores: dict[str, float], selected: set[str], recal, trig: dict[str, bool]) -> dict:
    skipped = [t for t in rows if t not in selected]
    ps = [recal(scores[t]) for t in skipped]
    keep = 1.0
    for p in ps:
        keep *= 1.0 - p
    return {
        "log_sum_p": math.log1p(sum(ps)),
        "max_p": max(ps) if ps else 0.0,
        "r_prod": 1.0 - keep,
        "n_skip_file": math.log1p(sum(rows[t].get("cov_file", 0) for t in skipped)),
        "n_skip_line": math.log1p(sum(rows[t].get("cov_line", 0) for t in skipped)),
        "trig_dyn": float(trig.get("dynamic_call", False)),
        "trig_unt": float(trig.get("untested_change", False)),
        "trig_mod": float(trig.get("module_level_change", False)),
        "log_universe": math.log(max(len(rows), 1)),
    }


class ChangeRiskModel:
    def __init__(self, coef: list[float] | None = None, intercept: float | None = None, source: str = "prior"):
        self.coef = list(PRIOR_COEF if coef is None else coef)
        self.intercept = PRIOR_INTERCEPT if intercept is None else intercept
        self.source = source

    def __call__(self, z: dict) -> float:
        s = self.intercept + sum(w * z[k] for w, k in zip(self.coef, FEATURES, strict=True))
        return 1.0 / (1.0 + math.exp(-max(min(s, 50.0), -50.0)))

    @classmethod
    def fit(cls, points: list[list]) -> ChangeRiskModel:
        """points: [[feature dict, missed (0/1)], ...] from labelled changes; the prior if too few."""
        ys = [int(p[1]) for p in points]
        if len(points) < MIN_LABELLED or len(set(ys)) < 2:
            return cls()
        from sklearn.linear_model import LogisticRegression
        m = LogisticRegression(max_iter=5000).fit([[p[0][k] for k in FEATURES] for p in points], ys)
        return cls([float(v) for v in m.coef_[0]], float(m.intercept_[0]), source=f"fitted on {len(points)} changes")
