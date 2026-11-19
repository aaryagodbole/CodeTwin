"""Points from the merge review of the engine architecture (#104)."""
from __future__ import annotations

import math
from types import SimpleNamespace

from codetwin import views
from codetwin.lang import adapter_class, default_language, load_specs


def test_run_numbers_never_return_nan() -> None:
    """/api/summary is serialised with allow_nan=False: a NaN wall time must become null, not a 500."""
    run = SimpleNamespace(durations={"t": 1.0}, wall=math.nan)
    assert views.run_numbers(run) == {"test_files": 1, "suite_seconds": None}


def test_adapter_class_accepts_aliases_and_any_case() -> None:
    """`languages = ["Python", "py"]` must keep the Python adapter (and with it the configured packages)."""
    python = adapter_class("python")
    assert adapter_class("Python") is python and adapter_class("py") is python


def test_load_specs_returns_a_copy() -> None:
    specs = load_specs()
    specs.clear()
    assert load_specs()                      # the cached discovery is not changed by a caller


def test_semantic_noop_without_a_language_uses_the_default_wording() -> None:
    """A report Context built without `lang` keeps the default language's caveat (docstrings read at run time)."""
    from codetwin.report import semantic_noop

    default = adapter_class(default_language())
    ctx = SimpleNamespace(cfg=SimpleNamespace(root="."), base="HEAD", diff={}, is_source=lambda _: True, lang=None,
                          rows={})
    out = semantic_noop.contribute(ctx)
    assert out["kind"] == "no-source"
    # the wording a no-op would get is the default language's
    assert getattr(default, "noop_description", None)
