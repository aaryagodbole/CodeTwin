"""Tests for the freshness report section."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from codetwin.cli import main
from codetwin.report.freshness import DEFAULT_STALE_AFTER, contribute, get_stale_after


def _commit(repo: Path, msg: str) -> None:
    """Helper to create a git commit in the throwaway test repository."""
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--allow-empty", "-m", msg],
        cwd=repo,
        check=True,
        capture_output=True,
    )


class _DummyConfig:
    """Mock config object for testing get_stale_after with various [freshness] tables."""

    def __init__(self, section_data: Any) -> None:
        self._data = section_data
        self.root = Path(".")

    def section(self, name: str) -> Any:
        if name == "freshness":
            return self._data
        return {}


class _DummyContext:
    """Mock Context object for unit testing contribute()."""

    def __init__(self, base: str, cfg: Any = None) -> None:
        self.base = base
        self.cfg = cfg


def test_two_commits_after_recording_gives_count_two(toy_repo: Path, capsys: Any) -> None:
    """Two commits made after recording give a commit count of 2 and not stale."""
    # 1. Initialize CodeTwin and record evidence at the current commit
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])

    # 2. Make two commits after the recording
    _commit(toy_repo, "commit after record 1")
    _commit(toy_repo, "commit after record 2")

    # 3. Run select --json to inspect the report extras
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 2
    assert freshness["stale"] is False
    assert freshness["stale_after"] == DEFAULT_STALE_AFTER
    assert "2 commits old" in freshness["summary"]
    assert "not stale" in freshness["summary"]


def test_stale_after_one_makes_two_commits_stale(toy_repo: Path, capsys: Any) -> None:
    """Setting stale_after = 1 in .codetwin.toml marks 2 commits as stale and suggests recording."""
    # 1. Initialize CodeTwin and configure stale_after = 1
    main(["-C", str(toy_repo), "init"])
    cfg_file = toy_repo / ".codetwin.toml"
    cfg_file.write_text(cfg_file.read_text() + "\n[freshness]\nstale_after = 1\n")

    # 2. Record evidence at this commit
    main(["-C", str(toy_repo), "record"])

    # 3. Make two commits after the recording
    _commit(toy_repo, "commit 1")
    _commit(toy_repo, "commit 2")

    # 4. Run select --json and verify freshness is stale
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 2
    assert freshness["stale"] is True
    assert freshness["stale_after"] == 1
    assert "2 commits old" in freshness["summary"]
    assert "stale" in freshness["summary"]
    assert "codetwin record" in freshness["summary"]


def test_zero_commits_at_record(toy_repo: Path, capsys: Any) -> None:
    """When select runs on the recorded commit, commits_behind is 0."""
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])

    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 0
    assert freshness["stale"] is False
    assert freshness["stale_after"] == DEFAULT_STALE_AFTER
    assert freshness["summary"] == "evidence was recorded at the current commit"


def test_one_commit_singular_wording(toy_repo: Path, capsys: Any) -> None:
    """A single commit behind uses singular '1 commit' in the summary."""
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    _commit(toy_repo, "single commit")

    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 1
    assert freshness["stale"] is False
    assert "1 commit old" in freshness["summary"]
    assert "not stale" in freshness["summary"]


def test_get_stale_after_defaults_and_fallbacks() -> None:
    """Verify that get_stale_after handles valid, invalid, negative, and missing settings."""
    # Missing cfg or missing table falls back to default 20
    assert get_stale_after(None) == DEFAULT_STALE_AFTER
    assert get_stale_after(_DummyConfig({})) == DEFAULT_STALE_AFTER
    assert get_stale_after(_DummyConfig("not a dict")) == DEFAULT_STALE_AFTER

    # Valid positive integer or zero
    assert get_stale_after(_DummyConfig({"stale_after": 10})) == 10
    assert get_stale_after(_DummyConfig({"stale_after": 0})) == 0

    # Negative integer falls back to default 20
    assert get_stale_after(_DummyConfig({"stale_after": -5})) == DEFAULT_STALE_AFTER

    # Non-integer types fall back to default 20
    assert get_stale_after(_DummyConfig({"stale_after": "10"})) == DEFAULT_STALE_AFTER
    assert get_stale_after(_DummyConfig({"stale_after": 15.5})) == DEFAULT_STALE_AFTER
    assert get_stale_after(_DummyConfig({"stale_after": True})) == DEFAULT_STALE_AFTER
    assert get_stale_after(_DummyConfig({"stale_after": False})) == DEFAULT_STALE_AFTER


def test_freshness_unknown_base_commit(toy_repo: Path) -> None:
    """When the base commit does not exist or is empty, freshness returns unknown age."""
    # Non-existent commit SHA
    ctx_missing = _DummyContext(base="0000000000000000000000000000000000000000", cfg=_DummyConfig({}))
    ctx_missing.cfg.root = toy_repo  # type: ignore[attr-defined]
    res1: dict[str, Any] = contribute(ctx_missing)  # type: ignore[arg-type]

    assert res1["commits_behind"] is None
    assert res1["stale"] is False
    assert res1["stale_after"] == DEFAULT_STALE_AFTER
    assert "age is unknown" in res1["summary"]

    # Empty base commit
    ctx_empty = _DummyContext(base="", cfg=_DummyConfig({}))
    res2: dict[str, Any] = contribute(ctx_empty)  # type: ignore[arg-type]

    assert res2["commits_behind"] is None
    assert res2["stale"] is False
    assert "age is unknown" in res2["summary"]

