"""Ties the layers together: record evidence, analyse a change, select tests, learn from outcomes."""
from __future__ import annotations

from pathlib import Path
from typing import Self

from . import config as cfgmod
from . import lang as langmod
from . import report
from .change import ChangeContext
from .evidence import diff as diffmod
from .evidence import history
from .evidence.model import TestRun, incomplete_code
from .graph.impact import Impact
from .risk.ledger import CalibrationLedger
from .risk.model import RiskModel
from .selection import UNCALIBRATED_THRESHOLD, Decision, choose, only_tests
from .store.db import Store

__all__ = ["UNCALIBRATED_THRESHOLD", "ChangeContext", "Engine", "affected_tests"]

HISTORY_COMMITS = 300          # first-parent commits read for co-change evidence


class Engine:
    def __init__(self, root: str | Path = "."):
        self.cfg = cfgmod.load(root)
        self.root = self.cfg.root
        self.lang = langmod.get(self.cfg)
        self.store = Store(self.cfg.db_path)
        self._model: RiskModel | None = None
        self._history: dict[str, tuple[list[list[str]], str | None]] = {}

    @property
    def model(self) -> RiskModel:
        """Loaded on first use, so a broken model.json stops only the commands that score tests."""
        if self._model is None:
            self._model = RiskModel.load(self.cfg.state_dir / "model.json")
        return self._model

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

    def history(self, base: str | None = None) -> list[list[str]]:
        """Files of the last 300 first-parent commits up to `base` (default HEAD), oldest first, for co-change.

        Up to the recorded base, not HEAD: commits after it belong to the change being analysed, and counting them
        would let the change explain itself (E5). Empty when git cannot read it; `history_note` says why.
        """
        return self._read_history(base or "HEAD")[0]

    def _read_history(self, rev: str) -> tuple[list[list[str]], str | None]:
        """(commits, git error); read once per revision for this engine."""
        if rev not in self._history:
            try:
                self._history[rev] = (history.commits_until(self.root, rev, HISTORY_COMMITS), None)
            except RuntimeError as e:
                self._history[rev] = ([], (str(e).splitlines() or ["?"])[-1])
        return self._history[rev]

    def history_note(self, base: str | None = None) -> str | None:
        """Why co-change evidence up to `base` is missing or thin (git error, shallow clone), or None."""
        commits, error = self._read_history(base or "HEAD")
        if error:
            return f"git history is not available ({error}): no co-change evidence"
        n = len(commits)
        if n >= HISTORY_COMMITS:
            return None                              # a full window: whether the clone is shallow does not matter
        try:
            shallow = diffmod.git(self.root, "rev-parse", "--is-shallow-repository").strip() == "true"
        except RuntimeError:
            shallow = False
        if shallow:
            return (f"shallow clone: co-change evidence comes from only {n} commit(s); fetch the full history "
                    "(actions/checkout: fetch-depth: 0)")
        return None

    # ------------------------------------------------------------- record
    def record(self) -> TestRun:
        """Run the full suite with per-test coverage on the current checkout and store it as evidence."""
        sha = self.head()
        run = self.lang.run_suite(sha)
        if run.incomplete:
            earlier = self.store.run_returncode(sha)
            if earlier is not None and not incomplete_code(earlier):
                # Never replace a complete run of this commit with a partial one: keep the evidence that is there.
                run.notes.append(f"the test run did not complete ({run.returncode}); kept the earlier complete run of "
                                 f"{sha[:10]}. Fix the cause (a hanging or very slow test, a collection error) and "
                                 "record again")
                run.stored = False
                return run
            run.notes.append(f"the test run did not complete ({run.returncode}); it is stored but `select` will not use "
                             "it as the base. Fix the cause (a hanging or very slow test, a collection error) and run "
                             "`codetwin record` again")
        facts = self.facts_now()
        # One transaction: a crash between the two must not leave a run without its static facts (E6).
        with self.store.transaction():
            self.store.save_run(run)
            self.store.save_static(sha, facts)
        return run

    # ------------------------------------------------------------- the change
    def change(self, base: str | None = None, require_run: bool = True) -> ChangeContext:
        """The change of the working tree against a recorded commit (default: the newest complete run).

        Raises RuntimeError when nothing usable is recorded; the CLI prints it and exits with 2. With
        `require_run=False` (commands that also work without a recording, such as contracts) the base falls back
        to HEAD and the context has no run.
        """
        chosen = base is not None                    # the caller named the base: nothing was skipped on their behalf
        base = base or self.store.latest_run_sha()
        if not base:
            if not require_run:
                return ChangeContext(self, "HEAD", None, chosen=chosen)
            bad = self.store.latest_run_incomplete()
            if bad:
                raise RuntimeError(f"the recorded run of {bad[0][:10]} did not complete ({bad[1]}), so it cannot be "
                                   "the base; fix the cause and run `codetwin record` again")
            raise RuntimeError("no recorded run yet; run `codetwin record` on a clean checkout first")
        prev = self.store.get_run(base)
        if prev is None and require_run:
            raise RuntimeError(f"no recorded run for {base[:10]}; run `codetwin record` there first")
        return ChangeContext(self, base, prev, chosen=chosen)

    @property
    def ledger(self) -> CalibrationLedger:
        return CalibrationLedger(self.store, self.cfg.alpha, self.cfg.aci_gamma)

    # ------------------------------------------------------------- select
    def select(self, base: str | None = None, alpha: float | None = None, budget: float | None = None) -> Decision:
        """Decide which tests to run for the working tree's change, store the decision and return it."""
        ch = self.change(base)
        scores = self.model.scores(ch.rows)
        alpha = self.cfg.alpha if alpha is None else alpha
        if not ch.source_changed:
            d = only_tests(ch.rows, ch.evidence_notes)
            self._with_report(d, ch, scores)
            if ch.diff:
                # Stored too, so run, learn and explain see this change (E3). Without scores: nothing learns from
                # them. A clean tree (empty diff) is not a change and replaces no decision.
                self._save(d, ch.base, alpha, {})
            return d
        state = self.ledger.state(alpha)
        times = {t: ch.prev.durations.get(t, 1.0) for t in ch.rows} if ch.prev else {}
        d = choose(ch.rows, scores, state, alpha=alpha, fallback=self.cfg.fallback, budget=budget, times=times,
                   blind=ch.without_runtime_evidence,
                   notes=[*ch.impact().unknowns, *ch.evidence_notes, *state.notes])
        self._with_report(d, ch, scores)
        self._save(d, ch.base, alpha, scores)
        return d

    def _save(self, d: Decision, base: str, alpha: float, scores: dict[str, float]) -> int:
        return self.store.save_decision(base=base, head="working-tree", mode=d.mode, alpha=alpha,
                                        alpha_t=self.store.alpha_t(alpha), threshold=d.threshold,
                                        residual_risk=d.residual_risk, risk_before=d.risk_before,
                                        decision=d.decision, selected=d.selected, reasons=d.reasons,
                                        scores=scores, extras=d.extras)

    def report_context(self, change: ChangeContext, d: Decision | None, rows: dict | None = None,
                       scores: dict | None = None) -> report.Context:
        """The one place a report context is built, so every command gives sections the same inputs."""
        return report.Context.of(change, d, change.rows if rows is None else rows, scores or {})

    def _with_report(self, d: Decision, change: ChangeContext, scores: dict[str, float]) -> Decision:
        d.extras = report.build(self.report_context(change, d, change.rows, scores))
        return d

    # ------------------------------------------------------------- learn from the full run
    def learn(self) -> dict:
        """Run the full suite on the current tree, derive which tests were truly affected by the last
        analysed change, and update calibration, recalibration and the adaptive level."""
        last = self.store.last_decision()
        if not last:
            raise RuntimeError("no decision to learn from; run `codetwin select` first")
        ledger = self.ledger
        if ledger.labelled(last["id"]):
            raise RuntimeError(f"decision {last['id']} already has an outcome; run `codetwin select` for a new change "
                               "(learning twice from one change would count it twice in the calibration set)")
        ch = self.change(last["base"])
        if last.get("mode") == "no-source-change":
            # Only tests changed and every changed test ran, so nothing was missed. Such a change says nothing about
            # the risk model: no calibration, recalibration or adaptive-level update (it would shift calibration).
            new_tests = (set(ch.diff) & set(ch.tests_now)) - set(last["selected"])
            if ch.source_changed or new_tests:
                raise RuntimeError("the change differs from the one the last `codetwin select` saw (it edited only "
                                   f"{', '.join(last['selected']) or 'tests'}); run `codetwin select` again before "
                                   "`learn`")
            lab = ledger.label_unscored(last["id"])
            return {"affected": sorted(last["selected"]), "missed": [], "alpha_t": lab.alpha_t,
                    "calibration_size": lab.calibration_size,
                    "note": "a change that edits only tests: outcome stored, calibration unchanged"}
        blind = [f"{f} ({why})" for f, why in sorted(ch.without_runtime_evidence.items())]
        if blind:
            raise RuntimeError(f"cannot learn from this change: no runtime evidence for {', '.join(blind[:5])}, so which "
                               "tests it affects is unknown (set [runner] test_command, see docs/languages.md)")
        new = self.lang.run_suite("working-tree")
        if new.incomplete:
            # Partial coverage would label affected tests as unaffected: store nothing, so learn can run again.
            raise RuntimeError(f"the full test run did not complete ({new.returncode}), so which tests the change "
                               "affected is unknown; nothing was learned. Fix the cause and run `codetwin learn` again")
        affected = affected_tests(ch, new)
        selected = set(last["selected"])
        forced = {t for t, r in ch.rows.items() if r.get("forced")}
        lab = ledger.label(last["id"], last.get("mode", "calibrated"), last["scores"], selected, affected, forced)
        return {"affected": sorted(affected), "missed": sorted(affected - selected), "alpha_t": lab.alpha_t,
                "calibration_size": lab.calibration_size}

    # ------------------------------------------------------------- impact
    def impact(self, files: list[str], base: str | None = None) -> Impact:
        """Tests that reach `files` in the working tree, with the runtime evidence of `base` (default: newest)."""
        return self.change(base, require_run=False).impact(files)

    def explain(self) -> dict:
        rows = self.store.decisions(limit=1, extras=True)
        if not rows:
            return {"message": "no decision yet"}
        row = rows[0]
        return {k: row[k] for k in ("decision", "mode", "residual_risk", "risk_before", "threshold", "alpha", "reasons",
                                     "selected", "extras")}


def affected_tests(change: ChangeContext, new: TestRun) -> set[str]:
    """The ground truth for `learn`: tests whose run over the changed tree executed a changed line (or imported a
    module at a changed load-time line), plus the added and changed tests."""
    affected: set[str] = set()
    for f, d in change.diff.items():
        if not change.is_source(f) or d.status == "D":
            continue
        for t, files in new.covered.items():
            if set(d.new) & set(files.get(f, [])):
                affected.add(t)
        if set(d.new) & set(new.import_lines.get(f, [])):
            affected |= {t for t, files in new.covered.items() if f in files}
    return affected | {t for t, r in change.rows.items() if r["test_changed"]}
