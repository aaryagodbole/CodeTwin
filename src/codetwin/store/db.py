"""SQLite evidence store: test runs, static facts, decisions and observed outcomes.

Every row keeps the commit it describes and when it was recorded, so stale evidence can be detected.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

from ..evidence.model import FileFacts, TestRun

SCHEMA = """
create table if not exists runs (
  sha text primary key, recorded real, returncode text, wall real,
  durations text, failing text, covered text, import_lines text);
create table if not exists static (
  sha text, file text, facts text, primary key (sha, file));
create table if not exists decisions (
  id integer primary key autoincrement, recorded real, base text, head text, mode text,
  alpha real, alpha_t real, threshold real, residual_risk real, decision text, selected text, reasons text);
create table if not exists outcomes (
  decision_id integer primary key, missed integer, recorded real);
create table if not exists state (key text primary key, value text);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.con.executescript(SCHEMA)

    # ------------------------------------------------------------- runs
    def save_run(self, run: TestRun) -> None:
        self.con.execute("insert or replace into runs values (?,?,?,?,?,?,?,?)",
                         (run.sha, time.time(), str(run.returncode), run.wall, json.dumps(run.durations),
                          json.dumps(run.failing), json.dumps(run.covered), json.dumps(run.import_lines)))
        self.con.commit()

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
        return int(cur.lastrowid)

    def save_outcome(self, decision_id: int, missed: bool) -> None:
        self.con.execute("insert or replace into outcomes values (?,?,?)", (decision_id, int(missed), time.time()))
        self.con.commit()

    def get_state(self, key: str, default=None):
        row = self.con.execute("select value from state where key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_state(self, key: str, value) -> None:
        self.con.execute("insert or replace into state values (?,?)", (key, json.dumps(value)))
        self.con.commit()
