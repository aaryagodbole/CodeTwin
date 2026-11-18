from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def get_cross_repo_impact(base: str | None = None) -> dict:
        """Files and tests in connected repositories ([[repos]] in .codetwin.toml) that the working-tree change
        may affect: consumer files that use a changed function or class, files that only import this repository,
        the dependents' tests that reach them, and what cannot be seen (unknowns)."""
        from ..crossrepo.analysis import for_change
        with Engine(root) as eng:
            b = base or eng.store.latest_run_sha() or "HEAD"
            return for_change(eng.cfg, eng.facts_now(), eng.changed(b), eng.is_source, eng.store, b)
