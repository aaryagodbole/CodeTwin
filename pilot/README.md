# CodeTwin AI – study v2

Scripts behind the experiments in the paper on CodeTwin AI (calibrated, blind-spot-aware regression test selection).
Study v1 (40 commits per project, the earlier paper draft) is preserved on the `paper-v1` / `paper-v1-data` branches.

| File | What it does |
|---|---|
| `collect.py` | For each evaluated change: git diff; static facts of every file (imports, dynamic-call markers and their lines, function spans, import-time statement lines); per-test-file coverage, run times and per-test-case outcomes of the parent and of the new version; seeded faults (mutants) on changed lines and the test files that detect them. History mode uses the last N mainline commits; pairs mode uses the commit pairs of the NameRTS replication package. |
| `analyze.py` | Ground truths (coverage of the new version, killed mutants, NameRTS ground truth), baselines (incl. the published NameRTS selections), budgeted risk ranking, conformal risk control, file- and line-level uncertainty triggers with full-suite or hybrid fallback, ablation, bootstrap CIs and paired tests. Writes `results/results.json`, `results/stats.md` and plots. |
| `namerts/` | Ground truth and published selections from the NameRTS replication package (Apache 2.0). |

Subject projects: click, marshmallow, toolz, itsdangerous, python-dateutil (history mode, up to 250 commits each, newest commit before 2026-11-10); loguru, pvlib, seaborn (NameRTS commit pairs).

## Reproduce

```bash
pip install "pytest>=8,<9" pytest-cov "coverage>=7.6" hypothesis freezegun simplejson pytz six attrs numpy scikit-learn scipy matplotlib
cd pilot
python collect.py --project click --commits 250          # one project; --shard i/k to split the work
python collect.py --project loguru --pairs namerts/gt_loguru.json
python analyze.py
```

The workflow `.github/workflows/study.yml` runs all of this in parallel shards and publishes the data and results to the `study-v2-results` branch.

## Protocol (summary)

* Evidence for a change comes only from its parent (coverage, run times, static facts) and from the new version's static facts and diff; the new version's test run is used only for the ground truth.
* Risk model: logistic regression, leave-one-project-out over the history projects.
* Calibration: the first 40% of each project's changes in time order (never used for training); the rest are test changes.
* Budgets 10/25/50% of full-suite time; target miss rates α ∈ {0.01, 0.05, 0.10, 0.20}; random baseline averaged over 20 seeds.
* Up to three mutants per change (operators ROR, AOR, LCR, UOD, BCR, CRP, RVR, SDL, ASR) on changed lines; a mutant is detected by a test file when a test case that passed on the unmutated code fails.
