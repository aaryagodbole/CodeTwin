"""Cross-repository evidence: which files and tests in connected repositories a change in this one may affect.

Connected repositories are declared in `.codetwin.toml`, as many as needed; each one depends on (uses) this
repository and is either a local folder or a git URL (cloned by `codetwin crossrepo --sync`, see `sources.py`)::

    [[repos]]
    name = "web"
    path = "../web"                 # relative to this repository
    # packages = ["@acme/core"]     # optional: how `web` imports this repository (default: detected)

    [[repos]]
    name = "mobile"
    url = "https://github.com/acme/mobile.git"

For a change, every dependent's files that import one of this repository's package names are *consumers*.
A consumer that also names a changed function, method or class is a `uses-changed-symbol` link; one that only
imports the package is an `imports-package` link (weaker). Tests in the dependent come from its own recorded
run (`codetwin record` there; runtime evidence) or, without one, from its static impact graph. Everything the
analysis cannot see (missing repository, no package name, dynamic imports, no test reaching a consumer) is an
unknown, never silently "no impact".

Tests in a dependent are those its recorded run shows executing a consumer (runtime evidence) together with those
its static import graph reaches (a superset; without a recorded run, static only). Symbol uses are found by name
in code, not in comments or strings, so `uses-changed-symbol` means "names it", which is possible-use evidence.
"""
from __future__ import annotations

from .analysis import RepoImpact, analyse, declared
from .sources import Source, connected, sync

__all__ = ["RepoImpact", "Source", "analyse", "connected", "declared", "sync"]
