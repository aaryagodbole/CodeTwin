"""The Calibration ledger: what CodeTwin has learned from outcomes, behind one interface.

It owns the calibration set (the smallest affected score per labelled change, for conformal risk control), the
recalibration points (scores and whether each test was affected, for the isotonic map), the adaptive level
alpha_t (ACI) and the decision outcomes. The rules that keep them consistent live here, not in the callers:

- a decision is labelled at most once, and everything for one label is stored in one transaction, so a label
  that stops part way stores nothing and can simply be repeated;
- the adaptive level moves only after a calibrated-mode decision: a budget-mode selection missing a test says
  nothing about the calibrated threshold;
- a change that edits only tests stores its outcome and teaches nothing (it would shift calibration);
- the isotonic recalibration is used only with enough examples of both kinds (`Recalibrator.MIN_EACH`).

`state()` gives the selection policy what it needs; `label()` and `label_unscored()` are the only writers.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .calibration import AdaptiveLevel, crc_threshold
from .residual import Recalibrator


@dataclass
class CalibrationState:
    """A snapshot of the ledger at decision time."""
    calibration: list[float]          # smallest affected score of each labelled change (math.inf: none affected)
    level: AdaptiveLevel              # target alpha and the adaptive level alpha_t
    recalibrator: Recalibrator        # identity until there are enough examples
    labels: list[int]                 # affected (1) / unaffected (0) of every recalibration point

    @property
    def threshold(self) -> float | None:
        """The conformal threshold at the adaptive level, or None while there are too few labelled changes to
        reach that level (n >= 1/level). -1.0 means no threshold qualifies: select every test."""
        need = math.ceil(1 / max(self.level.level, 1e-9))
        return crc_threshold(self.calibration, self.level.level) if len(self.calibration) >= need else None

    @property
    def notes(self) -> list[str]:
        """What weakens the risk estimate: too few examples for the recalibration."""
        if not self.labels or Recalibrator.enough(self.labels):
            return []
        pos = sum(1 for x in self.labels if x)
        return [f"risk scores are not recalibrated yet: {pos} affected and {len(self.labels) - pos} unaffected test "
                f"examples, at least {Recalibrator.MIN_EACH} of each are needed (`codetwin learn`)"]


@dataclass
class Label:
    """What one `label()` stored."""
    missed: bool
    alpha_t: float
    calibration_size: int


class CalibrationLedger:
    """Reads and writes the learned state in the evidence store."""

    def __init__(self, store: Any, alpha: float, gamma: float):
        self.store = store
        self.alpha = alpha
        self.gamma = gamma

    def state(self, alpha: float | None = None) -> CalibrationState:
        alpha = self.alpha if alpha is None else alpha
        pts = self.store.recal_points()
        labels = [p[1] for p in pts]
        return CalibrationState(calibration=self.store.calibration(),
                                level=AdaptiveLevel(alpha, self.gamma, self.store.alpha_t()),
                                recalibrator=Recalibrator().fit([p[0] for p in pts], labels), labels=labels)

    def recalibrator(self) -> Recalibrator:
        pts = self.store.recal_points()
        return Recalibrator().fit([p[0] for p in pts], [p[1] for p in pts])

    def alpha_t(self, alpha: float | None = None) -> float:
        """The adaptive level now (the target until the first calibrated outcome)."""
        level = self.store.alpha_t(self.alpha if alpha is None else alpha)
        return self.alpha if level is None else level

    def size(self) -> int:
        return len(self.store.calibration())

    def labelled(self, decision_id: int) -> bool:
        return self.store.has_outcome(decision_id)

    def label(self, decision_id: int, mode: str, scores: dict[str, float], selected: Iterable[str],
              affected: set[str], forced: set[str]) -> Label:
        """Store the outcome of a decision and learn from it, in one transaction.

        `scores` are the scores stored with the decision, `affected` the tests the full run showed the change
        reached, and `forced` the tests that always run (added or changed tests): they carry no information about
        the model, so they are left out of calibration and recalibration."""
        if self.labelled(decision_id):
            raise RuntimeError(f"decision {decision_id} already has an outcome; run `codetwin select` for a new "
                               "change (learning twice from one change would count it twice in the calibration set)")
        missed = bool(affected - set(selected))
        non_forced = [scores[t] for t in affected if t in scores and t not in forced]
        with self.store.transaction():
            self.store.add_calibration(min(non_forced) if non_forced else math.inf, decision_id)
            self.store.add_recal_points(((t, s, int(t in affected)) for t, s in scores.items() if t not in forced),
                                        decision_id)
            level = AdaptiveLevel(self.alpha, self.gamma, self.store.alpha_t())
            if mode == "calibrated":
                self.store.set_alpha_t(level.update(missed), decision_id)
            self.store.save_outcome(decision_id, missed)
            size = self.size()
        return Label(missed=missed, alpha_t=level.alpha_t, calibration_size=size)

    def label_unscored(self, decision_id: int) -> Label:
        """Store the outcome of a change that edited only tests: nothing missed, nothing learned."""
        if self.labelled(decision_id):
            raise RuntimeError(f"decision {decision_id} already has an outcome; run `codetwin select` for a new change")
        self.store.save_outcome(decision_id, False)
        return Label(missed=False, alpha_t=self.alpha_t(), calibration_size=self.size())
