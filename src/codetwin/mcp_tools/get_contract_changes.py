from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def get_contract_changes(base: str | None = None) -> dict:
        """Breaking OpenAPI / JSON-schema changes between `base` (default: last recorded run) and the working tree:
        removed paths, operations, parameters, responses, properties and enum values, type changes, new required
        fields. Each is linked to code sites (path literals, field-name uses) in this and connected repositories,
        and to the tests that reach them; anything not found is listed as unknown."""
        from ..contracts import for_change
        with Engine(root) as eng:
            return for_change(eng.cfg, eng.lang, eng.change(base, require_run=False).base, eng.store)
