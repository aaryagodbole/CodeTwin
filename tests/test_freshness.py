"""Tests for the freshness report section."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from codetwin.cli import main
from codetwin.config import Config
from codetwin.report import Context
from codetwin.report.freshness import DEFAULT_STALE_AFTER, contribute, get_stale_after


def _commit(repo: Path, msg: str) -> None:
    """Helper to create a git commit in the throwaway test repository."""
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "--allow-empty", "-m", msg],
        cwd=repo,
        check=True,
        capture_output=True,
    )


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
    assert freshness["summary"] == "recorded evidence is 2 commits old (not stale)"


def test_merge_commits_counted(toy_repo: Path, capsys: Any) -> None:
    """Commits brought in by merges and the merge commit itself are all counted."""
    # 1. Initialize and record at the current commit
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])

    # 2. Create side branch with 3 empty commits
    subprocess.run(["git", "checkout", "-b", "side"], cwd=toy_repo, check=True)
    for i in range(3):
        _commit(toy_repo, f"side {i}")

    # 3. Checkout previous branch and merge side with --no-ff
    subprocess.run(["git", "checkout", "-"], cwd=toy_repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "merge", "--no-ff", "-m", "merge side", "side"],
        cwd=toy_repo,
        check=True,
    )

    # 4. Run select --json
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 4
    assert freshness["stale"] is False
    assert freshness["summary"] == "recorded evidence is 4 commits old (not stale)"


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

    # 4. Run select --json and verify freshness is stale with exact summary comparison
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 2
    assert freshness["stale"] is True
    assert freshness["stale_after"] == 1
    assert freshness["summary"] == "recorded evidence is 2 commits old (stale, limit 1); run `codetwin record`"


def test_boundary_stale_after_two(toy_repo: Path, capsys: Any) -> None:
    """With stale_after = 2, exactly 2 commits is not stale; 3 commits is stale."""
    main(["-C", str(toy_repo), "init"])
    cfg_file = toy_repo / ".codetwin.toml"
    cfg_file.write_text(cfg_file.read_text() + "\n[freshness]\nstale_after = 2\n")
    main(["-C", str(toy_repo), "record"])

    # Exactly 2 commits -> stale False
    _commit(toy_repo, "commit 1")
    _commit(toy_repo, "commit 2")

    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 2
    assert freshness["stale"] is False
    assert freshness["summary"] == "recorded evidence is 2 commits old (not stale)"

    # 3rd commit -> stale True
    _commit(toy_repo, "commit 3")

    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] == 3
    assert freshness["stale"] is True
    assert freshness["summary"] == "recorded evidence is 3 commits old (stale, limit 2); run `codetwin record`"


def test_head_older_than_recorded_commit(toy_repo: Path, capsys: Any) -> None:
    """When HEAD is older than the recorded commit (git checkout HEAD~2), age is unknown."""
    _commit(toy_repo, "commit 1")
    _commit(toy_repo, "commit 2")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])

    # Checkout two commits back
    subprocess.run(["git", "checkout", "-q", "HEAD~2"], cwd=toy_repo, check=True)

    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] is None
    assert freshness["stale"] is False
    assert freshness["summary"] == "current checkout is not based on the recorded commit; age is unknown"


def test_different_branch(toy_repo: Path, capsys: Any) -> None:
    """When HEAD is on a branch that diverged from base, age is unknown."""
    # 1. Start on branch-a and commit
    subprocess.run(["git", "checkout", "-b", "branch-a"], cwd=toy_repo, check=True, capture_output=True)
    _commit(toy_repo, "commit on branch a 1")

    # 2. Branch off to branch-b and commit
    subprocess.run(["git", "checkout", "-b", "branch-b"], cwd=toy_repo, check=True, capture_output=True)
    _commit(toy_repo, "commit on branch b 1")

    # 3. Checkout branch-a, make another commit, init and record
    subprocess.run(["git", "checkout", "branch-a"], cwd=toy_repo, check=True, capture_output=True)
    _commit(toy_repo, "commit on branch a 2")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])

    # 4. Switch to diverged branch-b and run select --json
    subprocess.run(["git", "checkout", "branch-b"], cwd=toy_repo, check=True, capture_output=True)
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)

    freshness = out["extras"]["freshness"]
    assert freshness["commits_behind"] is None
    assert freshness["stale"] is False
    assert freshness["summary"] == "current checkout is not based on the recorded commit; age is unknown"

    # 5. More commits on HEAD's side since the split than the limit allows: stale although the age is unknown
    cfg_file = toy_repo / ".codetwin.toml"
    cfg_file.write_text(cfg_file.read_text() + "\n[freshness]\nstale_after = 0\n")
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    freshness = json.loads(capsys.readouterr().out)["extras"]["freshness"]
    assert freshness["commits_behind"] is None
    assert freshness["stale"] is True
    assert freshness["summary"] == (
        "current checkout is not based on the recorded commit and has 1 commit since they split "
        "(stale, limit 0); run `codetwin record`"
    )


def test_shallow_boundary_in_range(tmp_path: Path) -> None:
    """A shallow repository where a shallow boundary commit lies in <base>..HEAD returns unknown."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "1 (base)"], cwd=repo, check=True)
    base_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    # Branch a from base
    subprocess.run(["git", "checkout", "-b", "branch-a"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "2 (branch a)"], cwd=repo, check=True)

    # Branch b from base
    subprocess.run(["git", "checkout", "-b", "branch-b", base_sha], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "3 (branch b)"], cwd=repo, check=True)
    b_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    # Merge branch a into branch b
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-ff", "-m", "merge", "branch-a"], cwd=repo, check=True)

    # Mark b_sha as a shallow root inside <base>..HEAD
    shallow_file = repo / ".git" / "shallow"
    shallow_file.write_text(b_sha + "\n", encoding="utf-8")

    cfg = Config(root=repo)
    ctx = Context(
        cfg=cfg,
        store=None,
        base=base_sha,
        prev=None,
        diff={},
        rows={},
        scores={},
        decision=None,
        is_source=lambda _: True,
    )
    res = contribute(ctx)
    assert res["commits_behind"] is None
    assert res["stale"] is False
    assert res["summary"] == "history is incomplete in a shallow clone; age is unknown"

    # The visible count is a lower bound: past the limit it is stale even though the exact age is unknown
    ctx_low = Context(cfg=Config(root=repo, raw={"freshness": {"stale_after": 1}}), store=None, base=base_sha,
                      prev=None, diff={}, rows={}, scores={}, decision=None, is_source=lambda _: True)
    res_low = contribute(ctx_low)
    assert res_low["commits_behind"] is None
    assert res_low["stale"] is True
    assert res_low["summary"] == (
        "recorded evidence is at least 3 commits old (stale, limit 1; shallow clone); run `codetwin record`"
    )

    # When boundary is base itself (not strictly in range <base>..HEAD), range is complete
    shallow_file.write_text(base_sha + "\n", encoding="utf-8")
    res_base_shallow = contribute(ctx)
    assert res_base_shallow["commits_behind"] == 3
    assert res_base_shallow["stale"] is False
    assert res_base_shallow["summary"] == "recorded evidence is 3 commits old (not stale)"


