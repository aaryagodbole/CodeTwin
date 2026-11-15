"""`codetwin outcomes import REPORT.xml...`: add CI test results (JUnit XML, any language) to the outcome history."""
from pathlib import Path

from ._util import engine

NAME, HELP, ORDER = "outcomes", "import CI test results (JUnit XML) into the outcome history used by `why`", 58


def add_arguments(p) -> None:
    p.add_argument("action", choices=["import"])
    p.add_argument("reports", nargs="+", type=Path)
    p.add_argument("--sha", help="commit the reports belong to (default: HEAD)")


def run(args) -> int:
    from ..triage.junit import read
    with engine(args) as eng:
        sha = args.sha or eng.head()
        got, unmapped = read(args.reports, eng.tests_now())
        eng.store.add_outcomes(sha, got, "ci")
    failed = sum(1 for v in got.values() if v)
    print(f"{len(got)} test files ({failed} failing) recorded for {sha[:10]}"
          + (f"; {len(unmapped)} test cases could not be mapped to a test file" if unmapped else ""))
    return 0
