"""The Selection policy is pure: every paper rule is tested here without git, a store or a model."""
from __future__ import annotations

import math

import pytest

from codetwin.risk.calibration import AdaptiveLevel
from codetwin.risk.ledger import CalibrationState
from codetwin.risk.residual import Recalibrator
from codetwin.selection import UNCALIBRATED_THRESHOLD, choose, only_tests


def _rows(**cov_file: int) -> dict[str, dict]:
    return {t: {"forced": False, "cov_file": c} for t, c in cov_file.items()}


def _state(calibration: list[float] | None = None, alpha: float = 0.1, labels: list[int] | None = None) -> CalibrationState:
    return CalibrationState(calibration=calibration or [], level=AdaptiveLevel(alpha), recalibrator=Recalibrator(),
                            labels=labels or [])


ROWS = _rows(a=1, b=0, c=0)
SCORES = {"a": 0.9, "b": 0.02, "c": 0.01}


def test_uncalibrated_uses_the_fixed_threshold_and_says_so() -> None:
    d = choose(ROWS, SCORES, _state(), alpha=0.1)
    assert d.threshold == UNCALIBRATED_THRESHOLD and d.selected == {"a"} and d.decision == "proceed"
    assert d.reasons[0].startswith("not calibrated yet (0 labelled changes)")
    assert d.residual_risk == pytest.approx(1 - 0.98 * 0.99) and d.risk_before == d.residual_risk


def test_calibration_that_saw_affected_tests_at_score_zero_selects_every_test() -> None:
    # 10 labelled changes whose affected tests scored 0: only threshold 0 keeps the risk under 10%
    d = choose(ROWS, SCORES, _state([0.0] * 10), alpha=0.1)
    assert d.threshold == 0.0 and d.selected == set(ROWS) and d.residual_risk == 0.0


def test_a_threshold_of_minus_one_selects_every_test() -> None:
    from codetwin.selection import threshold_select
    assert threshold_select(ROWS, SCORES, -1.0) == set(ROWS)


def test_abstains_to_the_broader_selection_when_the_risk_is_above_alpha() -> None:
    d = choose(ROWS, SCORES, _state(), alpha=0.01, fallback="full")
    assert d.decision == "abstain" and d.selected == set(ROWS) and d.risk_before > 0.01 and d.residual_risk == 0.0
    assert "running the broader full selection" in d.reasons[1]


def test_budget_mode_never_reads_the_threshold() -> None:
    d = choose(ROWS, SCORES, _state([math.inf] * 50), alpha=0.5, budget=0.5, times={"a": 1.0, "b": 1.0, "c": 1.0})
    assert d.mode == "budget 50%" and d.threshold is None and "a" in d.selected


def test_files_without_runtime_evidence_run_everything_with_the_risk_of_what_runs() -> None:
    d = choose(ROWS, SCORES, _state(), alpha=0.1, blind={"src/x.go": "no test runner configured"},
               notes=["an unknown"])
    assert d.decision == "abstain" and d.selected == set(ROWS) and d.residual_risk == 0.0 and d.risk_before > 0
    assert d.reasons[1].endswith("running every test instead (estimated residual risk 0.0%)")
    assert d.reasons[2] == "an unknown" and d.reasons[-1].startswith("no test runner configured for src/x.go")


def test_a_change_to_tests_only_runs_the_forced_tests() -> None:
    rows = {"t1": {"forced": True}, "t2": {"forced": False}}
    d = only_tests(rows, ["thin history"])
    assert d.selected == {"t1"} and d.mode == "no-source-change" and d.residual_risk == 0.0
    assert d.reasons == ["no source file changed; only added or changed tests run", "thin history"]


def test_too_few_recalibration_examples_are_a_stated_note() -> None:
    assert _state(labels=[1, 0, 0]).notes[0].startswith("risk scores are not recalibrated yet: 1 affected and 2")
    assert _state(labels=[1] * 5 + [0] * 5).notes == [] and _state().notes == []
