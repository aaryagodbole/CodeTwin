from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def get_cross_repo_impact(base: str | None = None) -> dict:
        """Files and tests in connected repositories ([[repos]] in .codetwin.toml) that the working-tree change
        may affect: consumer files that use a changed function or class, files that only import this repository,
        the dependents' tests that reach them, and what cannot be seen (unknowns)."""
        from ..crossrepo.analysis import for_change
        with Engine(root) as eng:
            ch = eng.change(base, require_run=False)
            return for_change(eng.cfg, ch.facts_now, ch.diff, ch.is_source, eng.store, ch.base)
