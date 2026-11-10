# Web dashboard (planned)

React + Cytoscape.js front end for the team, guide and review panel.
Pages: system map, pull-request view, research results. It reads only the HTTP API in `src/codetwin/server/`,
which reads the same SQLite evidence store as the CLI.

Put the front-end project in this folder (`dashboard/package.json`, `dashboard/src/`); keep it separate from the
VS Code extension.
