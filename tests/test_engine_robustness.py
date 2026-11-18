"""Engine robustness (#99, tasks 2.3, 2.4, 2.7, 2.9 and 2.10 of #71)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codetwin.cli import main
from codetwin.engine import Engine
from codetwin.evidence.model import TestRun
from codetwin.risk.residual import Recalibrator
from codetwin.store.db import Store


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def _recorded(repo: Path) -> None:
    main(["-C", str(repo), "init"])
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "codetwin config")
    main(["-C", str(repo), "record"])


def _edit_source(repo: Path) -> None:
    p = repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('i["price"]', 'i["price"] * 1'))


# --------------------------------------------------------------------------------- 2.3 (E5): history up to the base
def test_history_stops_at_the_base_commit(toy_repo: Path) -> None:
    _recorded(toy_repo)
    with Engine(toy_repo) as eng:
        base = eng.store.latest_run_sha()
    # A commit after the recorded base that changes price.py together with test_names.py: part of the change, so it
    # must not count as co-change history.
    _edit_source(toy_repo)
    n = toy_repo / "tests/test_names.py"
    n.write_text(n.read_text() + "\n# touched with price.py\n")
    _git(toy_repo, "commit", "-qam", "after base")
    with Engine(toy_repo) as eng:
        assert base is not None
        at_base, at_head = eng.history(base), eng.history()
        assert at_head[:-1] == at_base and sorted(at_head[-1]) == ["src/shop/price.py", "tests/test_names.py"]
        seen: list[str | None] = []
        real = eng.history
        eng.history = lambda b=None: seen.append(b) or real(b)   # type: ignore[method-assign]
        eng.analyse(base)
        assert seen == [base]                                     # analyse reads history up to the base only


# ------------------------------------------------------------------------------------------- 2.7: shallow history
def test_a_shallow_clone_says_so_in_the_decision(toy_repo: Path, tmp_path: Path) -> None:
    _git(toy_repo, "commit", "-q", "--allow-empty", "-m", "second")
    clone = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", toy_repo.as_uri(), str(clone)], check=True)
    _recorded(clone)
    _edit_source(clone)
    with Engine(clone) as eng:
        d = eng.select()
    assert any(r.startswith("shallow clone: co-change evidence comes from only") for r in d.reasons)


def test_a_full_clone_has_no_history_note(toy_repo: Path) -> None:
    _recorded(toy_repo)
    _edit_source(toy_repo)
    with Engine(toy_repo) as eng:
        d = eng.select()
        assert not any("shallow" in r or "git history" in r for r in d.reasons)
        assert eng.history("0" * 40) == [] and "git history is not available" in (eng.history_note or "")


# ------------------------------------------------------------------------------------ 2.4 (E6): one transaction
def test_a_crash_while_recording_leaves_no_half_recorded_run(toy_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        def boom(*a, **k):  # noqa: ANN002, ANN003
            raise RuntimeError("crash while storing static facts")
        monkeypatch.setattr(eng.store, "save_static", boom)
        with pytest.raises(RuntimeError, match="crash"):
            eng.record()
        assert eng.store.get_run(eng.head()) is None and eng.store.latest_run_sha() is None


def test_the_store_uses_wal_and_waits_for_a_busy_writer(tmp_path: Path) -> None:
    with Store(tmp_path / "s.db") as s:
        assert s.con.execute("pragma journal_mode").fetchone()[0] == "wal"
        assert s.con.execute("pragma busy_timeout").fetchone()[0] == 5000


# ----------------------------------------------------------------------------------------------- 2.9: incomplete runs
def _record_timeout(eng: Engine, monkeypatch: pytest.MonkeyPatch) -> TestRun:
    monkeypatch.setattr(eng.lang, "run_suite", lambda sha, *a, **k: TestRun(sha=sha, returncode="timeout"))
    return eng.record()


def test_an_incomplete_run_is_stored_with_a_warning_but_is_not_the_base(toy_repo: Path,
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    _recorded(toy_repo)
    with Engine(toy_repo) as eng:
        good = eng.store.latest_run_sha()
    _git(toy_repo, "commit", "-q", "--allow-empty", "-m", "later")
    with Engine(toy_repo) as eng:
        run = _record_timeout(eng, monkeypatch)
        assert run.incomplete and any("did not complete (timeout)" in n for n in run.notes)
        assert eng.store.get_run(eng.head()) is not None                    # stored, marked by its return code
        assert eng.store.latest_run_sha() == good                           # but the base stays the complete run
        assert eng.store.latest_run_incomplete() == (eng.head(), "timeout")


def test_select_explains_when_the_only_run_is_incomplete(toy_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        _record_timeout(eng, monkeypatch)
        _edit_source(toy_repo)
        with pytest.raises(RuntimeError, match=r"did not complete \(timeout\)"):
            eng.select()


@pytest.mark.parametrize(("code", "incomplete"), [(0, False), (1, False), (5, False), ("2", True), (4, True),
                                                 ("timeout", True), ("no-runner", False)])
def test_incomplete_return_codes(code: int | str, incomplete: bool) -> None:
    assert TestRun(sha="x", returncode=code).incomplete is incomplete


# ------------------------------------------------------------------------------- 2.10: bad model, tiny calibration
@pytest.mark.parametrize("content", ["{not json", '{"cov_line": "high"}', "[]", '{"cov_line": NaN}', "{}"])
def test_a_broken_model_file_gives_a_clear_error(toy_repo: Path, content: str) -> None:
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        model = eng.cfg.state_dir / "model.json"
    model.write_text(content)
    with pytest.raises(RuntimeError, match="delete it to use the built-in prior"):
        Engine(toy_repo)


def test_a_valid_model_file_loads(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        (eng.cfg.state_dir / "model.json").write_text('{"cov_line": 2, "intercept": -1.5}')
    with Engine(toy_repo) as eng:
        assert eng.model.weights == {"cov_line": 2.0, "intercept": -1.5}


def test_recalibration_waits_for_enough_examples() -> None:
    few = Recalibrator().fit([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])
    assert few.iso is None and few(0.8) == 0.8                       # raw score, not a step to 1.0
    n = Recalibrator.MIN_EACH
    enough = Recalibrator().fit([i / 10 for i in range(2 * n)], [0] * n + [1] * n)
    assert enough.iso is not None


def test_select_says_when_scores_are_not_recalibrated(toy_repo: Path) -> None:
    _recorded(toy_repo)
    _edit_source(toy_repo)
    with Engine(toy_repo) as eng:
        eng.store.add_recal_points([("tests/test_price.py", 0.9, 1), ("tests/test_names.py", 0.1, 0)])
        d = eng.select()
    assert any(r.startswith("risk scores are not recalibrated yet: 1 affected and 1 unaffected") for r in d.reasons)
