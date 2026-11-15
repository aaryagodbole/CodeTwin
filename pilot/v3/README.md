# Study v3 extensions

Computed on the v2 data with the v2 protocol (same test-level model, splits and selections). Run:

```bash
CT_PILOT=<dir with analyze.py and data/> CT_REPOS=<dir with bare clones of the 8 projects> python pilot/v3/run_v3.py
```

Output: `pilot/v3/results/v3.json`.

| Part | What | Main result (history projects, 332 test changes) |
|---|---|---|
| B | change-level risk q(c) instead of the product formula r(c) | ACI 10%: mean 8.9% vs observed 9.3% (r(c): 12.7%); Brier 0.062 vs 0.076; ECE 0.037 vs 0.067 |
| A | abstain when q(c) > target (`qrule`), and an online selective rule | qrule at 5%: miss among proceeded 2.5% (6 of 240; NameRTS commits 4.7%); online rule does not converge on these short histories |
| N | semantic no-op changes (AST identical after removing docstrings) | 41 of 332 are no-ops, none changed any test outcome |
| W | covered-but-unchecked changed lines (surviving seeded faults) | 105 of 209 changes that line coverage handled safely had an unchecked changed line |
