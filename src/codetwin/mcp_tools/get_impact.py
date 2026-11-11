from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def get_impact(files: list[str]) -> dict:
        """Tests that reach the given source files, with how each link was found, and unresolved links."""
        with Engine(root) as eng:
            imp = eng.impact(files)
        return {"tests": {t: sorted(v) for t, v in imp.tests.items()}, "unknowns": imp.unknowns}