def test_shallow_clone_incomplete_and_unshallow(tmp_path: Path) -> None:
    """A shallow clone where recorded commit and HEAD are disconnected gives unknown; unshallow gives 25."""
    src = tmp_path / "src"
    src.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "init"],
        cwd=src,
        check=True,
    )

    clone = tmp_path / "clone"
    url = src.resolve().as_uri()
    try:
        subprocess.run(
            ["git", "-c", "protocol.file.allow=always", "clone", "--depth", "1", url, str(clone)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        if "Could not read from remote repository" in (e.stderr or ""):
            pytest.skip(f"git clone file:// not supported in this execution environment: {e.stderr.strip()}")
        raise

    sha_a = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=clone, capture_output=True, text=True, check=True
    ).stdout.strip()

    for i in range(25):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", f"c{i}"],
            cwd=src,
            check=True,
        )

    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "fetch", "--depth", "1", "origin"], cwd=clone, check=True
    )
    fetch_sha = subprocess.run(
        ["git", "rev-parse", "FETCH_HEAD"], cwd=clone, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "checkout", "-q", fetch_sha], cwd=clone, check=True)

    cfg = Config(root=clone)
    ctx = Context(
        cfg=cfg,
        store=None,
        base=sha_a,
        prev=None,
        diff={},
        rows={},
        scores={},
        decision=None,
        is_source=lambda _: True,
    )
    res = contribute(ctx)
    assert res["commits_behind"] is None
    assert res["stale"] is False
    assert res["summary"] == "history is incomplete in a shallow clone; age is unknown"

    # The same shallow clone does not have a commit older than its depth: unknown, not stale
    ctx_old = Context(cfg=cfg, store=None, base="0" * 40, prev=None, diff={}, rows={}, scores={},
                      decision=None, is_source=lambda _: True)
    res_old = contribute(ctx_old)
    assert res_old["stale"] is False
    assert res_old["summary"] == "history is incomplete in a shallow clone; age is unknown"

    # Unshallow the clone to get full history
    subprocess.run(["git", "-c", "protocol.file.allow=always", "fetch", "--unshallow", "origin"], cwd=clone, check=True)
    res_unshallow = contribute(ctx)
    assert res_unshallow["commits_behind"] == 25
    assert res_unshallow["stale"] is True
    assert res_unshallow["stale_after"] == DEFAULT_STALE_AFTER
    assert res_unshallow["summary"] == "recorded evidence is 25 commits old (stale, limit 20); run `codetwin record`"


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
    assert freshness["summary"] == "recorded evidence is 1 commit old (not stale)"


