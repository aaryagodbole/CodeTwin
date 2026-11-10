from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def verify_change(alpha: float | None = None) -> dict:
        """Decide whether the current working-tree change can proceed with a selected set of tests.
        Returns proceed, or run_more (run the broader selection), the estimated residual risk, the
        selected tests, the reasons (including what the analysis cannot see) and extra report sections."""
        d = Engine(root).select(alpha=alpha).to_dict()
        d["decision"] = "proceed" if d["decision"] == "proceed" else "run_more"
        return d
