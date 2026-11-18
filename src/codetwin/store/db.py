"""SQLite evidence store: code entities, static and runtime evidence, test outcomes, decisions and learning state.

The schema is normalized (``migrations/0003_evidence_model.sql``, diagram in ``docs/database.md``): paths, shas and
test ids are stored once and referenced by id, every list in the evidence model is a table with one row per element,
and every row keeps the revision it describes and when it was recorded, so stale evidence can be detected.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager
from importlib import resources
from pathlib import Path
from typing import Any, Self

from .. import __version__
from ..evidence.model import FileFacts, TestRun, incomplete_code

MIGRATIONS = "codetwin.store.migrations"
SYMBOL_KINDS = ("class", "function", "method")
CALIBRATION_WINDOW, RECAL_WINDOW, CHANGE_WINDOW = 200, 5000, 2000
SELF = 1                                   # repository.id of the repository this database belongs to


def _migrations() -> list[tuple[str, str]]:
    """SQL files in ``store/migrations/``, applied once each in name order.

    Add a new file (e.g. ``0004_contracts.sql``) for a schema change; never edit an applied one. A migration that
    must also move data registers a Python step in ``store/legacy.py`` (``STEPS``); it runs in the same transaction.
    Applied files are tracked by name, so two branches adding different files never clash.
    """
    files = resources.files(MIGRATIONS)
    return sorted((f.name, f.read_text()) for f in files.iterdir() if f.name.endswith(".sql"))


def outcomes_of(run: TestRun) -> dict[str, list[str]]:
    """Test file -> failing test cases of a run (a failing case id is "file::case"; a run-level failure of a whole
    file, e.g. a collection error, is reported under the file itself)."""
    unrun = set(run.unrun)
    out: dict[str, list[str]] = {t: [] for t in run.durations if t not in unrun}
    for case in run.failing:
        f = case.split("::", 1)[0]
        if f not in unrun:
            out.setdefault(f, []).append(case)
    return out


def _num(x: float | None) -> float | None:
    """REAL for SQLite: NaN has no SQL value and is stored as null."""
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, isolation_level=None)    # transactions are explicit (_tx)
        self.con.execute("pragma foreign_keys = on")
        # The CLI, `codetwin serve`, MCP and the VS Code extension may open the store at the same time: readers do not
        # block the writer (WAL), and a writer waits for another instead of failing at once (E6).
        self.con.execute("pragma busy_timeout = 5000")
        self.con.execute("pragma journal_mode = wal")   # where WAL is not possible SQLite keeps its default journal
        self._depth = 0
        self._ids: dict[tuple, int] = {}
        self.migrate()

    # ------------------------------------------------------------- connection, transactions, migrations
    def transaction(self) -> AbstractContextManager[None]:
        """Group several writes into one transaction; nested blocks join the outer one, with no rollback of
        their own. An error rolls back everything only when it reaches the outermost block."""
        return self._tx()

    @contextmanager
    def _tx(self) -> Iterator[None]:
        """One transaction for the outermost block; nested blocks join it. Rolled back on any error."""
        if self._depth == 0:
            # immediate: take the write lock now. With WAL a deferred transaction that reads before it writes fails
            # at once (SQLITE_BUSY_SNAPSHOT) when another connection committed meanwhile, instead of waiting.
            self.con.execute("begin immediate")
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self.con.execute("rollback")
                self._ids.clear()
            raise
        self._depth -= 1
        if self._depth == 0:
            self.con.execute("commit")

    def migrate(self) -> list[str]:
        from .legacy import STEPS
        self.con.execute("create table if not exists migrations (name text primary key, applied real)")
        done = {r[0] for r in self.con.execute("select name from migrations")}
        new = []
        for name, sql in _migrations():
            if name in done:
                continue
            self._depth = 1
            try:
                # Inside the try: if the script itself fails part way, its open transaction is rolled back too.
                self.con.executescript("begin;\n" + sql)   # leaves the transaction open (no implicit commit)
                if name in STEPS:
                    STEPS[name](self)
                self.con.execute("insert into migrations values (?,?)", (name, time.time()))
            except BaseException:
                if self.con.in_transaction:
                    self.con.execute("rollback")
                self._ids.clear()
                raise
            finally:
                self._depth = 0
            self.con.execute("commit")
            new.append(name)
        return new

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def tables(self) -> list[str]:
        return [r[0] for r in self.con.execute("select name from sqlite_master where type='table' order by name")]

    # ------------------------------------------------------------- identities
    def _revision(self, sha: str, when: float | None = None, repo: int = SELF) -> int:
        key = ("rev", repo, sha)
        if key not in self._ids:
            self.con.execute("insert or ignore into revision (repository_id, sha, recorded) values (?,?,?)",
                             (repo, sha, time.time() if when is None else when))
            self._ids[key] = self.con.execute("select id from revision where repository_id=? and sha=?",
                                              (repo, sha)).fetchone()[0]
        return self._ids[key]

    def _revision_id(self, sha: str, repo: int = SELF) -> int | None:
        row = self.con.execute("select id from revision where repository_id=? and sha=?", (repo, sha)).fetchone()
        return row[0] if row else None

    def _entity(self, path: str, kind: str = "file", name: str = "", repo: int = SELF) -> int:
        key = (repo, kind, path, name)
        if key not in self._ids:
            self.con.execute("insert or ignore into code_entity (repository_id, kind, path, name) values (?,?,?,?)", key)
            self._ids[key] = self.con.execute("select id from code_entity where repository_id=? and kind=? and path=? "
                                              "and name=?", key).fetchone()[0]
        return self._ids[key]

    def repository(self, name: str, location: str | None = None) -> int:
        """Id of a connected repository (created on first use; its location is updated when given)."""
        key = ("repo", name)
        if key not in self._ids:
            with self._tx():
                self.con.execute("insert or ignore into repository (name, location) values (?,?)", (name, location))
                self._ids[key] = self.con.execute("select id from repository where name=?", (name,)).fetchone()[0]
        if location is not None:
            with self._tx():
                self.con.execute("update repository set location=? where id=? and is_self=0", (location, self._ids[key]))
        return self._ids[key]

    def _files(self) -> dict[int, str]:
        return dict(self.con.execute("select id, path from code_entity where kind='file'"))

    # ------------------------------------------------------------- runs (runtime evidence)
    def save_run(self, run: TestRun, recorded: float | None = None) -> None:
        """Store a full run, replacing an earlier run of the same revision."""
        t = time.time() if recorded is None else recorded
        with self._tx():
            rev = self._revision(run.sha, t)
            self.con.execute("delete from test_run where revision_id=?", (rev,))
            rid = self.con.execute("insert into test_run (revision_id, recorded, returncode, wall) values (?,?,?,?)",
                                   (rev, t, str(run.returncode), run.wall)).lastrowid
            tests = list(run.durations) + [x for x in run.covered if x not in run.durations]
            self.con.executemany(
                "insert into test_result (run_id, test_id, ordinal, duration, traced) values (?,?,?,?,?)",
                [(rid, self._entity(x), i, _num(run.durations.get(x)), int(x in run.covered))
                 for i, x in enumerate(tests)])
            self.con.executemany("insert into test_failure (run_id, ordinal, case_id) values (?,?,?)",
                                 [(rid, i, c) for i, c in enumerate(run.failing)])
            self.con.executemany(
                "insert or ignore into coverage_line (run_id, test_id, file_id, line) values (?,?,?,?)",
                [(rid, self._entity(x), self._entity(f), ln) for x, files in run.covered.items()
                 for f, lines in files.items() for ln in lines])
            self.con.executemany("insert or ignore into import_line (run_id, file_id, line) values (?,?,?)",
                                 [(rid, self._entity(f), ln) for f, lines in run.import_lines.items() for ln in lines])
            self.add_outcomes(run.sha, outcomes_of(run), "record", t)

    def get_run(self, sha: str) -> TestRun | None:
        row = self.con.execute("select t.id, t.returncode, t.wall from test_run t join revision r on r.id = t.revision_id "
                               "where r.repository_id=1 and r.sha=?", (sha,)).fetchone()
        if not row:
            return None
        rid, files = row[0], self._files()
        run = TestRun(sha=sha, returncode=row[1], wall=row[2])
        for tid, dur, traced in self.con.execute("select test_id, duration, traced from test_result where run_id=? "
                                                 "order by ordinal", (rid,)):
            if dur is not None:
                run.durations[files[tid]] = dur
            if traced:
                run.covered[files[tid]] = {}
        run.failing = [r[0] for r in self.con.execute("select case_id from test_failure where run_id=? order by ordinal",
                                                      (rid,))]
        for tid, fid, line in self.con.execute("select c.test_id, c.file_id, c.line from coverage_line c "
                                               "join code_entity f on f.id = c.file_id where c.run_id=? "
                                               "order by c.test_id, f.path, c.line", (rid,)):
            run.covered[files[tid]].setdefault(files[fid], []).append(line)
        for fid, line in self.con.execute("select i.file_id, i.line from import_line i join code_entity f on "
                                          "f.id = i.file_id where i.run_id=? order by f.path, i.line", (rid,)):
            run.import_lines.setdefault(files[fid], []).append(line)
        return run

    def run_shas(self) -> list[str]:
        return [r[0] for r in self.con.execute("select r.sha from test_run t join revision r on r.id = t.revision_id "
                                               "where r.repository_id=1 order by t.recorded, t.id")]

    def latest_run_sha(self) -> str | None:
        """The newest run that completed: an incomplete one (timeout, interrupted) is never the default base."""
        row = self._latest_complete_run()
        return row[0] if row else None

    def latest_run_incomplete(self) -> tuple[str, str] | None:
        """(sha, return code) of the newest run when it did not complete, else None: why `select` skipped it."""
        row = self.con.execute("select sha, returncode from latest_run").fetchone()
        return (row[0], row[1]) if row and incomplete_code(row[1]) else None

    def run_returncode(self, sha: str) -> str | None:
        """The stored return code of the run of `sha` (None: no run), without loading its coverage."""
        row = self.con.execute("select t.returncode from test_run t join revision r on r.id = t.revision_id "
                               "where r.repository_id = 1 and r.sha = ?", (sha,)).fetchone()
        return row[0] if row else None

    def _latest_complete_run(self) -> tuple | None:
        # Newest first; few runs are ever incomplete, so filtering in Python keeps the rule in one place.
        for sha, recorded, code in self.con.execute(
                "select r.sha, t.recorded, t.returncode from test_run t join revision r on r.id = t.revision_id "
                "where r.repository_id = 1 order by t.recorded desc, t.id desc"):
            if not incomplete_code(code):
                return sha, recorded
        return None

    def latest_run_recorded(self) -> float | None:
        """When the run returned by `latest_run_sha()` was recorded (same repository and row as that method)."""
        row = self._latest_complete_run()
        return row[1] if row else None

    def tests_covering(self, sha: str, file: str, line: int) -> list[str]:
        """Test files whose recorded run executed `file` at `line` (uses the coverage_by_line index)."""
        return [r[0] for r in self.con.execute(
            "select distinct te.path from coverage_line c join test_run t on t.id = c.run_id "
            "join revision r on r.id = t.revision_id join code_entity f on f.id = c.file_id "
            "join code_entity te on te.id = c.test_id where r.repository_id=1 and r.sha=? and f.kind='file' and f.path=? and c.line=? "
            "order by te.path", (sha, file, line))]

    # ------------------------------------------------------------- test outcomes (history for failure triage)
    def add_outcomes(self, sha: str, outcomes: dict[str, list[str]], source: str, when: float | None = None) -> None:
        """Append one row per test file: `outcomes` maps a test file to its failing test cases ([] = passed)."""
        t = time.time() if when is None else when
        with self._tx():
            rev = self._revision(sha, t)
            for test, cases in sorted(outcomes.items()):
                oid = self.con.execute("insert into test_outcome (revision_id, test_id, recorded, passed, source) "
                                       "values (?,?,?,?,?)", (rev, self._entity(test), t, int(not cases), source)).lastrowid
                self.con.executemany("insert into test_outcome_case (outcome_id, ordinal, case_id) values (?,?,?)",
                                     [(oid, i, c) for i, c in enumerate(sorted(cases))])

    def outcomes(self, test: str | None = None) -> list[dict]:
        q = ("select o.id, r.sha, o.recorded, e.path, o.passed, o.source from test_outcome o "
             "join revision r on r.id = o.revision_id join code_entity e on e.id = o.test_id")
        rows = self.con.execute(q + (" where e.repository_id=1 and e.kind='file' and e.path=?" if test else "") + " order by o.recorded, o.id",
                                (test,) if test else ()).fetchall()
        cases: dict[int, list[str]] = {}
        if rows:
            ids = [r[0] for r in rows]
            for i in range(0, len(ids), 900):            # SQLite's bound-parameter limit
                chunk = ids[i:i + 900]
                for oid, c in self.con.execute(f"select outcome_id, case_id from test_outcome_case where outcome_id in "  # noqa: S608 (constant SQL; values bound)
                                               f"({','.join('?' * len(chunk))}) order by outcome_id, ordinal", chunk):
                    cases.setdefault(oid, []).append(c)
        return [{"sha": r[1], "recorded": r[2], "test": r[3], "passed": bool(r[4]), "failing_cases": cases.get(r[0], []),
                 "source": r[5]} for r in rows]

    def flaky_tests(self) -> list[dict]:
        return [{"sha": r[0], "test": r[1], "passes": r[2], "failures": r[3]} for r in self.con.execute(
            "select r.sha, f.test, f.passes, f.failures from flaky_test f join revision r on r.id = f.revision_id "
            "where r.repository_id = 1 order by f.test, r.recorded, r.id")]

    # ------------------------------------------------------------- static facts (static evidence)
    def save_static(self, sha: str, facts: dict[str, FileFacts], when: float | None = None) -> None:
        """Store the static facts of a revision, replacing all earlier ones of it (a file analysed before but not
        now, e.g. after a change of source_dirs, must not stay in the snapshot)."""
        t = time.time() if when is None else when
        with self._tx():
            rev = self._revision(sha, t)
            self.con.execute("delete from file_snapshot where revision_id=?", (rev,))
            self.con.execute("delete from evidence_edge where revision_id=? and type='static'", (rev,))
            for f, x in facts.items():
                fid = self._entity(f)
                sid = self.con.execute("insert into file_snapshot (revision_id, file_id) values (?,?)",
                                       (rev, fid)).lastrowid
                ex = self.con.executemany
                ex("insert into snapshot_import values (?,?,?)", [(sid, i, m) for i, m in enumerate(x.imports)])
                ex("insert into unresolved_reference values (?,?,?)", [(sid, i, k) for i, k in enumerate(x.dynamic)])
                ex("insert into snapshot_line values (?,?,?,?)",
                   [(sid, "dynamic", i, ln) for i, ln in enumerate(x.dyn_lines)]
                   + [(sid, "module", i, ln) for i, ln in enumerate(x.mod_lines)])
                ex("insert into definition values (?,?,?,?,?)", [(sid, i, *d) for i, d in enumerate(x.defs)])
                for i, (name, kind, first, last) in enumerate(x.symbols):
                    if kind not in SYMBOL_KINDS:
                        raise ValueError(f"{f}: unknown symbol kind {kind!r} for {name!r}")
                    self.con.execute("insert into symbol_occurrence values (?,?,?,?,?)",
                                     (sid, i, self._entity(f, kind, name), first, last))
                ex("insert into evidence_edge (revision_id, src_id, dst_id, type, ordinal, source, tool_version, observed) "
                   "values (?,?,?,'static',?,'import-resolution',?,?)",
                   [(rev, fid, self._entity(d), i, __version__, t) for i, d in enumerate(x.deps) if d != f])

    def get_static(self, sha: str) -> dict[str, FileFacts]:
        rev = self._revision_id(sha)
        if rev is None:
            return {}
        files = self._files()
        snaps = dict(self.con.execute("select s.id, f.path from file_snapshot s join code_entity f on f.id = s.file_id "
                                      "where s.revision_id=? order by s.id", (rev,)))
        out = {path: FileFacts() for path in snaps.values()}

        def each(sql: str) -> Iterable[tuple]:
            return self.con.execute(sql, (rev,))
        j = " x join file_snapshot s on s.id = x.snapshot_id where s.revision_id=? order by x.snapshot_id, "
        for sid, m in each("select x.snapshot_id, x.module from snapshot_import" + j + "x.ordinal"):  # noqa: S608 (constant SQL; values bound)
            out[snaps[sid]].imports.append(m)
        for sid, k in each("select x.snapshot_id, x.kind from unresolved_reference" + j + "x.ordinal"):  # noqa: S608 (constant SQL; values bound)
            out[snaps[sid]].dynamic.append(k)
        for sid, role, ln in each("select x.snapshot_id, x.role, x.line from snapshot_line" + j + "x.role, x.ordinal"):  # noqa: S608 (constant SQL; values bound)
            (out[snaps[sid]].dyn_lines if role == "dynamic" else out[snaps[sid]].mod_lines).append(ln)
        for sid, a, b, c in each("select x.snapshot_id, x.start_line, x.end_line, x.body_line from definition" + j  # noqa: S608 (constant SQL; values bound)
                                 + "x.ordinal"):
            out[snaps[sid]].defs.append([a, b, c])
        for sid, name, kind, a, b in each("select x.snapshot_id, e.name, e.kind, x.first_line, x.last_line from "
                                          "symbol_occurrence x join code_entity e on e.id = x.entity_id join "
                                          "file_snapshot s on s.id = x.snapshot_id where s.revision_id=? "
                                          "order by x.snapshot_id, x.ordinal"):
            out[snaps[sid]].symbols.append([name, kind, a, b])
        for src, dst in self.con.execute("select src_id, dst_id from evidence_edge where revision_id=? and type='static' "
                                         "order by src_id, ordinal", (rev,)):
            if files[src] in out:
                out[files[src]].deps.append(files[dst])
        return out

    def evidence(self, sha: str) -> list[dict]:
        """Every typed link recorded for a revision (view `evidence`): static, runtime and unresolved."""
        rev = self._revision_id(sha)
        if rev is None:
            return []
        files = dict(self.con.execute("select id, path from code_entity"))
        return [{"src": files[s], "dst": files.get(d), "type": t, "source": src, "status": st} for s, d, t, src, st in
                self.con.execute("select src_id, dst_id, type, source, status from evidence where revision_id=? "
                                 "order by type, src_id, dst_id", (rev,))]

    # ------------------------------------------------------------- decisions and their outcomes
    def save_decision(self, **d: Any) -> int:
        """Store a decision: base, head, mode, alpha, alpha_t, threshold, residual_risk, decision ('proceed' or
        'abstain'), selected tests, reasons and, optionally, the model's score of every candidate test."""
        with self._tx():
            when = d.get("recorded") or time.time()
            cur = self.con.execute(
                "insert into decision (id, recorded, base_revision_id, head, mode, alpha, alpha_t, threshold, "
                "residual_risk, verdict) values (?,?,?,?,?,?,?,?,?,?)",
                (d.get("id"), when, self._revision(d["base"], when), d.get("head"), d["mode"], d.get("alpha"),
                 d.get("alpha_t"), _num(d.get("threshold")), _num(d.get("residual_risk")), d["decision"]))
            did = cur.lastrowid
            if did is None:
                raise RuntimeError("decision was not stored")
            self.con.executemany("insert into decision_selection values (?,?)",
                                 [(did, self._entity(t)) for t in sorted(d["selected"])])
            self.con.executemany("insert into decision_reason values (?,?,?)",
                                 [(did, i, str(r)) for i, r in enumerate(d.get("reasons", []))])
            self.con.executemany("insert into decision_score values (?,?,?)",
                                 [(did, self._entity(t), _num(s)) for t, s in (d.get("scores") or {}).items()])
        return did

    def save_outcome(self, decision_id: int, missed: bool, when: float | None = None) -> None:
        with self._tx():
            self.con.execute("insert or replace into decision_outcome values (?,?,?)",
                             (decision_id, int(missed), time.time() if when is None else when))

    def has_outcome(self, decision_id: int) -> bool:
        return self.con.execute("select 1 from decision_outcome where decision_id=?", (decision_id,)).fetchone() is not None

    def _tests_of(self, table: str, decision_id: int) -> list[str]:
        return [r[0] for r in self.con.execute(f"select e.path from {table} x join code_entity e on e.id = x.test_id "  # noqa: S608 (constant SQL; values bound)
                                               "where x.decision_id=? order by e.path", (decision_id,))]

    def decision(self, decision_id: int) -> dict | None:
        """One decision with its selection, reasons, scores and outcome (missed: None until learned)."""
        rows = self.decisions(ids=[decision_id])
        return rows[0] if rows else None

    def decisions(self, limit: int = 100, ids: list[int] | None = None) -> list[dict]:
        """Newest first."""
        q = ("select d.id, d.recorded, r.sha, d.mode, d.alpha, d.alpha_t, d.threshold, d.residual_risk, d.verdict, "
             "o.missed from decision d join revision r on r.id = d.base_revision_id "
             "left join decision_outcome o on o.decision_id = d.id ")
        rows = (self.con.execute(q + f"where d.id in ({','.join('?' * len(ids))}) order by d.id desc", ids) if ids
                else self.con.execute(q + "order by d.id desc limit ?", (limit,)))
        keys = ["id", "recorded", "base", "mode", "alpha", "alpha_t", "threshold", "residual_risk", "decision", "missed"]
        out = []
        for r in rows.fetchall():
            d = dict(zip(keys, r, strict=True))
            d["missed"] = None if d["missed"] is None else bool(d["missed"])
            d["selected"] = self._tests_of("decision_selection", d["id"])
            d["reasons"] = [x[0] for x in self.con.execute("select text from decision_reason where decision_id=? "
                                                           "order by ordinal", (d["id"],))]
            out.append(d)
        return out

    def scores(self, decision_id: int) -> dict[str, float]:
        return {p: (math.nan if s is None else s) for p, s in self.con.execute(
            "select e.path, x.score from decision_score x join code_entity e on e.id = x.test_id "
            "where x.decision_id=? order by e.path", (decision_id,))}

    def last_decision(self) -> dict | None:
        """The newest stored decision in the shape `learn` needs: id, base, mode, selected, scores."""
        row = self.con.execute("select max(id) from decision").fetchone()
        if row[0] is None:
            return None
        d = self.decision(row[0])
        if d is None:
            return None
        return {"id": d["id"], "base": d["base"], "mode": d["mode"], "selected": d["selected"],
                "scores": self.scores(d["id"])}

    def labelled(self, mode: str = "calibrated") -> list[tuple[int, float, float, int]]:
        """(decision id, alpha, alpha_t, missed) of labelled decisions of a mode, oldest first."""
        return [tuple(r) for r in self.con.execute("select id, alpha, alpha_t, missed from labelled_decision "
                                                   "where mode=? order by id", (mode,))]

    def counts(self) -> dict[str, int]:
        return {"decisions": self.con.execute("select count(*) from decision").fetchone()[0],
                "labelled_decisions": self.con.execute("select count(*) from decision_outcome").fetchone()[0]}

    # ------------------------------------------------------------- learning state (append-only histories)
    def calibration(self, window: int = CALIBRATION_WINDOW) -> list[float]:
        """The newest `window` calibration scores, oldest first (+inf: no affected test was scored)."""
        rows = self.con.execute("select value from (select id, value from calibration_point order by id desc limit ?) "
                                "order by id", (window,))
        return [math.inf if v is None else v for (v,) in rows]

    def add_calibration(self, value: float, decision_id: int | None = None, when: float | None = None) -> None:
        with self._tx():
            self.con.execute("insert into calibration_point (decision_id, value, recorded) values (?,?,?)",
                             (decision_id, None if math.isinf(value) else _num(value),
                              time.time() if when is None else when))

    def recal_points(self, window: int = RECAL_WINDOW) -> list[tuple[float, int]]:
        """The newest `window` (score, label) pairs, oldest first."""
        return [(s, lab) for s, lab in self.con.execute(
            "select score, label from (select id, score, label from recalibration_point order by id desc limit ?) "
            "order by id", (window,))]

    def add_recal_points(self, points: Iterable[tuple[str | None, float, int]], decision_id: int | None = None) -> None:
        """`points`: (test file or None, score, 1 if the test was affected)."""
        with self._tx():
            self.con.executemany(
                "insert into recalibration_point (decision_id, test_id, score, label) values (?,?,?,?)",
                [(decision_id, self._entity(t) if t else None, s, int(lab)) for t, s, lab in points])

    def change_points(self, window: int = CHANGE_WINDOW) -> list[list]:
        """The newest `window` [features, label] pairs, oldest first."""
        pts = self.con.execute("select id, label from (select id, label from change_point order by id desc limit ?) "
                               "order by id", (window,)).fetchall()
        feats: dict[int, dict[str, float]] = {p: {} for p, _ in pts}
        if pts:
            for pid, name, value in self.con.execute("select point_id, name, value from change_feature where point_id "
                                                     ">= ? order by point_id, name", (pts[0][0],)):
                if pid in feats:
                    feats[pid][name] = math.nan if value is None else value
        return [[feats[p], lab] for p, lab in pts]

    def add_change_point(self, features: dict[str, float], label: int, decision_id: int | None = None,
                         when: float | None = None) -> None:
        with self._tx():
            pid = self.con.execute("insert into change_point (decision_id, label, recorded) values (?,?,?)",
                                   (decision_id, int(label), time.time() if when is None else when)).lastrowid
            self.con.executemany("insert into change_feature values (?,?,?)",
                                 [(pid, k, _num(float(v))) for k, v in features.items()])

    def alpha_t(self, default: float | None = None) -> float | None:
        row = self.con.execute("select alpha_t from adaptive_level order by id desc limit 1").fetchone()
        return row[0] if row else default

    def set_alpha_t(self, value: float, decision_id: int | None = None, when: float | None = None) -> None:
        with self._tx():
            self.con.execute("insert into adaptive_level (decision_id, alpha_t, recorded) values (?,?,?)",
                             (decision_id, value, time.time() if when is None else when))

    # ------------------------------------------------------------- scratch settings (not evidence)
    def get_state(self, key: str, default=None):
        row = self.con.execute("select value from setting where key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_state(self, key: str, value) -> None:
        with self._tx():
            self.con.execute("insert or replace into setting values (?,?)", (key, json.dumps(value)))
