"""Data steps of migrations: Python that runs inside a migration's transaction, after its SQL.

``STEPS`` maps a migration file name to a function taking the Store. A step must be idempotent with respect to an
empty source (fresh databases run every step) and must not commit; Store.migrate commits once, after the step.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any

from ..evidence.model import FileFacts, TestRun

# A codetwin.store.db.Store. Not imported: db imports this module to run the data steps of its migrations.
Store = Any

OLD_TABLES = ("runs", "static", "decisions", "outcomes", "state", "test_outcomes")


def _has(store: Store, table: str) -> bool:
    return store.con.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone() is not None


def import_v2(store: Store) -> None:
    """Copy the JSON-blob tables of 0001/0002 into the normalized tables of 0003, then drop them.

    Decision ids are kept, so outcomes and the last decision still point at the right rows. Learning histories that
    0001 kept as lists in `state` (calibration, recal_points, change_points) are imported in order with no decision
    (it was not recorded); `last_decision.scores` becomes the scores of that decision.
    """
    con = store.con
    if _has(store, "runs"):
        for sha, rec, rc, wall, dur, fail, cov, imp in con.execute(
                "select sha, recorded, returncode, wall, durations, failing, covered, import_lines from runs "
                "order by recorded").fetchall():
            run = TestRun(sha=sha, returncode=rc, wall=wall or 0.0, durations=json.loads(dur), failing=json.loads(fail),
                          covered=json.loads(cov), import_lines=json.loads(imp))
            # save_run would also append a 'record' outcome; 0002 already holds those rows (copied below)
            store.save_run(run, recorded=rec)
            con.execute("delete from test_outcome where source='record' and recorded=? and revision_id="
                        "(select id from revision where sha=?)", (rec, sha))
    if _has(store, "static"):
        by_sha: dict[str, dict[str, FileFacts]] = {}
        for sha, f, facts in con.execute("select sha, file, facts from static order by sha, file").fetchall():
            by_sha.setdefault(sha, {})[f] = FileFacts(**json.loads(facts))
        for sha, facts in by_sha.items():
            store.save_static(sha, facts)
    if _has(store, "test_outcomes"):
        for sha, rec, test, _passed, cases, source in con.execute(
                "select sha, recorded, test, passed, failing_cases, source from test_outcomes order by recorded, id"
        ).fetchall():
            store.add_outcomes(sha, {test: json.loads(cases)}, source, rec)
    state = dict(con.execute("select key, value from state").fetchall()) if _has(store, "state") else {}
    last = json.loads(state.pop("last_decision", "null")) or {}
    if _has(store, "decisions"):
        for (did, rec, base, head, mode, alpha, alpha_t, thr, rr, dec, sel, reasons) in con.execute(
                "select id, recorded, base, head, mode, alpha, alpha_t, threshold, residual_risk, decision, selected, "
                "reasons from decisions order by id").fetchall():
            store.save_decision(id=did, recorded=rec, base=base, head=head, mode=mode, alpha=alpha, alpha_t=alpha_t,
                                threshold=thr, residual_risk=rr, decision=dec, selected=json.loads(sel),
                                reasons=json.loads(reasons), scores=last.get("scores") if last.get("id") == did else None)
    if _has(store, "outcomes"):
        for did, missed, rec in con.execute("select decision_id, missed, recorded from outcomes order by decision_id"
                                            ).fetchall():
            store.save_outcome(did, bool(missed), rec)
    if "alpha_t" in state and json.loads(state["alpha_t"]) is not None:
        store.set_alpha_t(float(json.loads(state.pop("alpha_t"))))
    state.pop("alpha_t", None)
    for v in json.loads(state.pop("calibration", "[]")):
        store.add_calibration(math.inf if v is None else float(v))
    store.add_recal_points((None, float(s), int(lab)) for s, lab in json.loads(state.pop("recal_points", "[]")))
    for feats, lab in json.loads(state.pop("change_points", "[]")):
        store.add_change_point(feats, lab)
    for k, v in state.items():                        # scratch values, e.g. pending_change_features
        con.execute("insert or replace into setting values (?,?)", (k, v))
    for t in OLD_TABLES:
        con.execute(f"drop table if exists {t}")


STEPS: dict[str, Callable[[Store], None]] = {"0003_evidence_model.sql": import_v2}