def test_get_stale_after_defaults_and_fallbacks(toy_repo: Path) -> None:
    """Verify that get_stale_after handles valid, invalid, negative, and missing settings using real Config."""
    # Missing [freshness] table falls back to default 20
    assert get_stale_after(Config(root=toy_repo, raw={})) == DEFAULT_STALE_AFTER

    # Valid positive integer or zero
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": {"stale_after": 10}})) == 10
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": {"stale_after": 0}})) == 0

    # Negative integer falls back to default 20
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": {"stale_after": -5}})) == DEFAULT_STALE_AFTER

    # Non-integer types fall back to default 20
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": {"stale_after": "10"}})) == DEFAULT_STALE_AFTER
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": {"stale_after": 15.5}})) == DEFAULT_STALE_AFTER
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": {"stale_after": True}})) == DEFAULT_STALE_AFTER
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": {"stale_after": False}})) == DEFAULT_STALE_AFTER

    # List value for section (e.g. [[freshness]] array of tables in TOML)
    assert get_stale_after(Config(root=toy_repo, raw={"freshness": [{"stale_after": 5}]})) == DEFAULT_STALE_AFTER


def test_freshness_unknown_base_commit(toy_repo: Path) -> None:
    """When the base commit does not exist or is empty, freshness returns unknown age."""
    cfg = Config(root=toy_repo, raw={})

    # Non-existent commit SHA
    ctx_missing = Context(
        cfg=cfg,
        store=None,
        base="0000000000000000000000000000000000000000",
        prev=None,
        diff={},
        rows={},
        scores={},
        decision=None,
        is_source=lambda _: True,
    )
    res1: dict[str, Any] = contribute(ctx_missing)
    assert res1["commits_behind"] is None
    assert res1["stale"] is True
    assert res1["stale_after"] == DEFAULT_STALE_AFTER
    assert res1["summary"] == (
        "recorded commit is no longer in this history (rewritten or deleted); run `codetwin record`"
    )

    # Empty base commit
    ctx_empty = Context(
        cfg=cfg,
        store=None,
        base="",
        prev=None,
        diff={},
        rows={},
        scores={},
        decision=None,
        is_source=lambda _: True,
    )
    res2: dict[str, Any] = contribute(ctx_empty)
    assert res2["commits_behind"] is None
    assert res2["stale"] is False
    assert res2["summary"] == "recorded commit not found; age is unknown"


def test_non_repository_root_is_not_swallowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A root that is not a git repository is a real error, so report.build() can show it."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    ctx = Context(
        cfg=Config(root=tmp_path, raw={}),
        store=None,
        base="a" * 40,
        prev=None,
        diff={},
        rows={},
        scores={},
        decision=None,
        is_source=lambda _: True,
    )
    with pytest.raises((RuntimeError, OSError)):
        contribute(ctx)


def test_missing_git_binary_is_not_swallowed(toy_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git missing from PATH is a real error and is not reported as an unknown age."""
    monkeypatch.setenv("PATH", "")
    ctx = Context(
        cfg=Config(root=toy_repo, raw={}),
        store=None,
        base="a" * 40,
        prev=None,
        diff={},
        rows={},
        scores={},
        decision=None,
        is_source=lambda _: True,
    )
    with pytest.raises((RuntimeError, OSError)):
        contribute(ctx)


def test_other_git_failure_on_verify_is_not_swallowed(toy_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A git failure while looking up the recorded commit (corrupt repository, lock) is not an unknown age."""
    import codetwin.report.freshness as freshness

    real_run = subprocess.run

    def run(cmd: list[str], *a: Any, **kw: Any) -> Any:
        if "--verify" in cmd:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: bad object database")
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(freshness.subprocess, "run", run)
    ctx = Context(cfg=Config(root=toy_repo, raw={}), store=None, base="a" * 40, prev=None, diff={}, rows={},
                  scores={}, decision=None, is_source=lambda _: True)
    with pytest.raises(RuntimeError, match="bad object database"):
        contribute(ctx)
