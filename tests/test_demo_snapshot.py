"""The dashboard demo snapshot: file naming must match `demoName` in dashboard/src/lib/demo-path.mjs."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("demo_snapshot", ROOT / "scripts" / "demo_snapshot.py")
assert spec and spec.loader
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

CONTRACT = json.loads((ROOT / "dashboard" / "src" / "lib" / "demo-contract.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(("path", "params", "want"), CONTRACT["names"])
def test_snapshot_names_match_the_dashboard_client(path: str, params: dict[str, str], want: str) -> None:
    # The same cases are checked against the dashboard's demoName() by scripts/check_demo_build.mjs in CI.
    assert demo.snapshot_name(path, params) == want


def test_demo_edits_still_apply_to_the_example() -> None:
    for file, old, _new in demo.EDITS:
        assert old in (demo.EXAMPLE / file).read_text(), f"{file}: {old!r}"


def test_normalise_keeps_order_and_drops_run_dependent_values() -> None:
    answers = {
        "a.json": [{"recorded": 1700000050.5, "x": 1}, {"recorded": 1700000001.2}],
        "b.json": {"suite_seconds": 0.37, "nested": {"recorded": 1700000050.5}},
    }
    demo.normalise(answers)
    assert answers["a.json"] == [{"recorded": demo.EPOCH + 60.0, "x": 1}, {"recorded": demo.EPOCH}]
    assert answers["b.json"] == {"suite_seconds": 1.0, "nested": {"recorded": demo.EPOCH + 60.0}}
