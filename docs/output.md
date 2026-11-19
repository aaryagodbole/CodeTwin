# Output contract (`codetwin select --json`, MCP `verify_change` / `recommend_tests`)

```json
{
  "schema": 1,
  "decision": "proceed",            // "proceed" | "abstain"   (MCP verify_change: "proceed" | "run_more")
  "residual_risk": 0.031,           // estimated chance that a skipped test was affected
  "threshold": 0.42,                // calibrated threshold, or null in budget mode
  "mode": "calibrated",             // "calibrated" | "budget 25%" | "no-source-change"
  "selected": ["tests/test_price.py"],
  "reasons": ["estimated residual risk 3.1% <= target 10%", "src/x.py: dynamic calls (getattr) cannot be followed statically"],
  "extras": {
    "changed_files": {"files": {"src/shop/price.py": 1}, "summary": "1 source files, 1 changed lines"}
  }
}
```

Rules:

- Built-in sections: `changed_files`, `semantic_noop` (`kind`: noop | annotation | semantic | no-source,
  `sufficient_tests` for no-ops), `change_risk` (`q`, `r_product`, `features`, `triggers`, `above_target`),
  `promise` (`observed`, `ci95`, `alert`) and `changed_symbols` (`symbols`: changed functions, methods and
  classes with `name`, `kind`, `file`, `start`, `end`, `tests_before`; `untested`: those no test executed) and
  `contracts` (`breaking`: each breaking contract change with `consumers` and `tests`; see `docs/contracts.md`) and
  `cross_repo` (`repos`: per connected repository its `consumers`, `tests` and `unknowns`; see `docs/crossrepo.md`) and
  `test_gaps` (`files`: changed lines that ran under no test, with `lines`, `changed_lines`, and enclosing `symbols`) and
  `freshness` (`commits_behind`: number of commits since recorded commit, or `null` when the age cannot be established
  [no recorded commit, recorded commit not present in this checkout (deleted, squashed or missing from a shallow clone),
  not an ancestor of HEAD such as an older checkout or different branch, or history is incomplete in a shallow clone];
  counts every commit reachable from HEAD but not from the recorded commit, including commits brought in by merges
  (deliberately not `--first-parent`: merged commits change the code like local ones; raise `stale_after` if you merge often).
  A git failure that is not an unknown commit, such as git missing or a root that is not a repository, is not reported
  here: the section fails and `report.build()` shows its error; `stale`: true when `commits_behind > stale_after`, false when `commits_behind` is `null`;
  `stale_after`: limit from `[freshness] stale_after` defaulting to 20; `summary`: one-line text; consumers must not do
  `commits_behind > 0` or print "null commits" when `commits_behind` is `null`, and should display `summary` instead).
- `extras` holds one object per report section (`src/codetwin/report/<name>.py`). Each has a one-line `summary`;
  the rest is section-specific and documented in the section's module docstring.
- Adding a section or a key is **not** a breaking change. Renaming or removing a top-level key is: bump
  `OUTPUT_SCHEMA` in `selection.py` and update `extensions/vscode/src/cli.ts` in the same pull request.
- Consumers (VS Code, GitHub Action, dashboard) must ignore sections they do not know.