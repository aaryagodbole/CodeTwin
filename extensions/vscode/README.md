# CodeTwin AI for VS Code (preview)

See which tests your change needs, what the analysis cannot see, and how much risk is left if you run only
those tests.

## Features

- **Impact graph of a selection.** Select code (or put the cursor in a function) and run
  *CodeTwin: Show impact graph of selection* (right-click, or `Ctrl+Alt+I` / `Cmd+Alt+I`). A graph opens beside
  the editor: files that import it, files it imports, tests that execute the selected lines, and links that
  cannot be followed. Line style shows how each link is known: solid grey static, blue runtime (coverage),
  orange dashed co-change, grey dotted unresolved. Click a node to open the file. The graph follows your
  selection while it is open.
- **Hover summary.** Hover a function, class or selection: `used by N · M tests · K unknown`, with a link to
  the graph.
- **Select tests for my change.** Decision (proceed / run more), estimated residual risk, selected tests and
  reasons; the status bar shows the last decision.
- **Record evidence** and **Explain last decision**.

## Requirements

- The `codetwin` command-line tool (Python 3.11+). If it is missing, the extension offers to install it.
- A Python project with a pytest suite. Run *CodeTwin: Record evidence* once on a clean checkout so that
  runtime (coverage) links are known.

## Settings

| Setting | Default | |
|---|---|---|
| `codetwin.cliPath` | `codetwin` | path to the CLI |
| `codetwin.alpha` | `0.1` | target miss rate |
| `codetwin.graph.hover` | `true` | hover summary |
| `codetwin.graph.followSelection` | `true` | update the graph as the selection changes |
| `codetwin.installCommand` | pip install | command used to install the CLI |

## Development

`npm install && npm run compile`, then press F5 to start an Extension Development Host.
Each feature is one file in `src/features/` (see `AGENTS.md`).
