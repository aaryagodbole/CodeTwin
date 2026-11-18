"""Ties the layers together: record evidence, analyse a change, select tests, learn from outcomes."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Self

from . import config as cfgmod
from . import lang as langmod
from . import report
from .evidence import diff as diffmod
from .evidence.model import TestRun
from .graph.impact import Impact, build_graph, impact_of
from .risk import features
from .risk.calibration import AdaptiveLevel, crc_threshold
from .risk.model import RiskModel
from .risk.residual import Recalibrator, residual_risk
from .selection import Decision, budget_select, decide, threshold_select
from .store.db import Store

UNCALIBRATED_THRESHOLD = 0.5


class Engine:
    def __init__(self, root: str | Path = "."):
        self.cfg = cfgmod.load(root)
        self.root = self.cfg.root
        self.lang = langmod.get(self.cfg)
        self.store = Store(self.cfg.db_path)
        self.model = RiskModel.load(self.cfg.state_dir / "model.json")

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------- helpers
    def head(self) -> str:
        return diffmod.git(self.root, "rev-parse", "HEAD").strip()

    def is_source(self, path: str) -> bool:
        return self.lang.is_source(path)

    def facts_now(self):
        return self.lang.facts()

    def tests_now(self) -> list[str]:
        return self.lang.list_tests()

    def changed(self, base: str, head: str | None = None):
        return diffmod.changed_lines(self.root, base, head, self.lang.extensions)

    def history(self) -> list[list[str]]:
        out = subprocess.run(["git", "log", "--first-parent", "--name-only", "--format=@@", "-n", "300"],
                             cwd=self.root, capture_output=True, text=True, check=False).stdout
        commits = [c.split() for c in out.split("@@") if c.strip()]
        return commits[::-1]

    # ------------------------------------------------------------- record
    def record(self) -> TestRun:
        """Run the full suite with per-test coverage on the current checkout and store it as evidence."""
        sha = self.head()
        run = self.lang.run_suite(sha)
        self.store.save_run(run)
        self.store.save_static(sha, self.facts_now())
        return run

    # ------------------------------------------------------------- analyse a change
    def change(self, base: str | None = None):
        """The recorded commit to compare with, its recorded run, and the working tree's changed lines.

        Raises RuntimeError when nothing is recorded; the CLI prints it and exits with 2.
        """
        base = base or self.store.latest_run_sha()
        if not base:
            raise RuntimeError("no recorded run yet; run `codetwin record` on a clean checkout first")
        prev = self.store.get_run(base)
        if prev is None:
            raise RuntimeError(f"no recorded run for {base[:10]}; run `codetwin record` there first")
        return base, prev, self.changed(base)

    def analyse(self, base: str | None = None):
        base, prev, diff = self.change(base)
        tests = sorted(set(prev.durations) | set(self.tests_now()))
        rows = features.compute(diff, prev, self.store.get_static(base), self.facts_now(), tests,
                                self.cfg.src_root, self.is_source, self.history(), self.lang.stem)
        return base, prev, diff, rows

    # ------------------------------------------------------------- select
    def select(self, base: str | None = None, alpha: float | None = None, budget: float | None = None) -> Decision:
        base, prev, diff, rows = self.analyse(base)
        scores = self.model.scores(rows)
        alpha = self.cfg.alpha if alpha is None else alpha
        if not any(self.is_source(f) for f in diff):
            d = Decision({t for t, r in rows.items() if r["forced"]}, "proceed", 0.0, None, "no-source-change",
                         ["no source file changed; only added or changed tests run"], risk_before=0.0)
            self._with_report(d, base, prev, diff, rows, scores)
            if diff:
                # Stored too, so run, learn and explain see this change (E3). Without scores: nothing learns from
                # them. A clean tree (empty diff) is not a change and replaces no decision.
                self._save(d, base, alpha, {})
            return d
        recal = self._recalibrator()
        times = {t: prev.durations.get(t, 1.0) for t in rows}
        if budget is not None:
            sel = budget_select(rows, scores, times, budget * sum(times.values()))
            d = decide(rows, scores, sel, alpha, recal, self.cfg.fallback, mode=f"budget {budget:.0%}")
            risk_reason = d.reasons[0]
        else:
            level = AdaptiveLevel(alpha, self.cfg.aci_gamma, self.store.alpha_t())
            calib = self.store.calibration()
            lam = crc_threshold(calib, level.level) if len(calib) >= math.ceil(1 / max(level.level, 1e-9)) else -2.0
            note = []
            if lam == -2.0:
                lam = UNCALIBRATED_THRESHOLD
                note = [f"not calibrated yet ({len(calib)} labelled changes); using threshold {lam}"]
            sel = threshold_select(rows, scores, lam)
            d = decide(rows, scores, sel, alpha, recal, self.cfg.fallback, threshold=lam)
            risk_reason = d.reasons[0]
            d.reasons = note + d.reasons
        unknowns = self.impact([f for f in diff if self.is_source(f)]).unknowns
        d.reasons += unknowns
        blind = self.without_runtime_evidence(diff, prev)
        if blind:
            # Unknown is not "no dependency": without coverage for these files' tests, the risk of skipping a test
            # cannot be estimated. Run everything and say why.
            d.decision, d.selected = "abstain", set(rows)
            d.residual_risk = residual_risk(scores, d.selected, recal)   # the risk of what now runs (E2)
            # decide()'s sentence describes a selection that no longer runs: keep it and add the risk of what runs.
            d.reasons[d.reasons.index(risk_reason)] = (
                f"{risk_reason}; running every test instead (estimated residual risk {d.residual_risk:.1%})")
            for why in sorted(set(blind.values())):
                fs = sorted(f for f, w in blind.items() if w == why)
                d.reasons.append(f"{why} for {', '.join(fs[:5])}{' and others' if len(fs) > 5 else ''}: "
                                 "static evidence only, running every test (see docs/languages.md)")
        self._with_report(d, base, prev, diff, rows, scores)
        self._save(d, base, alpha, scores)
        return d

    def _save(self, d: Decision, base: str, alpha: float, scores: dict[str, float]) -> int:
        return self.store.save_decision(base=base, head="working-tree", mode=d.mode, alpha=alpha,
                                        alpha_t=self.store.alpha_t(alpha), threshold=d.threshold,
                                        residual_risk=d.residual_risk, risk_before=d.risk_before,
                                        decision=d.decision, selected=d.selected, reasons=d.reasons,
                                        scores=scores, extras=d.extras)

    def without_runtime_evidence(self, diff, prev) -> dict[str, str]:
        """Changed source files whose tests have no runtime evidence, with the reason: no runner configured, or a
        runner whose runs recorded no coverage at all for the file's project (e.g. a missing coverage tool)."""
        # groups of the source files any test executed (a test project may live apart from the code it tests)
        covered = {self.lang.evidence_group(f) for files in (prev.covered.values() if prev else []) for f in files}
        out: dict[str, str] = {}
        for f in diff:
            if not self.is_source(f):
                continue
            if not self.lang.has_runtime_evidence(f):
                out[f] = "no test runner configured"
            elif self.lang.evidence_group(f) not in covered:
                out[f] = "no coverage recorded for this project's tests"
        return out

    def report_context(self, d: Decision | None, base, prev, diff, rows, scores) -> report.Context:
        """The one place a report context is built, so every command gives sections the same inputs."""
        return report.Context(cfg=self.cfg, store=self.store, base=base, prev=prev, diff=diff, rows=rows,
                              scores=scores, decision=d, is_source=self.is_source, facts_now=self.facts_now,
                              impact=self.impact, lang=self.lang)

    def _with_report(self, d: Decision, base, prev, diff, rows, scores) -> Decision:
        d.extras = report.build(self.report_context(d, base, prev, diff, rows, scores))
        return d

    def _recalibrator(self) -> Recalibrator:
        pts = self.store.recal_points()
        return Recalibrator().fit([p[0] for p in pts], [p[1] for p in pts])

    # ------------------------------------------------------------- learn from the full run
    def learn(self) -> dict:
        """Run the full suite on the current tree, derive which tests were truly affected by the last
        analysed change, and update calibration, recalibration and the adaptive level."""
        last = self.store.last_decision()
        if not last:
            raise RuntimeError("no decision to learn from; run `codetwin select` first")
        if self.store.has_outcome(last["id"]):
            raise RuntimeError(f"decision {last['id']} already has an outcome; run `codetwin select` for a new change "
                               "(learning twice from one change would count it twice in the calibration set)")
        if last.get("mode") == "no-source-change":
            # Only tests changed and every changed test ran, so nothing was missed. Such a change says nothing about
            # the risk model: no calibration, recalibration or adaptive-level update (it would shift calibration).
            now = self.changed(last["base"])
            new_tests = (set(now) & set(self.tests_now())) - set(last["selected"])
            if any(self.is_source(f) for f in now) or new_tests:
                raise RuntimeError("the change differs from the one the last `codetwin select` saw (it edited only "
                                   f"{', '.join(last['selected']) or 'tests'}); run `codetwin select` again before "
                                   "`learn`")
            self.store.save_outcome(last["id"], False)
            return {"affected": sorted(last["selected"]), "missed": [],
                    "alpha_t": self.store.alpha_t(self.cfg.alpha), "calibration_size": len(self.store.calibration()),
                    "note": "a change that edits only tests: outcome stored, calibration unchanged"}
        _base, _prev, diff, rows = self.analyse(last["base"])
        no_ev = self.without_runtime_evidence(diff, self.store.get_run(last["base"]))
        blind = [f"{f} ({why})" for f, why in sorted(no_ev.items())]
        if blind:
            raise RuntimeError(f"cannot learn from this change: no runtime evidence for {', '.join(blind[:5])}, so which "
                               "tests it affects is unknown (set [runner] test_command, see docs/languages.md)")
        new = self.lang.run_suite("working-tree")
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
        # One transaction: if learning stops part way, nothing is stored and `learn` can simply run again
        # (calibration_point.decision_id is unique, so a half-stored label could never be completed).
        with self.store.transaction():
            self.store.add_calibration(min(non_forced) if non_forced else math.inf, last["id"])
            calib = self.store.calibration()
            self.store.add_recal_points(((t, scores[t], int(t in affected)) for t in scores
                                         if not rows.get(t, {}).get("forced")), last["id"])
            level = AdaptiveLevel(self.cfg.alpha, self.cfg.aci_gamma, self.store.alpha_t())
            # The adaptive level tracks misses of the *calibrated* threshold only; a budget-mode selection
            # missing a test says nothing about it. Scores and labels above are valid in both modes.
            if last.get("mode", "calibrated") == "calibrated":
                self.store.set_alpha_t(level.update(missed), last["id"])
            self.store.save_outcome(last["id"], missed)
        return {"affected": sorted(affected), "missed": sorted(affected - selected), "alpha_t": level.alpha_t,
                "calibration_size": len(calib)}

    # ------------------------------------------------------------- impact
    def impact(self, files: list[str], base: str | None = None) -> Impact:
        base = base or self.store.latest_run_sha()
        run = self.store.get_run(base) if base else None
        g = build_graph(self.facts_now(), run)
        return impact_of(g, files, self.tests_now())

    def explain(self) -> dict:
        rows = self.store.decisions(limit=1, extras=True)
        if not rows:
            return {"message": "no decision yet"}
        row = rows[0]
        return {k: row[k] for k in ("decision", "mode", "residual_risk", "risk_before", "threshold", "alpha", "reasons",
                                     "selected", "extras")}
