#!/usr/bin/env bash
# Definition of done for every change: lint, tests and the VS Code extension build.
set -euo pipefail
cd "$(dirname "$0")/.."
ruff check src tests
python -m pytest
if command -v npm >/dev/null; then
  (cd extensions/vscode && { [ -d node_modules ] || npm install --silent; } && npm run --silent compile)
else
  echo "npm not found: skipped the VS Code extension build"
fi
echo "check: OK"
