from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def explain_decision() -> dict:
        """The evidence and numbers behind the last decision."""
        return Engine(root).explain()
