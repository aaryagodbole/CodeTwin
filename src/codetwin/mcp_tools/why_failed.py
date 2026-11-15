from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def why_failed(test: str) -> dict:
        """Why a test file fails: its outcome timeline, the first failing commit and the last passing one, suspect
        commits ranked by whether they changed lines or files the test executed, and the likely cause
        (regression, test-changed, flaky, environment-or-unknown) with its evidence. A hypothesis, not a verdict."""
        from ..triage import triage
        with Engine(root) as eng:
            return triage(eng.root, eng.store, eng.facts_now(), test)
