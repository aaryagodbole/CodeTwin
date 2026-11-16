# Pull-request review (`codetwin review`)

`codetwin review` reviews a change like a reviewer who has read the test evidence: it posts one summary comment
on the pull request and inline comments on the lines that need attention. Tools such as CodeRabbit ask a
language model to read the diff. CodeTwin starts from facts it measured: which tests ran each line before the
change, how much risk skipping tests leaves, which calls cannot be followed, which contracts and connected
repositories are affected. A language model can add advisory comments on top (`--llm`), but it never decides.

```bash
codetwin review                               # Markdown summary on standard output
codetwin review --format json                 # the Review as JSON (schema below)
codetwin review --format sarif -o r.sarif     # SARIF 2.1.0, for GitHub code scanning and other tools
codetwin review --decision d.json             # reuse `codetwin select --json` output instead of selecting again
codetwin review --llm                         # add advisory comments from Groq/Gemini ([llm], docs/llm.md)
codetwin review --only untested_change,contracts --skip blind_spots
codetwin review --fail-on-blocking            # exit 1 on abstention or a high/critical evidence finding
codetwin review --post-github                 # in GitHub Actions: post/update the comments (needs GITHUB_TOKEN)
```

## How it works

```
codetwin select  ─►  decision (selected tests, residual risk, report sections)
                         │
knowledge graph ─────────┤   files, symbols, tests and typed evidence edges of the recorded commit (codetwin.kg)
                         ▼
          review/analyzers/<name>.py  (auto-discovered, one file each)  ─►  Findings
                         ▼
          de-duplicate (fingerprint) ─► sort by severity ─► Review
                         ▼
     render: markdown (summary comment) · github (inline review) · sarif · json
```

## Rules

Every finding names a rule. Ids are stable: never renumber or reuse one (`src/codetwin/review/rules.py`).

| Rule | Analyzer | Severity | Raised when |
|---|---|---|---|
| CT001 | `residual_risk` | high | the calibrated selection abstained: skipping tests is not safe enough at the target α |
| CT002 | `untested_change` | medium | a changed function, method or class was executed by no test on the recorded commit |
| CT003 | `blind_spots` | low | the changed file has dynamic calls whose targets cannot be followed statically |
| CT004 | `contracts` | high (medium if no consumer found) | an OpenAPI / JSON-schema change is breaking |
| CT005 | `cross_repo` | medium (low if only unknowns) | a connected repository uses a symbol the change modifies |
| CT006 | `blind_spots` | medium | a changed file has no recorded evidence (new or unparsed) |
| CT100 | `llm_review` (off by default) | at most medium | a language model's comment on a line in the diff |

A review is **blocking** when CodeTwin abstained or an evidence finding is high or critical. LLM findings
never make a review blocking, are capped at medium, and are dropped when they point outside the diff.

## In GitHub Actions

```yaml
on: pull_request
permissions:
  contents: read
  pull-requests: write        # post the summary and inline comments
  security-events: write      # only if you upload SARIF
jobs:
  codetwin:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v7
        with: { python-version: "3.12" }
      - run: pip install -e ".[test]"         # your project's own test dependencies
      - id: codetwin
        uses: aaryagodbole/CodeTwin/action@main
        with:
          review: "true"
      - uses: github/codeql-action/upload-sarif@v4
        if: always() && steps.codetwin.outputs.sarif-file != ''
        with:
          sarif_file: ${{ steps.codetwin.outputs.sarif-file }}
          category: codetwin
```

The summary comment carries a hidden marker and is edited in place on every push. Inline comments carry the
finding's fingerprint, so a finding already on the pull request is not posted again.

## Adding an analyzer

Create `src/codetwin/review/analyzers/<name>.py`:

```python
from ..context import ReviewContext
from ..model import Finding, Severity

NAME = "my_check"
DEFAULT = True          # False = only with --only my_check


def analyze(ctx: ReviewContext) -> list[Finding]:
    sec = ctx.section("changed_symbols")        # a report section of the decision ({} if missing or failed)
    return [Finding("CT0xx", Severity.LOW, "title", "why it matters", path="src/a.py", start_line=3)]
```

Add the rule to `rules.py` first, add a test in `tests/test_review.py`, and document it in the table above.
Analyzers only read the context; they must not change the selection, the decision or the evidence store.

## Settings

```toml
[review]
analyzers = ["residual_risk", "untested_change", "blind_spots", "contracts", "cross_repo"]   # default: all evidence analyzers
skip = ["blind_spots"]
```

## Output schema (`--format json`)

```json
{"schema": 1, "decision": "proceed", "residual_risk": 0.031, "alpha": 0.1, "blocking": false,
 "counts": {"critical": 0, "high": 0, "medium": 1, "low": 0, "info": 0},
 "selected": ["tests/test_price.py"],
 "files": [{"path": "src/shop/price.py", "changed_lines": 4, "tests": ["tests/test_price.py"], "findings": 1}],
 "findings": [{"rule": "CT002", "severity": "medium", "title": "...", "message": "...", "source": "evidence",
               "path": "src/shop/price.py", "start_line": 9, "end_line": 10, "evidence": ["..."],
               "suggestion": "...", "analyzer": "untested_change", "fingerprint": "3f9c..."}],
 "notes": []}
```

Status: built and tested; not part of the paper's evaluation.
