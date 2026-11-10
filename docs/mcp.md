# Using CodeTwin from an AI coding agent (MCP)

Install with the MCP extra and register the stdio server in your agent's MCP configuration.

```bash
pip install -e ".[mcp]"
```

Example configuration (Claude Code `.mcp.json`, Cursor `.cursor/mcp.json`, VS Code `.vscode/mcp.json`; the
outer key differs per client, the server entry is the same):

```json
{
  "mcpServers": {
    "codetwin": {
      "command": "codetwin-mcp",
      "env": { "CODETWIN_ROOT": "/path/to/project" }
    }
  }
}
```

The project must have a `.codetwin.toml` and a recorded run (`codetwin init && codetwin record`).

| Tool | Returns |
|---|---|
| `verify_change(alpha?)` | `proceed` or `run_more`, estimated residual risk, tests to run, reasons and unknowns |
| `get_impact(files)` | tests reaching the files, with evidence types, and unresolved links |
| `recommend_tests(budget?)` | highest-risk tests within a share of full-suite time, and the risk left |
| `explain_decision()` | numbers and reasons behind the last decision |

Suggested agent rule: *before opening a pull request, call `verify_change`; if the decision is `run_more`,
run the returned tests and report the result instead of overriding the decision.*
