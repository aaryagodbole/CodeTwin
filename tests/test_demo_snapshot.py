"""The dashboard demo snapshot: file naming must match `demoPath` in dashboard/src/lib/api.ts."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("demo_snapshot", ROOT / "scripts" / "demo_snapshot.py")
assert spec and spec.loader
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_snapshot_names_match_the_dashboard_client():
    # The same three cases are documented next to demoPath() in api.ts; change both together.
    assert demo.snapshot_name("/summary") == "summary.json"
    assert demo.snapshot_name("/decisions", {"limit": "10"}) == "decisions__limit-10.json"
    assert demo.snapshot_name("/graph", {"file": "src/shop/calc.py", "lines": "3-4"}) == \
        "graph__file-src_shop_calc.py__lines-3-4.json"


def test_demo_edits_still_apply_to_the_example():
    for file, old, _new in demo.EDITS:
        assert old in (demo.EXAMPLE / file).read_text(), f"{file}: {old!r}"
