"""MCP server: lets AI coding agents ask CodeTwin before they submit a change.

Tools (Table IV of the paper): verify_change, get_impact, recommend_tests, explain_decision.
Run with `codetwin-mcp` (stdio) from the repository root.
"""
from __future__ import annotations

import os


def build_server(root: str = "."):
    try:                                    # MCP Python SDK 2.x
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:                     # SDK 1.x
        from mcp.server.fastmcp import FastMCP as Server

    from .engine import Engine

    mcp = Server("codetwin")

    @mcp.tool()
    def verify_change(alpha: float | None = None) -> dict:
        """Decide whether the current working-tree change can proceed with a selected set of tests.
        Returns proceed, or abstain (run the broader selection / ask a human), the estimated residual
        risk, the selected tests and the reasons, including what the analysis cannot see."""
        d = Engine(root).select(alpha=alpha)
        action = "proceed" if d.decision == "proceed" else "run_more"
        return {"decision": action, "residual_risk": d.residual_risk, "tests": sorted(d.selected), "reasons": d.reasons}

    @mcp.tool()
    def get_impact(files: list[str]) -> dict:
        """Tests that reach the given source files, with how each link was found, and unresolved links."""
        imp = Engine(root).impact(files)
        return {"tests": {t: sorted(v) for t, v in imp.tests.items()}, "unknowns": imp.unknowns}

    @mcp.tool()
    def recommend_tests(budget: float = 0.25) -> dict:
        """Highest-risk tests that fit in the given share of full-suite time, with the risk left behind."""
        d = Engine(root).select(budget=budget)
        return {"tests": sorted(d.selected), "residual_risk": d.residual_risk, "reasons": d.reasons}

    @mcp.tool()
    def explain_decision() -> dict:
        """The evidence and numbers behind the last decision."""
        return Engine(root).explain()

    return mcp


def main() -> None:
    build_server(os.environ.get("CODETWIN_ROOT", ".")).run()


if __name__ == "__main__":
    main()
