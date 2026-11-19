"""The Calibration ledger keeps the learning rules: one label per decision, one transaction, alpha_t moves only for
calibrated decisions, forced tests teach nothing."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from codetwin.risk.ledger import CalibrationLedger
from codetwin.store.db import Store


def _decision(st: Store, mode: str = "calibrated") -> int:
    return st.save_decision(base="b" * 40, head="working-tree", mode=mode, alpha=0.1, alpha_t=0.1, threshold=0.5,
                            residual_risk=0.0, decision="proceed", selected=["a"], reasons=[],
                            scores={"a": 0.9, "b": 0.2, "f": 0.1})


def test_a_label_stores_everything_once(tmp_path: Path) -> None:
    with Store(tmp_path / "e.db") as st:
        led = CalibrationLedger(st, alpha=0.1, gamma=0.02)
        did = _decision(st)
        lab = led.label(did, "calibrated", {"a": 0.9, "b": 0.2, "f": 0.1}, ["a"], affected={"a", "b", "f"},
                        forced={"f"})
        assert lab.missed and lab.calibration_size == 1 and st.calibration() == [0.2]     # forced f left out
        assert lab.alpha_t == pytest.approx(0.1 + 0.02 * (0.1 - 1.0)) and st.alpha_t() == pytest.approx(lab.alpha_t)
        assert sorted(st.recal_points()) == [(0.2, 1), (0.9, 1)]
        with pytest.raises(RuntimeError, match="already has an outcome"):
            led.label(did, "calibrated", {}, [], set(), set())


def test_budget_decisions_do_not_move_the_adaptive_level(tmp_path: Path) -> None:
    with Store(tmp_path / "e.db") as st:
        led = CalibrationLedger(st, alpha=0.1, gamma=0.02)
        lab = led.label(_decision(st, "budget 25%"), "budget 25%", {"a": 0.9}, ["a"], affected=set(), forced=set())
        assert st.alpha_t() is None and lab.alpha_t == 0.1 and st.calibration() == [math.inf]


def test_a_failed_label_stores_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with Store(tmp_path / "e.db") as st:
        led = CalibrationLedger(st, alpha=0.1, gamma=0.02)
        did = _decision(st)

        def boom(*_a: object, **_k: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(st, "save_outcome", boom)
        with pytest.raises(OSError):
            led.label(did, "calibrated", {"a": 0.9}, ["a"], affected={"a"}, forced=set())
        assert st.calibration() == [] and st.recal_points() == [] and st.alpha_t() is None


def test_state_reaches_the_level_before_using_a_threshold(tmp_path: Path) -> None:
    with Store(tmp_path / "e.db") as st:
        led = CalibrationLedger(st, alpha=0.1, gamma=0.02)
        assert led.state().threshold is None                    # 0 < 1/0.1 labelled changes
        for _ in range(10):
            led.label(_decision(st), "calibrated", {"a": 0.9, "b": 0.2}, ["a", "b"], affected={"a"}, forced=set())
        assert led.state().threshold is not None
