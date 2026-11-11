from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def recommend_tests(budget: float = 0.25) -> dict:
        """Highest-risk tests that fit in the given share of full-suite time, with the risk left behind."""
        with Engine(root) as eng:
            return eng.select(budget=budget).to_dict()
