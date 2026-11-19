"""The normalized evidence store: exact round trips, constraints, views and the upgrade from the JSON-blob schema."""
import json
import math
import sqlite3
from importlib import resources

import pytest

from codetwin.evidence.model import FileFacts, TestRun
from codetwin.store import legacy
from codetwin.store.db import Store

RUN = TestRun(sha="a" * 40, returncode="1", wall=2.5,
              durations={"tests/test_b.py": 0.4, "tests/test_a.py": 1.25},
              failing=["tests/test_b.py::test_x", "tests/test_b.py"],
              covered={"tests/test_b.py": {"src/p.py": [1, 2, 9], "src/q.py": [3]},
                       "tests/test_a.py": {},                              # traced, nothing covered
                       "tests/test_c.py": {"src/p.py": [2]}},             # traced, not timed
              import_lines={"src/p.py": [1, 2], "src/q.py": [1]})
FACTS = {"src/p.py": FileFacts(imports=["pkg.q", "pkg.r"], dynamic=["getattr", "importlib"], dyn_lines=[7, 3],
                               defs=[[1, 4, 2], [6, 9, 7]], mod_lines=[1, 5], deps=["src/r.py", "src/q.py"],
                               symbols=[["A", "class", 1, 9], ["A.f", "method", 2, 4], ["g", "function", 6, 9]]),
         "src/q.py": FileFacts(dynamic=["unparsed"])}


