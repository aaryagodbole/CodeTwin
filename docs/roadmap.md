# Roadmap

Plan from *CodeTwin AI – Final Objectives v4*. The task board with status lives in Notion
(**CodeTwin Product Tasks**), including who works on what; this file is the summary.

Objectives: O1 evidence graph (within and across repositories) · O2 risk-ranked test recommendation with test
gaps · O3 calibrated residual risk with abstention · O4 delivery in VS Code, pull request, dashboard and MCP ·
O5 evaluation. Scope rule from the objectives doc: **Must** = U1, U2, U3, VS Code F1–F4, PR check.
Nothing in *Could* starts before the Must items are evaluated.

## Done

| Work | Objective |
|---|---|
| Engine, CLI, MCP server (`verify_change`, `get_impact`, `get_graph`, `recommend_tests`, `explain_decision`), Action skeleton, CI and release workflow | O2, O3, O4 |
| VS Code: impact graph of a selection beside the editor (F1, file-level and line-level), hover summary | O4 |
| Web dashboard skeleton (Next.js): overview, system map, decisions, results, impact graph; `codetwin serve` API | O4 |
| Calibrated threshold (CRC + adaptive), residual risk `r(c)`, abstention (U2) | O3 |
| Study v2 and paper: 681 changes, 8 projects, 812 mutants, NameRTS comparison | O5 |

## Plan

| When | Work | Scope | Objective |
|---|---|---|---|
| 11–15 Nov | Set up environment, `scripts/check.sh` green on every laptop | Must | – |
| 26 Nov – 6 Dec | Blind-spot list with file, line and reason in CLI JSON and MCP (U1) | Must | O1, O3 |
| 26 Nov – 6 Dec | Evidence self-check (every test mapped) and parser-coverage warning | Must | O1, O3 |
| 26 Nov – 6 Dec | Test-gap report: changed lines no test executes (`codetwin gaps`, JSON, MCP) | Must | O2 |
| 26 Nov – 13 Dec | VS Code F3 blind-spot shading, F4 test-gap gutter | Must | O4 |
| 7 – 20 Dec | Symbol-level impact: functions, classes, config keys | Must | O1 |
| 7 – 20 Dec | Evidence cards for every recommended test | Must | O2 |
| 7 – 27 Dec | PR comment and check run in the GitHub Action | Must | O4 |
| 14 – 27 Dec | VS Code F2 impact CodeLens | Must | O4 |
| 21 Dec – 10 Jan | Per-project model trained from `codetwin learn` history | Should | O2, O3 |
| 2 – 24 Jan | Cross-repo: declared repositories, cross-repo edges, 2–3 library + dependents sets | Must | O1 |
| 2 – 24 Jan | Evidence freshness in the risk number (U5, RQ5) | Should | O3 |
| 2 – 24 Jan | VS Code F1: symbol-level graph, cross-repo consumers in the panel | Must | O4 |
| 11 – 31 Jan | Dashboard API: pull-request view, evidence cards, test gaps endpoints | Must | O4 |
| 25 Jan – 14 Feb | OpenAPI / JSON-schema contract diff linked to consumers | Must | O1 |
| 25 Jan – 28 Feb | LLM-suggested links verified by a runtime probe (U3, RQ6) – scope after guide's decision | Must | O1, O3 |
| 1 – 28 Feb | Dashboard UI: pull-request view, risk-budget slider, recall-vs-budget plot | Must | O4 |
| 15 Feb – 7 Mar | Cross-repo evaluation with seeded API changes | Must | O1, O5 |
| 1 – 14 Mar | Close-the-gap ranking (U4) | Should | O3 |
| 1 – 21 Mar | Legacy-code lens / calibrated dead code (F6, E1) | Should | E1 |
| 8 – 21 Mar | Agent experiment over MCP (RQ7) | Should | O4, O5 |
| 22 Mar – 10 Apr | Integration, 60-second demo, final evaluation rerun, merge into `main` | Must | O5 |

## Not now

Collision radar, executable review claims, promise monitor, conformal culprit set, failed-test triage (E2),
signed receipt (E4c). Out of scope: the financial graph module, automatic patching. (Other languages were added in
November 2026: `src/codetwin/lang/`, docs/languages.md.)
