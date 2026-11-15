"""Why did a test fail? Failure timeline, first-failing window, ranked suspect commits and a likely cause.

Evidence (any language): the append-only outcome history (`codetwin record`, CI JUnit reports imported with
`codetwin outcomes import`, reruns), the commit history, and the test's recorded coverage before it failed.

- **Timeline:** every recorded outcome of the test, in time order, with its commit.
- **Window:** the commits after the last passing commit up to the first failing commit of the current failure.
- **Suspects:** commits in the window, ranked by how directly they touch what the test exercises: lines the test
  executed (strongest), files it executed, the test file itself, files it imports, then anything else.
- **Likely cause** (a hypothesis, stated with its evidence, never a verdict):
  `flaky` (different outcomes on the same commit, or mixed results on rerun), `test-changed`, `regression`
  (a suspect touches code the test executed), `environment-or-unknown` (nothing the test exercises changed).
"""
from __future__ import annotations

from .analysis import triage

__all__ = ["triage"]
