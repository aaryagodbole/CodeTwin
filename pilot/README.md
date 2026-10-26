# CodeTwin AI – pilot study

Scripts behind the experiments in the paper *"CodeTwin AI: A Survey of Regression Test Selection and a Blind-Spot-Aware, Risk-Calibrated Framework for Code Changes"*.

| File | What it does |
|---|---|
| `collect.py` | For the last N commits of each subject project: git diff, Python `ast` import graph and dynamic-call markers, per-test-file coverage (pytest + coverage.py dynamic contexts) and run times. Writes JSON to `data/<project>/`. |
| `analyze.py` | Ground truth, baselines, risk-ranked budgeted selection, conformal risk control with abstention, trigger usefulness and ablation. Writes `results/results.json`, LaTeX table rows `results/tables_*.tex` and `results/budget.pdf`. |

Subject projects: click, marshmallow, toolz, itsdangerous, python-dateutil.

## Reproduce

```bash
pip install pytest pytest-cov "coverage>=7.6" hypothesis freezegun simplejson pytz six numpy scikit-learn matplotlib
cd pilot
python collect.py --project all --commits 40   # about 1 hour
python analyze.py
```

The GitHub Actions workflow `.github/workflows/pilot.yml` runs the same steps and publishes the data and results to the `pilot-results` branch.

## Protocol (summary)

* Evidence for a commit comes only from the previous commit (coverage) and the commit itself (diff, static analysis).
* Risk model: logistic regression trained leave-one-project-out.
* Calibration: the first 40% of each project's commits (never used for training); the rest are test commits.
* Budgets 10/25/50% of full-suite time; target miss rates α ∈ {0.05, 0.10, 0.20}; random baseline averaged over 20 seeds.
