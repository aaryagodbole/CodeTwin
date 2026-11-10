import math

from codetwin.risk.calibration import AdaptiveLevel, crc_threshold
from codetwin.risk.model import RiskModel
from codetwin.risk.residual import residual_risk
from codetwin.selection import budget_select, decide, threshold_select


def test_crc_threshold_needs_enough_changes():
    assert crc_threshold([0.6] * 5, 0.10) == -1.0          # 1/(n+1) > alpha: infeasible
    lam = crc_threshold([0.6, 0.7, 0.8, 0.9, 0.95, 0.6, 0.65, 0.7, 0.75, 0.8, math.inf, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9], 0.10)
    assert 0 < lam <= 0.6                                    # no calibration change may be missed


def test_adaptive_level_moves_against_errors():
    lv = AdaptiveLevel(0.1, gamma=0.02)
    lv.update(missed=True)
    assert lv.alpha_t < 0.1
    lv.update(missed=False)
    assert abs(lv.alpha_t - (0.1 - 0.018 + 0.002)) < 1e-9


def test_residual_risk_and_decision():
    scores = {"a": 0.9, "b": 0.2, "c": 0.01}
    assert residual_risk(scores, {"a", "b", "c"}) == 0
    assert abs(residual_risk(scores, {"a"}) - (1 - 0.8 * 0.99)) < 1e-9
    rows = {t: {"forced": False, "cov_file": t != "c"} for t in scores}
    d = decide(rows, scores, {"a"}, alpha=0.1)
    assert d.decision == "abstain" and d.selected == {"a", "b"}
    assert decide(rows, scores, {"a", "b"}, alpha=0.1).decision == "proceed"


def test_selection_modes():
    rows = {"a": {"forced": True}, "b": {"forced": False}, "c": {"forced": False}}
    scores = {"a": 0.1, "b": 0.9, "c": 0.5}
    assert threshold_select(rows, scores, 0.6) == {"a", "b"}
    assert budget_select(rows, scores, {"a": 1, "b": 1, "c": 1}, 2.0) == {"a", "b"}


def test_prior_model_orders_line_coverage_first():
    m = RiskModel()
    base = {"cov_line": 0, "cov_func": 0, "cov_file": 0, "static_inv_dist": 0, "name_match": 0, "cochange": 0, "test_changed": 0}
    assert m.score({**base, "cov_line": 1, "cov_file": 1}) > m.score({**base, "cov_file": 1}) > m.score(base)
