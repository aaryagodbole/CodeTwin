"""MCP server: lets AI coding agents ask CodeTwin before they submit a change.

Tools live in ``codetwin/mcp_tools/`` (one file each, auto-discovered).
Run with `codetwin-mcp` (stdio) from the repository root.
"""
from __future__ import annotations

import os

from .plugins import discover


def build_server(root: str = "."):
    try:                                    # MCP Python SDK 2.x
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:                     # SDK 1.x
        from mcp.server.fastmcp import FastMCP as Server  # type: ignore[attr-defined,no-redef]

    mcp = Server("codetwin")
    for mod in discover("codetwin.mcp_tools"):
        mod.register(mcp, root)
    return mcp


def main() -> None:
    build_server(os.environ.get("CODETWIN_ROOT", ".")).run()


if __name__ == "__main__":
    main()
