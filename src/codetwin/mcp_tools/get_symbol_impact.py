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
            ch = eng.change(require_run=False)
            facts = ch.facts_now
            base_facts = ch.static_base if ch.prev is not None else None
            hits = find(facts, path, query or "")
            return [symbol_impact(eng.root, facts, ch.prev, ch.tests_now, s, eng.lang.is_test, base_facts).to_dict()
                    for s in hits] \
                or [{"symbol": {"name": query, "file": path}, "unknowns": [f"no symbol '{query}' in {path}"]}]
