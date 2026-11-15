"""Cross-repository evidence: which files and tests in connected repositories a change in this one may affect.

Connected repositories are declared in `.codetwin.toml`; each one depends on (uses) this repository::

    [[repos]]
    name = "web"
    path = "../web"                 # relative to this repository
    # packages = ["@acme/core"]     # optional: how `web` imports this repository (default: detected)

For a change, every dependent's files that import one of this repository's package names are *consumers*.
A consumer that also names a changed function, method or class is a `uses-changed-symbol` link; one that only
imports the package is an `imports-package` link (weaker). Tests in the dependent come from its own recorded
run (`codetwin record` there; runtime evidence) or, without one, from its static impact graph. Everything the
analysis cannot see (missing repository, no package name, dynamic imports, no test reaching a consumer) is an
unknown, never silently "no impact".
"""
from __future__ import annotations

from .analysis import RepoImpact, analyse, declared

__all__ = ["RepoImpact", "analyse", "declared"]
