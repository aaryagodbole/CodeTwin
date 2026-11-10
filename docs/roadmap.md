# Roadmap

Objectives from the synopsis: O1 evidence graph · O2 risk-ranked selection · O3 calibrated residual risk with
abstention · O4 developer and agent integration · O5 evaluation.

| Phase | Work | Objective | Proposed owner | Status |
|---|---|---|---|---|
| 0 | Project skeleton: engine, CLI, MCP server, VS Code and Action skeletons, CI | all | Aarya | done |
| 1 | Evidence: robust coverage collection (xdist, timeouts), non-Python files, stale-evidence check | O1 | Suhani | next |
| 1 | Store and graph: evidence cards (claim, source, method, time, status), graph queries by symbol | O1 | Madhura | next |
| 2 | Risk: train the model from `codetwin learn` history; per-project model files; trigger rules as features | O2, O3 | Aarya | next |
| 2 | VS Code: select-to-impact panel (webview graph), impact CodeLens, blind-spot highlighting, test-gap gutter | O4 | Shreya | next |
| 3 | GitHub Action: PR comment with decision and risk, merge gate ("risk-bearing receipt") | O4 | Madhura | later |
| 3 | MCP: agent-in-the-loop demo with an AI coding agent; `ask_human` decision | O4 | Aarya | later |
| 4 | Cross-repository evidence (API contracts, consumer repos), second language adapter (tree-sitter) | O1 | Suhani | stretch |
| 4 | Verified LLM link suggestions (H4) | O1, O3 | Shreya | stretch |
| 5 | Evaluation on larger projects; demo project for the final review | O5 | all | later |

Owners are a proposal; change them in Notion.
