"""The Change module: one baseline rule, parsed once, history bounded at the base."""
from __future__ import annotations

from pathlib import Path

import pytest

from codetwin.cli import main
from codetwin.engine import Engine


def _recorded(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text() + "\n# changed\n")


def test_the_working_tree_is_parsed_once_per_change(toy_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _recorded(toy_repo)
    with Engine(toy_repo) as eng:
        calls = []
        real = eng.lang.facts
        monkeypatch.setattr(eng.lang, "facts", lambda: calls.append(1) or real())
        eng.select()                     # features, impact, every report section
        assert len(calls) == 1


def test_selection_and_impact_use_the_same_base(toy_repo: Path) -> None:
    _recorded(toy_repo)
    with Engine(toy_repo) as eng:
        ch = eng.change()
        assert ch.base == eng.store.latest_run_sha() and ch.source_files == ["src/shop/price.py"]
        assert ch.impact().tests and ch.changed_since(ch.base) is ch.diff


def test_without_a_recording(toy_repo: Path) -> None:
    main(["-C", str(toy_repo), "init"])
    with Engine(toy_repo) as eng:
        with pytest.raises(RuntimeError, match="no recorded run yet"):
            eng.change()
        ch = eng.change(require_run=False)
        assert ch.base == "HEAD" and ch.prev is None and ch.impact(["src/shop/price.py"]).tests is not None
