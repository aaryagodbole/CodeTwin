# Domain language

The words this codebase, its docs and its reviews use. Code names follow them; when a new concept appears, add it
here in the same pull request.

## Evidence

- **Recorded run.** One full run of the test suite on a clean commit, with per-test coverage, durations,
  failures and import-time lines (`TestRun`). Made by `codetwin record`. A run that did not finish (timeout,
  collection error, signal) is *incomplete*: stored, but never the default base.
- **Static facts.** What the parser knows about each file: dependencies, function spans, load-time lines,
  dynamic constructs (`FileFacts`). Stored for the recorded commit; computed again for the working tree.
- **Base (baseline).** The recorded commit a change is compared with: by default the newest *complete*
  recorded run. Only evidence that exists at the base may inform a decision (no look-ahead).
- **Co-change history.** Which files changed together in earlier first-parent commits, read up to the base only.
- **Unknown.** A link the analysis cannot resolve (a dynamic call, an unparsed file). Reported, never read as
  "no dependency".

## A change and its decision

- **Change.** The working tree's changed lines against the base. `ChangeContext` (`src/codetwin/change.py`)
  holds everything known about one change before its tests run: base, recorded run, static facts then and now,
  diff, history, feature rows, impact and evidence notes. Built once by `Engine.change()`.
- **Evidence notes.** Sentences that say what weakens a change's evidence: thin or missing history, an
  incomplete run, a newer run that was skipped, too few recalibration examples.
- **Feature rows.** The risk model's input per test (coverage overlap, import distance, name match, co-change,
  changed test).
- **Forced test.** An added or changed test: it always runs and teaches the model nothing.
- **Selection policy.** The rules from scores to a decision (Algorithm 1 of the paper): the conformal
  threshold or a time budget, the residual risk, abstention, files without runtime evidence. One pure function,
  `selection.choose()`.
- **Decision.** The selected tests, the verdict (`proceed` or `abstain`), the residual risk of the tests that run
  (`residual_risk`) and of the first selection (`risk_before`), the mode, the reasons and the report sections
  (`extras`). Its JSON form is the output contract (`docs/output.md`).
- **Mode.** `calibrated` (conformal threshold), `budget N%` (time budget) or `no-source-change` (only tests
  changed).
- **Report section.** Extra data attached to every decision (`src/codetwin/report/<name>.py`), read from the
  change only; it never changes the decision.

## Learning

- **Outcome.** Whether a decision missed a test the change affected, found by `codetwin learn` from a full run
  on the changed tree. The only place the new run is used.
- **Calibration ledger.** What has been learned from outcomes (`src/codetwin/risk/ledger.py`): the calibration
  set, the recalibration points, the adaptive level and the outcomes, with the rules that keep them consistent.
- **Calibration set.** For each labelled calibrated change, the smallest score of an affected test.
- **Adaptive level (alpha_t).** The level conformal risk control is run at, moved after each calibrated outcome
  (ACI). **Target (alpha)** is the miss rate the user asked for.
- **Recalibration.** The isotonic map from model scores to observed frequencies, used once there are enough
  affected and unaffected examples.

## Languages

- **Language spec.** One file per language in `src/codetwin/lang/specs/`: extensions, test globs, build markers
  and which adapter handles it. Data, not code paths in shared modules.
- **Language adapter.** The code that analyses and runs one language: the generic tree-sitter adapter, or a
  built-in one (Python: ast, pytest and coverage.py).

## Reading

- **Read model (view).** A number or list the dashboard shows, defined once in `src/codetwin/views.py` and served
  by the local API; `codetwin push` sends the same values to the cloud.
