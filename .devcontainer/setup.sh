#!/usr/bin/env bash
# One-time setup of a Codespace / dev container: everything scripts/check.sh needs.
set -euo pipefail
pip install -e ".[dev,mcp,server]" pre-commit
pre-commit install
(cd extensions/vscode && npm ci)
(cd dashboard && npm ci)
echo "Ready. Run scripts/check.sh, or: codetwin serve  /  cd dashboard && npm run dev"
