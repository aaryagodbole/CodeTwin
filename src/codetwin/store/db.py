"""SQLite evidence store: test runs, static facts, decisions and observed outcomes.

Every row keeps the commit it describes and when it was recorded, so stale evidence can be detected.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from importlib import resources
from pathlib import Path
from typing import Self

from ..evidence.model import FileFacts, TestRun

MIGRATIONS = "codetwin.store.migrations"


def _migrations() -> list[tuple[str, str]]:
    """SQL files in ``store/migrations/``, applied once each in name order.

    Add a new file (e.g. ``0002_evidence_cards.sql``) for a schema change; never edit an applied one.
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


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.migrate()

    def migrate(self) -> list[str]:
        self.con.execute("create table if not exists migrations (name text primary key, applied real)")
        done = {r[0] for r in self.con.execute("select name from migrations")}
        new = []
        for name, sql in _migrations():
            if name not in done:
                self.con.executescript(sql)
                self.con.execute("insert into migrations values (?,?)", (name, time.time()))
                new.append(name)
        self.con.commit()
        return new

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------- runs
    def save_run(self, run: TestRun) -> None:
        self.con.execute("insert or replace into runs values (?,?,?,?,?,?,?,?)",
                         (run.sha, time.time(), str(run.returncode), run.wall, json.dumps(run.durations),
                          json.dumps(run.failing), json.dumps(run.covered), json.dumps(run.import_lines)))
        self.add_outcomes(run.sha, outcomes_of(run), "record")

    def add_outcomes(self, sha: str, outcomes: dict[str, list[str]], source: str, when: float | None = None) -> None:
        """Append one row per test file: `outcomes` maps a test file to its failing test cases ([] = passed)."""
        t = time.time() if when is None else when
        self.con.executemany("insert into test_outcomes (sha, recorded, test, passed, failing_cases, source) "
                             "values (?,?,?,?,?,?)",
                             [(sha, t, test, int(not cases), json.dumps(sorted(cases)), source)
                              for test, cases in sorted(outcomes.items())])
        self.con.commit()

    def outcomes(self, test: str | None = None) -> list[dict]:
        q = "select sha, recorded, test, passed, failing_cases, source from test_outcomes"
        rows = self.con.execute(q + (" where test=? order by recorded, id" if test else " order by recorded, id"),
                                (test,) if test else ()).fetchall()
        return [{"sha": r[0], "recorded": r[1], "test": r[2], "passed": bool(r[3]), "failing_cases": json.loads(r[4]),
                 "source": r[5]} for r in rows]

    def run_shas(self) -> list[str]:
        return [r[0] for r in self.con.execute("select sha from runs order by recorded")]

    def get_run(self, sha: str) -> TestRun | None:
        row = self.con.execute("select sha, returncode, wall, durations, failing, covered, import_lines from runs where sha=?",
                               (sha,)).fetchone()
        if not row:
            return None
        return TestRun(sha=row[0], returncode=row[1], wall=row[2], durations=json.loads(row[3]), failing=json.loads(row[4]),
                       covered=json.loads(row[5]), import_lines=json.loads(row[6]))

    def latest_run_sha(self) -> str | None:
        row = self.con.execute("select sha from runs order by recorded desc limit 1").fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------- static facts
    def save_static(self, sha: str, facts: dict[str, FileFacts]) -> None:
        self.con.executemany("insert or replace into static values (?,?,?)",
                             [(sha, f, json.dumps(asdict(x))) for f, x in facts.items()])
        self.con.commit()

    def get_static(self, sha: str) -> dict[str, FileFacts]:
        return {f: FileFacts(**json.loads(j)) for f, j in self.con.execute("select file, facts from static where sha=?", (sha,))}

    # ------------------------------------------------------------- decisions and outcomes (for adaptive calibration)
    def save_decision(self, **d) -> int:
        cur = self.con.execute(
            "insert into decisions (recorded, base, head, mode, alpha, alpha_t, threshold, residual_risk, decision, selected, reasons) "
            "values (?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), d["base"], d.get("head"), d["mode"], d.get("alpha"), d.get("alpha_t"), d.get("threshold"),
             d.get("residual_risk"), d["decision"], json.dumps(sorted(d["selected"])), json.dumps(d.get("reasons", []))))
        self.con.commit()
        if cur.lastrowid is None:
            raise RuntimeError("decision was not stored")
        return cur.lastrowid

    def save_outcome(self, decision_id: int, missed: bool) -> None:
        self.con.execute("insert or replace into outcomes values (?,?,?)", (decision_id, int(missed), time.time()))
        self.con.commit()

    def get_state(self, key: str, default=None):
        row = self.con.execute("select value from state where key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_state(self, key: str, value) -> None:
        self.con.execute("insert or replace into state values (?,?)", (key, json.dumps(value)))
        self.con.commit()
