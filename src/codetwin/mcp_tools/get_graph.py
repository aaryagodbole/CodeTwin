from ..commands.graph import build
from ..engine import Engine


def register(mcp, root: str) -> None:
    @mcp.tool()
    def get_graph(file: str, start_line: int | None = None, end_line: int | None = None) -> dict:
        """Impact graph around a file or a line range: importers, dependencies, tests that execute it, and
        links the analysis cannot follow. Edges carry their evidence type (static, runtime, unresolved)."""
        lines = (start_line, end_line or start_line) if start_line else None
        return build(Engine(root), file, lines)
