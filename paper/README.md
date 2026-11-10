# Paper source

* `main.template.tex` – the paper with placeholders `<<KEY>>` for every number about our study.
* `main.tex` – generated: `cd pilot && python paper_numbers.py ../paper/main.template.tex ../paper/main.tex`
  (needs `pilot/results/results.json` from `analyze.py`; `python paper_numbers.py --list` prints every key).
* `refs.bib` – bibliography. `figures/` – figures; `budget.pdf` and `calibration.pdf` are written by `analyze.py`.

Edit the template, not `main.tex`, so that the numbers stay tied to the results. Upload `main.tex`, `refs.bib`
and `figures/` to Prism or Overleaf to compile (IEEEtran class).
