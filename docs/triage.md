# Why did this test fail?

`codetwin why TEST` answers when a test file started failing, which commits are suspects and what the likely cause
is. It works for every language: it reads outcomes, commits and coverage, not source code.

**Outcome history.** Every `codetwin record` appends the outcome of each test file. CI results can be added from
JUnit XML reports, which almost every test runner writes (pytest `--junitxml`, Jest/Vitest/Mocha reporters, Maven
Surefire, Gradle, go-junit-report, cargo-nextest, dotnet, PHPUnit):

```bash
codetwin outcomes import build/test-results/*.xml --sha "$GITHUB_SHA"
```

History is append-only, so several runs of one commit are kept; that is how flaky tests show up.

**Window and suspects.** For a failing test, the window is the commits after its last passing outcome up to its
first failing one (uncommitted changes count when the failure is in the working tree). Suspects are ranked by
what they changed: lines the test executed in the last passing run (5), the test file itself (3), other files it
executed (2), files it imports (1).

**Likely cause** (a hypothesis with its evidence, never a verdict): `flaky` (different outcomes on the same
commit, or mixed results with `--rerun N`), `test-changed`, `regression` (a suspect changed code the test
executed), `environment-or-unknown` (nothing the test exercises changed: a dependency, the runner, data or time).
With `--rerun N` and every rerun passing, a regression is reported as `regression-not-reproduced`.

**Unknowns:** no recorded outcome, a test that has never passed, or no coverage for the last passing commit
(suspects are then ranked by files only).

MCP: `why_failed(test)`.
