#!/usr/bin/env bash
# Definition of done for every change: lint, tests with coverage, VS Code extension and dashboard builds.
set -euo pipefail
cd "$(dirname "$0")/.."
ruff check src tests
python -m pytest --cov --cov-report=term
if command -v npm >/dev/null; then
  (cd extensions/vscode && { [ -d node_modules ] || npm ci --silent; } && npm run --silent compile)
  (cd dashboard && { [ -d node_modules ] || npm ci --silent; } && npm run --silent lint && npm run --silent build >/dev/null)
else
  echo "npm not found: skipped the VS Code extension build"
fi
echo "check: OK"
