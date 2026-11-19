# 0004. Deep modules inside the engine: Change, Selection policy, Calibration ledger, read models, language specs

Status: Proposed (November 2026)

## Context

The engine grew one feature at a time. By v0.2.0 an architecture review found five places where knowledge was
spread across callers instead of held by one module (the full review: issue #71, plan task 2.2 onwards):

- **The base of a change** was resolved in 13 places (`args.base or store.latest_run_sha()`, some falling back to
  `HEAD`, some not), and the working tree was parsed again by each command, MCP tool and report section that
  needed it. Report sections received twelve untyped fields, three of them callables. A rule such as "the base
  must be a complete run" (#99) had to reach every copy.
- **The decision** was made in `selection.decide()` and then changed by `Engine.select()` (files without runtime
  evidence), which is how a stored risk came to describe a selection that did not run (#96, E1 and E2). The
  paper's rules could only be tested through git, SQLite and the model.
- **Learning** called eight store methods from `Engine.learn()`, which held the rules (one label per decision,
  one transaction, the adaptive level moves only after calibrated decisions). Three readers rebuilt the
  calibration state from raw rows.
- **Dashboard numbers** (summary, decision rows) were computed in the local API, in the cloud and in new
  endpoints, each slightly differently (#77).
- **Python** was a special case in shared code (`name == "python"` in the language factory, detection, config
  writing, weakcheck and a report section), against the rule that no language is hard-coded.

## Decision

Deepen five modules. Each has a small interface, holds its rules, and is tested through that interface.

1. **Change** (`codetwin/change.py`). `Engine.change(base)` builds one `ChangeContext` per change: the base,
   its recorded run and static facts, the diff, the working tree's facts and tests (parsed once), history up to
   the base, feature rows, impact and evidence notes, each computed on first use. Commands, MCP tools, the server
   and report sections read it; `report.Context.of(change, ...)` keeps the old fields for existing sections.
2. **Selection policy** (`selection.choose()`, `selection.only_tests()`). A pure function from feature rows,
   scores, the calibration state and the change's evidence to the finished `Decision`. Nothing changes a decision
   after it returns. `Engine.select()` computes inputs and stores the result.
3. **Calibration ledger** (`risk/ledger.py`). `state()` for selection and reports; `label()` and
   `label_unscored()` as the only writers of calibration, recalibration, adaptive level and outcomes.
4. **Read models** (`codetwin/views.py`). Summary, decision rows, decision detail, run numbers and calibration
   points, defined once; the local API serialises them and `codetwin push` takes its numbers from them.
5. **Language specs choose the adapter.** Every language, Python included, is a spec in `lang/specs/` whose
   `adapter` field names the adapter (`generic` or a built-in one registered in `lang.ADAPTERS`).
   Language-specific behaviour that shared code needs (config template, no-op wording, whether every function
   can be mutated, whether `packages` is read) is an adapter attribute or method.

Not done: a storage seam for SQLite and Postgres. The engine has one storage adapter, and the cloud keeps its
own schema by design (ADR 0003). One adapter makes it a hypothetical seam. Revisit when a second engine-side
backend is real.

## Consequences

- One place per rule: the base rule, look-ahead, the decision, the learning invariants, each dashboard number.
- The paper's selection rules have table tests without git or a database (`tests/test_selection_policy.py`).
- The working tree is parsed once per decision (it was parsed again by impact and by four report sections).
- Behaviour is unchanged. The dashboard demo snapshot, which replays ten select and learn cycles through the API,
  is identical before and after.
- `Engine.analyse()` and `Engine.without_runtime_evidence()` are gone; `Engine.change()` returns a
  `ChangeContext` instead of a tuple. New code should read `ctx.change` in report sections.
- Still open: splitting the language adapter's interface into file classification, static analysis and test
  running (so `Multi` stops forwarding eighteen methods). That change touches the Python evidence path the paper
  depends on and is scheduled after the paper submission.
