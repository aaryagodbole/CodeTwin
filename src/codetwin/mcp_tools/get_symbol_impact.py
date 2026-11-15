from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def get_symbol_impact(target: str) -> list[dict]:
        """Impact of one function, method or class, given as "path:Name", "path:Class.method" or "path:line":
        the tests that execute it (runtime coverage) or reach its callers, the code that refers to it, and what
        the analysis cannot see (dynamic calls, unparsed files, test gaps)."""
        from ..graph.symbols import find, parse_target, symbol_impact
        path, query = parse_target(target)
        with Engine(root) as eng:
            facts = eng.facts_now()
            base = eng.store.latest_run_sha()
            run = eng.store.get_run(base) if base else None
            hits = find(facts, path, query or "")
            return [symbol_impact(eng.root, facts, run, eng.tests_now(), s, eng.lang.is_test).to_dict() for s in hits] \
                or [{"symbol": {"name": query, "file": path}, "unknowns": [f"no symbol '{query}' in {path}"]}]
