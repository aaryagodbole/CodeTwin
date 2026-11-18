"""Fixes from the merge review of release v0.2.0 (#89)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.store import db as store_db
from codetwin.store.db import Store


def _recorded(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])


def test_run_takes_the_tests_from_the_decision_file(toy_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    """A change that edits only tests is printed by select but not stored; `run --decision` still runs its tests."""
    _recorded(toy_repo)
    ran: list[list[str]] = []
    import contextlib

    import codetwin.commands.run as run_cmd
    real_engine = run_cmd.engine

    @contextlib.contextmanager
    def engine_without_runner(args):  # noqa: ANN001
        with real_engine(args) as eng:
            monkeypatch.setattr(eng.lang, "run_all", lambda root, tests, timeout: ran.append(list(tests)) or True)
            yield eng
    monkeypatch.setattr(run_cmd, "engine", engine_without_runner)
    decision = tmp_path / "d.json"
    decision.write_text(json.dumps({"decision": "proceed", "residual_risk": 0.02, "selected": ["tests/test_price.py"],
                                    "reasons": [], "extras": {}}), encoding="utf-8")
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "run", "--decision", str(decision)]) == 0
    assert ran and ran[-1] == ["tests/test_price.py"]


def test_run_refuses_a_file_that_is_not_a_decision(toy_repo: Path, tmp_path: Path,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    _recorded(toy_repo)
    bad = tmp_path / "bad.json"
    for content in ['{"selected": null}', "", "{not json"]:
        bad.write_text(content, encoding="utf-8")
        with pytest.raises(SystemExit, match="--decision"):
            main(["-C", str(toy_repo), "run", "--decision", str(bad)])
    with pytest.raises(SystemExit, match="not both"):
        main(["-C", str(toy_repo), "run", "tests/test_price.py", "--decision", str(bad)])


def test_run_refuses_an_empty_or_stale_decision(toy_repo: Path, tmp_path: Path) -> None:
    """`--decision ""` is an error, not "use the last decision"; a decision made for another commit is refused."""
    _recorded(toy_repo)
    with pytest.raises(SystemExit, match="--decision"):
        main(["-C", str(toy_repo), "run", "--decision", ""])
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"decision": "proceed", "residual_risk": 0.02, "selected": ["tests/test_price.py"],
                                 "reasons": [], "extras": {"changed_files": {"base": "0" * 40}}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="computed against 000000000000"):
        main(["-C", str(toy_repo), "run", "--decision", str(stale)])


def test_learn_can_be_retried_after_failing_part_way(toy_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _recorded(toy_repo)
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))
    with Engine(toy_repo) as eng:
        eng.select()
        real = eng.store.add_recal_points

        def boom(*a, **k):  # noqa: ANN002, ANN003
            raise RuntimeError("disk full")
        monkeypatch.setattr(eng.store, "add_recal_points", boom)
        with pytest.raises(RuntimeError, match="disk full"):
            eng.learn()
        monkeypatch.setattr(eng.store, "add_recal_points", real)
        out = eng.learn()                       # used to fail: UNIQUE constraint failed: calibration_point.decision_id
    assert "missed" in out


def test_a_failing_migration_script_is_rolled_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with Store(tmp_path / "e.sqlite"):
        pass
    bad = "create table half_done (x integer);\nthis is not sql;\n"
    real = store_db._migrations
    monkeypatch.setattr(store_db, "_migrations", lambda: [*real(), ("9999_broken.sql", bad)])
    with pytest.raises(Exception):  # noqa: B017  (sqlite3.OperationalError)
        Store(tmp_path / "e.sqlite")
    monkeypatch.setattr(store_db, "_migrations", real)
    with Store(tmp_path / "e.sqlite") as s:
        tables = {r[0] for r in s.con.execute("select name from sqlite_master where type='table'")}
        names = {r[0] for r in s.con.execute("select name from migrations")}
    assert "half_done" not in tables and "9999_broken.sql" not in names


def test_decision_lists_default_to_empty() -> None:
    from codetwin.server.app import _clean_decision

    out = _clean_decision({"id": 1, "decision": "proceed"})
    assert out["selected"] == [] and out["reasons"] == []


def test_inline_comments_use_the_pull_request_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from codetwin.commands.review import _pull_request_base

    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "a.txt").write_text("a\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "a"],
                   check=True)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                         check=True).stdout.strip()
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 3, "base": {"sha": sha}}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    assert _pull_request_base(repo) == sha
    event.write_text(json.dumps({"pull_request": {"number": 3, "base": {"sha": "f" * 40}}}), encoding="utf-8")
    assert _pull_request_base(repo) is None              # not in the local history: fall back to the recorded base
    monkeypatch.delenv("GITHUB_EVENT_PATH")
    assert _pull_request_base(repo) is None


def test_a_malformed_event_never_crashes_the_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from codetwin.commands.review import _pull_request_base

    event = tmp_path / "event.json"
    for payload in ['{"pull_request": {"base": "main"}}', '{"pull_request": []}', "[1]", "{bad"]:
        event.write_text(payload, encoding="utf-8")
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
        assert _pull_request_base(tmp_path) is None
