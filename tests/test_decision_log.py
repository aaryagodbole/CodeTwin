"""Decision log (#96, E1 to E4 of #71): the stored risk describes the stored selection, test-only changes and report
sections are stored, and migration 0005 keeps every existing decision."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

import pytest

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.risk.residual import residual_risk
from codetwin.selection import decide
from codetwin.store import db as store_db
from codetwin.store.db import Store


def _engine(toy_repo: Path) -> Engine:
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    return Engine(toy_repo)


def _edit_source(toy_repo: Path) -> None:
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))


# ----------------------------------------------------------------------------------------- E1: abstain to broader
def test_abstain_keeps_the_risk_before_and_stores_the_risk_of_what_runs() -> None:
    rows = {"a": {"forced": False, "cov_file": 1}, "b": {"forced": False, "cov_file": 0}}
    scores = {"a": 0.5, "b": 0.1}
    d = decide(rows, scores, set(), alpha=0.1)            # nothing selected: risk 55% > 10%, widen to file coverage
    assert d.decision == "abstain" and d.selected == {"a"}
    assert d.risk_before == pytest.approx(residual_risk(scores, set()))
    assert d.residual_risk == pytest.approx(residual_risk(scores, {"a"}))
    assert f"{d.risk_before:.1%}" in d.reasons[0] and f"{d.residual_risk:.1%}" in d.reasons[0]
    out = d.to_dict()
    assert out["risk_before"] == round(d.risk_before, 4) and out["residual_risk"] == round(d.residual_risk, 4)


def test_proceed_has_one_risk() -> None:
    d = decide({"a": {"forced": False, "cov_file": 1}}, {"a": 0.01}, {"a"}, alpha=0.1)
    assert d.decision == "proceed" and d.risk_before == d.residual_risk


# ------------------------------------------------------------------- E2: blind-evidence override, stored decision
def test_blind_override_stores_the_risk_of_every_test(toy_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _engine(toy_repo) as eng:
        _edit_source(toy_repo)
        monkeypatch.setattr(eng, "without_runtime_evidence",
                            lambda diff, prev: {"src/shop/price.py": "no test runner configured"})
        d = eng.select()
        stored = eng.store.decision(eng.store.last_decision()["id"])
        assert stored["decision"] == "abstain" and set(stored["selected"]) == set(eng.store.scores(stored["id"]))
        recal = eng._recalibrator()
        assert stored["residual_risk"] == pytest.approx(residual_risk(eng.store.scores(stored["id"]),
                                                                      set(stored["selected"]), recal))
        assert stored["residual_risk"] == pytest.approx(d.residual_risk)
        assert stored["risk_before"] == pytest.approx(d.risk_before)


def test_stored_decision_matches_the_returned_one(toy_repo: Path) -> None:
    with _engine(toy_repo) as eng:
        _edit_source(toy_repo)
        d = eng.select()
        stored = eng.store.decision(eng.store.last_decision()["id"])
        assert stored["decision"] == d.decision and set(stored["selected"]) == d.selected
        assert stored["residual_risk"] == pytest.approx(d.residual_risk)
        assert stored["risk_before"] == pytest.approx(d.risk_before)
        assert stored["reasons"] == d.reasons


# ----------------------------------------------------------------------------------- E3: change that edits tests only
def test_test_only_change_is_stored_and_teaches_no_calibration(toy_repo: Path) -> None:
    with _engine(toy_repo) as eng:
        t = toy_repo / "tests/test_price.py"
        t.write_text(t.read_text() + "\ndef test_more():\n    assert True\n")
        d = eng.select()
        assert d.mode == "no-source-change" and d.selected == {"tests/test_price.py"}
        last = eng.store.last_decision()
        assert last is not None and last["mode"] == "no-source-change" and last["selected"] == ["tests/test_price.py"]
        calib, recal = len(eng.store.calibration()), len(eng.store.recal_points())
        out = eng.learn()
        assert out["missed"] == [] and out["affected"] == ["tests/test_price.py"]
        assert eng.store.has_outcome(last["id"])
        assert (len(eng.store.calibration()), len(eng.store.recal_points())) == (calib, recal)
        assert eng.explain()["mode"] == "no-source-change"


# ----------------------------------------------------------------------------------------------- E4: report sections
def test_report_sections_round_trip(toy_repo: Path) -> None:
    with _engine(toy_repo) as eng:
        _edit_source(toy_repo)
        d = eng.select()
        assert d.extras, "the toy change should produce report sections"
        stored = eng.store.decision(eng.store.last_decision()["id"])
        assert stored["extras"] == json.loads(json.dumps(store_db._finite_json(d.extras)))
        assert eng.explain()["extras"] == stored["extras"]


def test_extras_with_non_finite_numbers_are_stored_as_null(tmp_path: Path) -> None:
    with Store(tmp_path / "s.db") as s:
        did = s.save_decision(base="b" * 40, mode="calibrated", decision="proceed", selected=[],
                              extras={"x": {"v": math.inf, "w": [math.nan, 1.0], "tags": {"b", "a"}}})
        assert s.decision(did)["extras"] == {"x": {"v": None, "w": [None, 1.0], "tags": ["a", "b"]}}


# ---------------------------------------------------------------------------------------------------- migration 0005
def test_migration_0005_keeps_existing_decisions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "old.db"
    every = store_db._migrations()
    monkeypatch.setattr(store_db, "_migrations", lambda: [m for m in every if m[0] < "0005"])
    with Store(path) as s:
        ids = [s.save_decision(base="b" * 40, mode="calibrated", alpha=0.1, residual_risk=0.02, decision="proceed",
                               selected=["tests/a.py", "tests/b.py"], reasons=["r1", "r2"],
                               scores={"tests/a.py": 0.3, "tests/c.py": 0.1}) for _ in range(3)]
        s.save_outcome(ids[0], False)
        s.add_calibration(0.3, ids[0])
        before = {t: s.con.execute(f"select count(*) from {t}").fetchone()[0]  # noqa: S608 (constant names)
                  for t in ("decision", "decision_selection", "decision_reason", "decision_score", "decision_outcome",
                            "calibration_point")}
    monkeypatch.setattr(store_db, "_migrations", lambda: every)
    with Store(path) as s:
        after = {t: s.con.execute(f"select count(*) from {t}").fetchone()[0] for t in before}  # noqa: S608
        assert after == before
        assert s.con.execute("pragma foreign_keys").fetchone()[0] == 1
        assert s.con.execute("pragma foreign_key_check").fetchall() == []
        assert [d["id"] for d in s.decisions()] == sorted(ids, reverse=True)
        assert s.decision(ids[1])["reasons"] == ["r1", "r2"] and s.decision(ids[1])["risk_before"] is None
        assert len(s.labelled()) == 1
        # deleting a decision still cascades to its child rows (the rebuilt table keeps the references)
        s.con.execute("delete from decision where id=?", (ids[2],))
        assert s.con.execute("select count(*) from decision_selection where decision_id=?", (ids[2],)).fetchone()[0] == 0
        # the new mode is allowed, other modes are still refused
        assert s.save_decision(base="b" * 40, mode="no-source-change", decision="proceed", selected=[]) > 0
        with pytest.raises(sqlite3.IntegrityError):
            s.save_decision(base="b" * 40, mode="whatever", decision="proceed", selected=[])