def test_run_and_static_facts_round_trip(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        s.save_run(RUN)
        s.save_static(RUN.sha, FACTS)
    with Store(tmp_path / "e.sqlite") as s:                 # reopen: nothing lives only in memory
        got = s.get_run(RUN.sha)
        assert got is not None and got == RUN
        assert list(got.durations) == list(RUN.durations)  # runner order kept
        assert s.get_static(RUN.sha) == FACTS
        assert s.latest_run_sha() == RUN.sha and s.run_shas() == [RUN.sha]
        assert s.get_run("b" * 40) is None and s.get_static("b" * 40) == {}


def test_rerecording_a_revision_replaces_its_run(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        s.save_run(RUN)
        s.save_run(TestRun(sha=RUN.sha, durations={"tests/test_a.py": 1.0}, covered={"tests/test_a.py": {"src/p.py": [1]}}))
        assert s.con.execute("select count(*) from test_run").fetchone()[0] == 1
        assert s.con.execute("select count(*) from coverage_line").fetchone()[0] == 1    # old rows cascaded away
        assert s.get_run(RUN.sha).durations == {"tests/test_a.py": 1.0}


def test_rerecording_static_facts_replaces_the_whole_snapshot(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        s.save_static(RUN.sha, FACTS)
        s.save_static(RUN.sha, {"src/q.py": FACTS["src/q.py"]})        # src/p.py no longer analysed
        assert s.get_static(RUN.sha) == {"src/q.py": FACTS["src/q.py"]}
        assert s.con.execute("select count(*) from evidence_edge").fetchone()[0] == 0


def test_entities_are_stored_once_and_typed(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        s.save_run(RUN)
        s.save_static(RUN.sha, FACTS)
        s.save_static("c" * 40, FACTS)
        kinds = dict(s.con.execute("select name, kind from code_entity where name <> ''"))
        assert kinds == {"A": "class", "A.f": "method", "g": "function"}
        assert s.con.execute("select count(*) from code_entity where kind='file' and path='src/p.py'").fetchone()[0] == 1


def test_evidence_view_types_every_link(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        s.save_run(RUN)
        s.save_static(RUN.sha, FACTS)
        ev = s.evidence(RUN.sha)
    by = {(e["type"], e["src"], e["dst"]) for e in ev}
    assert ("static", "src/p.py", "src/r.py") in by and ("static", "src/p.py", "src/q.py") in by
    assert ("runtime", "tests/test_b.py", "src/q.py") in by and ("runtime", "tests/test_c.py", "src/p.py") in by
    assert ("unresolved", "src/q.py", None) in by                    # unknown is kept, not dropped
    assert {e["source"] for e in ev if e["type"] == "unresolved"} == {"getattr", "importlib", "unparsed"}


def test_tests_covering_a_line(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        s.save_run(RUN)
        assert s.tests_covering(RUN.sha, "src/p.py", 2) == ["tests/test_b.py", "tests/test_c.py"]
        assert s.tests_covering(RUN.sha, "src/p.py", 5) == []


def test_decisions_outcomes_and_learning_history(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        assert s.last_decision() is None
        did = s.save_decision(base=RUN.sha, head="working-tree", mode="calibrated", alpha=0.1, alpha_t=0.1,
                              threshold=0.2, residual_risk=0.05, decision="proceed",
                              selected={"tests/test_b.py"}, reasons=["r1", "r2"],
                              scores={"tests/test_b.py": 0.9, "tests/test_a.py": 0.01})
        last = s.last_decision()
        assert last == {"id": did, "base": RUN.sha, "mode": "calibrated", "selected": ["tests/test_b.py"],
                        "scores": {"tests/test_a.py": 0.01, "tests/test_b.py": 0.9}}
        assert not s.has_outcome(did) and s.decision(did)["missed"] is None
        s.save_outcome(did, True)
        assert s.has_outcome(did) and s.decision(did)["missed"] is True
        assert s.labelled() == [(did, 0.1, 0.1, 1)] and s.counts() == {"decisions": 1, "labelled_decisions": 1}
        for v in (0.3, math.inf):
            s.add_calibration(v, None)
        assert s.calibration() == [0.3, math.inf] and s.calibration(window=1) == [math.inf]
        s.add_recal_points([("tests/test_b.py", 0.9, 1), (None, 0.1, 0)], did)
        assert s.recal_points() == [(0.9, 1), (0.1, 0)]
        assert s.alpha_t() is None and s.alpha_t(0.1) == 0.1
        s.set_alpha_t(0.08, did)
        s.set_alpha_t(0.09, did)
        assert s.alpha_t() == 0.09                                    # the history is kept, the newest wins
        s.add_change_point({"r_prod": 0.2, "n": 3.0}, 1, did)
        assert s.change_points() == [[{"n": 3.0, "r_prod": 0.2}, 1]]


def test_constraints_reject_bad_rows(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        with pytest.raises(sqlite3.IntegrityError):
            s.save_decision(base="x", mode="calibrated", decision="maybe", selected=[])   # verdict domain
        with pytest.raises(sqlite3.IntegrityError):
            s.save_decision(base="x", mode="whatever", decision="proceed", selected=[])  # mode domain
        with pytest.raises(sqlite3.IntegrityError):
            s.save_outcome(12345, False)                                                  # no such decision
        with pytest.raises(sqlite3.IntegrityError):
            s.add_outcomes("x", {"t.py": []}, "gossip")                                    # source domain
        with pytest.raises(ValueError, match="unknown symbol kind"):
            s.save_static("x", {"f.py": FileFacts(symbols=[["X", "macro", 1, 2]])})
        assert s.con.execute("select count(*) from decision").fetchone()[0] == 0           # all rolled back
        assert s.con.execute("select count(*) from file_snapshot").fetchone()[0] == 0
        assert s.save_decision(base="x", mode="budget 30%", decision="abstain", selected=[]) > 0


def test_outcome_history_and_flaky_view(tmp_path):
    with Store(tmp_path / "e.sqlite") as s:
        s.add_outcomes("x", {"t.py": []}, "ci", when=1.0)
        s.add_outcomes("x", {"t.py": ["t.py::b", "t.py::a"]}, "rerun", when=2.0)
        s.add_outcomes("y", {"u.py": []}, "ci", when=3.0)
        h = s.outcomes("t.py")
        assert [(o["passed"], o["failing_cases"], o["source"]) for o in h] == [(True, [], "ci"),
                                                                                (False, ["t.py::a", "t.py::b"], "rerun")]
        assert len(s.outcomes()) == 3
        assert s.flaky_tests() == [{"sha": "x", "test": "t.py", "passes": 1, "failures": 1}]


def _old_database(path):
    """A database as the 0001/0002 code wrote it, with one of everything."""
    con = sqlite3.connect(path)
    con.execute("create table migrations (name text primary key, applied real)")
    for name in ("0001_initial.sql", "0002_test_outcomes.sql"):
        con.executescript(resources.files("codetwin.store.migrations").joinpath(name).read_text())
        con.execute("insert into migrations values (?, 0)", (name,))
    con.execute("insert into runs values (?,?,?,?,?,?,?,?)",
                (RUN.sha, 10.0, RUN.returncode, RUN.wall, json.dumps(RUN.durations), json.dumps(RUN.failing),
                 json.dumps(RUN.covered), json.dumps(RUN.import_lines)))
    for f, x in FACTS.items():
        con.execute("insert into static values (?,?,?)", (RUN.sha, f, json.dumps(x.__dict__)))
    con.execute("insert into test_outcomes (sha, recorded, test, passed, failing_cases, source) values "
                "(?, 10.5, 'tests/test_b.py', 0, ?, 'record')", (RUN.sha, json.dumps(["tests/test_b.py::test_x"])))
    for did, missed in ((3, 0), (7, None)):
        con.execute("insert into decisions values (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (did, 11.0 + did, RUN.sha, "working-tree", "calibrated", 0.1, 0.1, 0.2, 0.04, "proceed",
                     json.dumps(["tests/test_b.py"]), json.dumps([f"reason {did}"])))
        if missed is not None:
            con.execute("insert into outcomes values (?,?,?)", (did, missed, 20.0))
    state = {"alpha_t": 0.12, "calibration": [0.5, math.inf], "recal_points": [[0.9, 1], [0.2, 0]],
             "change_points": [[{"r_prod": 0.3}, 0]], "pending_change_features": {"base": "z"},
             "last_decision": {"id": 7, "base": RUN.sha, "scores": {"tests/test_b.py": 0.9}, "selected": ["tests/test_b.py"],
                               "mode": "calibrated"}}
    con.executemany("insert into state values (?,?)", [(k, json.dumps(v)) for k, v in state.items()])
    con.commit()
    con.close()


def test_upgrade_from_blob_schema_keeps_everything(tmp_path):
    db = tmp_path / "old.sqlite"
    _old_database(db)
    with Store(db) as s:
        assert not set(legacy.OLD_TABLES) & set(s.tables())          # old tables are gone
        assert s.get_run(RUN.sha) == RUN and s.get_static(RUN.sha) == FACTS
        assert [(o["test"], o["passed"], o["recorded"]) for o in s.outcomes()] == [("tests/test_b.py", False, 10.5)]
        assert [d["id"] for d in s.decisions()] == [7, 3]             # ids kept
        assert s.decision(3)["missed"] is False and s.decision(7)["missed"] is None
        assert s.decision(3)["reasons"] == ["reason 3"]
        assert s.last_decision() == {"id": 7, "base": RUN.sha, "mode": "calibrated", "selected": ["tests/test_b.py"],
                                     "scores": {"tests/test_b.py": 0.9}}
        assert s.alpha_t() == 0.12 and s.calibration() == [0.5, math.inf]
        assert s.recal_points() == [(0.9, 1), (0.2, 0)] and s.change_points() == [[{"r_prod": 0.3}, 0]]
        assert s.get_state("pending_change_features") == {"base": "z"}
        assert s.con.execute("pragma foreign_key_check").fetchall() == []
        assert s.con.execute("pragma integrity_check").fetchone()[0] == "ok"
    with Store(db) as s:
        assert s.migrate() == []


def test_failed_migration_step_rolls_back(tmp_path, monkeypatch):
    db = tmp_path / "old.sqlite"
    _old_database(db)

    def boom(store):
        legacy.import_v2(store)
        raise RuntimeError("disk on fire")
    monkeypatch.setitem(legacy.STEPS, "0003_evidence_model.sql", boom)
    with pytest.raises(RuntimeError, match="disk on fire"):
        Store(db)
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    assert "runs" in tables and "decision" not in tables                  # untouched, old data intact
    assert "0003_evidence_model.sql" not in {r[0] for r in con.execute("select name from migrations")}
    con.close()


def test_analysis_history_is_bounded(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from codetwin.store import analyses
    monkeypatch.setattr(analyses, "KEEP", 3)
    cfg = SimpleNamespace(root=tmp_path)
    with Store(tmp_path / "e.sqlite") as s:
        for i in range(5):
            analyses.save_crossrepo(s, cfg, "x" * 40, {"summary": str(i), "packages": []}, [], [])
        assert [h["summary"] for h in analyses.crossrepo_history(s)] == ["4", "3", "2"]


def test_contract_element_kinds_and_diff_cache(tmp_path):
    from types import SimpleNamespace

    from codetwin.contracts.diff import ContractChange
    from codetwin.store import analyses
    C = ContractChange
    assert [analyses.element_kind(c) for c in (
        C("a", "path-removed", "/x", "", True, path="/x"),
        C("a", "parameter-required", "GET /x query q", "", True, path="/x", field="q"),
        C("a", "type-changed", "GET /x query q", "", True, path="/x", field="q"),
        C("a", "type-changed", "User.age", "", True, field="age"),
        C("a", "enum-value-removed", "Role", "", True, field="Role"),
        C("a", "response-removed", "GET /x 404", "", True, path="/x"))] == \
        ["path", "parameter", "parameter", "property", "schema", "response"]
    cfg = SimpleNamespace(root=tmp_path)
    old, new = '{"openapi": "3.0.0", "paths": {"/x": {}}}', '{"openapi": "3.1.0", "paths": {}}'
    ch = [C("api.json", "path-removed", "/x", "path removed", True, path="/x")]
    doc = analyses.ContractDoc("api.json", old, new, json.loads(old), json.loads(new), ch)
    with Store(tmp_path / "e.sqlite") as s:
        for _ in range(2):
            analyses.save_contracts(s, cfg, "b" * 40, {"summary": "s", "unknowns": ["u"]}, [doc],
                                    [analyses.Scope("this repository", str(tmp_path), "analysed", is_self=True)],
                                    [("this repository", ch[0], "src/a.py", 3, "path-literal")], [])
        assert s.con.execute("select count(*) from contract_diff").fetchone()[0] == 1
        assert s.con.execute("select count(*) from contract_change").fetchone()[0] == 1
        assert [r["spec_version"] for r in analyses.api_history(s, "api.json")] == ["3.0.0", "3.1.0"]
        last = s.con.execute("select max(id) from impact_analysis").fetchone()[0]
        assert analyses.breaking_matrix(s, last) == [{"change_id": 1, "location": "/x", "check_id": "path-removed",
                                                      "repository": ".", "state": "affected", "sites": 1, "tests": 0}]
        with pytest.raises(sqlite3.IntegrityError):                     # a site must point at a real change
            s.con.execute("insert into contract_site (target_id, change_id, file_id, line, how) values (1, 99, 1, 1, "
                          "'path-literal')")


def test_decisions_reads_children_in_one_query_per_table(tmp_path) -> None:
    """Listing 30 decisions costs 3 queries (rows, selections, reasons), not 2 per row (#91)."""
    from codetwin.store.db import Store
    with Store(tmp_path / "e.db") as st:
        for i in range(30):
            st.save_decision(base="b" * 40, head="working-tree", mode="calibrated", alpha=0.1, alpha_t=0.1,
                             threshold=0.5, residual_risk=0.01, decision="proceed", selected=[f"t{i}", "t_all"],
                             reasons=[f"why {i}", "and"], scores={f"t{i}": 0.9})
        seen: list[str] = []
        st.con.set_trace_callback(seen.append)
        rows = st.decisions(limit=30)
        st.con.set_trace_callback(None)
        assert len([q for q in seen if q.lstrip().lower().startswith("select")]) == 3
        assert rows[0]["selected"] == ["t29", "t_all"] and rows[0]["reasons"] == ["why 29", "and"]
        assert rows[-1]["selected"] == ["t0", "t_all"] and st.decisions(limit=1, ids=[999]) == []
