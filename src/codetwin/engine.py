"""Ties the layers together: record evidence, analyse a change, select tests, learn from outcomes."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from . import config as cfgmod
from . import report
from .evidence import coverage, static
from .evidence import diff as diffmod
from .evidence.model import TestRun
from .graph.impact import Impact, build_graph, impact_of
from .risk import features
from .risk.calibration import AdaptiveLevel, crc_threshold
from .risk.model import RiskModel
from .risk.residual import Recalibrator
from .selection import Decision, budget_select, decide, threshold_select
from .store.db import Store

UNCALIBRATED_THRESHOLD = 0.5


class Engine:
    def __init__(self, root: str | Path = "."):
        self.cfg = cfgmod.load(root)
        self.root = self.cfg.root
        self.store = Store(self.cfg.db_path)
        self.model = RiskModel.load(self.cfg.state_dir / "model.json")

    # ------------------------------------------------------------- helpers
    def head(self) -> str:
        return diffmod.git(self.root, "rev-parse", "HEAD").strip()

    def is_source(self, path: str) -> bool:
        name = path.rsplit("/", 1)[-1]
        if path.startswith(self.cfg.tests_dir.rstrip("/") + "/") or name.startswith("test_"):
            return False
        return path.endswith(".py") and any(path.startswith(d.rstrip("/") + "/") for d in self.cfg.source_dirs)

    def facts_now(self):
        return static.snapshot(self.root, self.cfg.src_root, self.cfg.packages, self.cfg.source_dirs + [self.cfg.tests_dir])

    def tests_now(self) -> list[str]:
        d = self.root / self.cfg.tests_dir
        return sorted(p.relative_to(self.root).as_posix() for p in d.rglob("test_*.py")) if d.exists() else []

    def history(self) -> list[list[str]]:
        out = subprocess.run(["git", "log", "--first-parent", "--name-only", "--format=@@", "-n", "300"],
                             cwd=self.root, capture_output=True, text=True, check=False).stdout
        commits = [c.split() for c in out.split("@@") if c.strip()]
        return commits[::-1]

    # ------------------------------------------------------------- record
    def record(self) -> TestRun:
        """Run the full suite with per-test coverage on the current checkout and store it as evidence."""
        sha = self.head()
        run = coverage.run_suite(self.root, sha, self.cfg.tests_dir, self.cfg.packages, self.cfg.src_root)
        self.store.save_run(run)
        self.store.save_static(sha, self.facts_now())
        return run

    # ------------------------------------------------------------- analyse a change
    def analyse(self, base: str | None = None):
        base = base or self.store.latest_run_sha()
        if not base:
            raise RuntimeError("no recorded run yet; run `codetwin record` on a clean checkout first")
        prev = self.store.get_run(base)
        if prev is None:
            raise RuntimeError(f"no recorded run for {base[:10]}; run `codetwin record` there first")
        diff = diffmod.changed_lines(self.root, base)
        tests = sorted(set(prev.durations) | set(self.tests_now()))
        rows = features.compute(diff, prev, self.store.get_static(base), self.facts_now(), tests,
                                self.cfg.src_root, self.is_source, self.history())
        return base, prev, diff, rows

    # ------------------------------------------------------------- select
    def select(self, base: str | None = None, alpha: float | None = None, budget: float | None = None) -> Decision:
        base, prev, diff, rows = self.analyse(base)
        scores = self.model.scores(rows)
        if not any(self.is_source(f) for f in diff):
            d = Decision({t for t, r in rows.items() if r["forced"]}, "proceed", 0.0, None, "no-source-change",
                         ["no source file changed; only added or changed tests run"])
            return self._with_report(d, base, prev, diff, rows, scores)
        recal = self._recalibrator()
        alpha = self.cfg.alpha if alpha is None else alpha
        times = {t: prev.durations.get(t, 1.0) for t in rows}
        if budget is not None:
            sel = budget_select(rows, scores, times, budget * sum(times.values()))
            d = decide(rows, scores, sel, alpha, recal, self.cfg.fallback, mode=f"budget {budget:.0%}")
        else:
            level = AdaptiveLevel(alpha, self.cfg.aci_gamma, self.store.get_state("alpha_t"))
            calib = self.store.get_state("calibration", [])
            lam = crc_threshold(calib, level.level) if len(calib) >= math.ceil(1 / max(level.level, 1e-9)) else -2.0
            note = []
            if lam == -2.0:
                lam = UNCALIBRATED_THRESHOLD
                note = [f"not calibrated yet ({len(calib)} labelled changes); using threshold {lam}"]
            sel = threshold_select(rows, scores, lam)
            d = decide(rows, scores, sel, alpha, recal, self.cfg.fallback, threshold=lam)
            d.reasons = note + d.reasons
        unknowns = self.impact([f for f in diff if self.is_source(f)]).unknowns
        d.reasons += unknowns
        self._with_report(d, base, prev, diff, rows, scores)
        did = self.store.save_decision(base=base, head="working-tree", mode=d.mode, alpha=alpha,
                                       alpha_t=self.store.get_state("alpha_t", alpha), threshold=d.threshold,
                                       residual_risk=d.residual_risk, decision=d.decision, selected=d.selected,
                                       reasons=d.reasons)
        self.store.set_state("last_decision", {"id": did, "base": base, "scores": scores, "selected": sorted(d.selected)})
        return d

    def _with_report(self, d: Decision, base, prev, diff, rows, scores) -> Decision:
        ctx = report.Context(cfg=self.cfg, store=self.store, base=base, prev=prev, diff=diff, rows=rows, scores=scores,
                             decision=d, is_source=self.is_source, facts_now=self.facts_now, impact=self.impact)
        d.extras = report.build(ctx)
        return d

    def _recalibrator(self) -> Recalibrator:
        pts = self.store.get_state("recal_points", [])
        return Recalibrator().fit([p[0] for p in pts], [p[1] for p in pts])

    # ------------------------------------------------------------- learn from the full run
    def learn(self) -> dict:
        """Run the full suite on the current tree, derive which tests were truly affected by the last
        analysed change, and update calibration, recalibration and the adaptive level."""
        last = self.store.get_state("last_decision")
        if not last:
            raise RuntimeError("no decision to learn from; run `codetwin select` first")
        _base, _prev, diff, rows = self.analyse(last["base"])
        new = coverage.run_suite(self.root, "working-tree", self.cfg.tests_dir, self.cfg.packages, self.cfg.src_root)
        affected = set()
        for f, d in diff.items():
            if not self.is_source(f) or d.status == "D":
                continue
            for t, files in new.covered.items():
                if set(d.new) & set(files.get(f, [])):
                    affected.add(t)
            if set(d.new) & set(new.import_lines.get(f, [])):
                affected |= {t for t, files in new.covered.items() if f in files}
        affected |= {t for t, r in rows.items() if r["test_changed"]}
        scores, selected = last["scores"], set(last["selected"])
        missed = bool(affected - selected)
        non_forced = [scores[t] for t in affected if t in scores and not rows.get(t, {}).get("forced")]
        calib = self.store.get_state("calibration", [])
        calib.append(min(non_forced) if non_forced else math.inf)
        self.store.set_state("calibration", calib[-200:])
        pts = self.store.get_state("recal_points", [])
        pts += [[scores[t], int(t in affected)] for t in scores if not rows.get(t, {}).get("forced")]
        self.store.set_state("recal_points", pts[-5000:])
        level = AdaptiveLevel(self.cfg.alpha, self.cfg.aci_gamma, self.store.get_state("alpha_t"))
        self.store.set_state("alpha_t", level.update(missed))
        self.store.save_outcome(last["id"], missed)
        return {"affected": sorted(affected), "missed": sorted(affected - selected), "alpha_t": level.alpha_t,
                "calibration_size": len(calib)}

    # ------------------------------------------------------------- impact
    def impact(self, files: list[str], base: str | None = None) -> Impact:
        base = base or self.store.latest_run_sha()
        run = self.store.get_run(base) if base else None
        g = build_graph(self.facts_now(), run, self.cfg.src_root)
        return impact_of(g, files, self.tests_now())

    def explain(self) -> dict:
        last = self.store.get_state("last_decision")
        if not last:
            return {"message": "no decision yet"}
        row = self.store.con.execute("select decision, residual_risk, threshold, alpha, reasons from decisions where id=?",
                                     (last["id"],)).fetchone()
        return {"decision": row[0], "residual_risk": row[1], "threshold": row[2], "alpha": row[3],
                "reasons": __import__("json").loads(row[4]), "selected": last["selected"]}
