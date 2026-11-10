# Roadmap

Plan from *CodeTwin AI – Final Objectives v4*. The task board with status lives in Notion
(**CodeTwin Product Tasks**); this file is the summary. Dates are a proposal; change them there.

Objectives: O1 evidence graph (within and across repositories) · O2 risk-ranked test recommendation with test
gaps · O3 calibrated residual risk with abstention · O4 delivery in VS Code, pull request, dashboard and MCP ·
O5 evaluation. Scope rule from the objectives doc: **Must** = U1, U2, U3, VS Code F1–F4, PR check.
Nothing in *Could* starts before the Must items are evaluated.

## Owners

| Area | Owner | Objectives |
|---|---|---|
| A – graph, cross-repo, contracts | Suhani | O1 |
| B – selection outputs, test gaps, evidence cards, PR check, dashboard API | Madhura | O2, O4 |
| C – calibration, risk, blind spots, LLM links, agents | Aarya | O3, O5 |
| D – VS Code extension, dashboard UI, legacy-code lens | Shreya | O4, E1 |

## Done

| Work | Objective |
|---|---|
| Engine, CLI, MCP server (`verify_change`, `get_impact`, `recommend_tests`, `explain_decision`), VS Code and Action skeletons, CI | O2, O3, O4 |
| Calibrated threshold (CRC + adaptive), residual risk `r(c)`, abstention (U2) | O3 |
| Study v2 and paper: 681 changes, 8 projects, 812 mutants, NameRTS comparison | O5 |

## Plan

| When | Owner | Work | Scope | Objective |
|---|---|---|---|---|
| 11–15 Nov | all | Set up environment, `scripts/check.sh` green on every laptop | Must | – |
| 26 Nov – 6 Dec | Suhani | Evidence self-check (every test mapped) and parser-coverage warning | Must | O1, O3 |
| 26 Nov – 6 Dec | Madhura | Test-gap report: changed lines no test executes (`codetwin gaps`, JSON, MCP) | Must | O2 |
| 26 Nov – 6 Dec | Aarya | Blind-spot list with file, line and reason in CLI JSON and MCP (U1) | Must | O1, O3 |
| 26 Nov – 13 Dec | Shreya | VS Code F3 blind-spot shading, F4 test-gap gutter | Must | O4 |
| 7 – 20 Dec | Suhani | Symbol-level impact: functions, classes, config keys | Must | O1 |
| 7 – 20 Dec | Madhura | Evidence cards for every recommended test | Must | O2 |
| 7 – 27 Dec | Aarya | Per-project model trained from `codetwin learn` history | Should | O2, O3 |
| 14 – 27 Dec | Shreya | VS Code F2 impact CodeLens | Must | O4 |
| 21 Dec – 10 Jan | Madhura | PR comment and check run in the GitHub Action | Must | O4 |
| 2 – 24 Jan | Suhani | Cross-repo: declared repositories, cross-repo edges, 2–3 library + dependents sets | Must | O1 |
| 2 – 24 Jan | Aarya | Evidence freshness in the risk number (U5, RQ5) | Should | O3 |
| 2 – 24 Jan | Shreya | VS Code F1 select-to-impact graph panel | Must | O4 |
| 11 – 31 Jan | Madhura | Dashboard API (`codetwin serve`, read-only over the evidence store) | Must | O4 |
| 25 Jan – 14 Feb | Suhani | OpenAPI / JSON-schema contract diff linked to consumers | Must | O1 |
| 25 Jan – 28 Feb | Aarya | LLM-suggested links verified by a runtime probe (U3, RQ6) – scope after guide's decision | Must | O1, O3 |
| 1 – 28 Feb | Shreya | Dashboard UI: system map, PR view, research results | Must | O4 |
| 15 Feb – 7 Mar | Suhani | Cross-repo evaluation with seeded API changes | Must | O1, O5 |
| 1 – 14 Mar | Aarya | Close-the-gap ranking (U4) | Should | O3 |
| 1 – 21 Mar | Shreya | Legacy-code lens / calibrated dead code (F6, E1) | Should | E1 |
| 15 – 28 Mar | Aarya | Agent experiment over MCP (RQ7) | Should | O4, O5 |
| 22 Mar – 10 Apr | all | Integration, 60-second demo, final evaluation rerun, merge into `main` | Must | O5 |

## Not now

Collision radar, executable review claims, promise monitor, conformal culprit set, failed-test triage (E2),
signed receipt (E4c). Out of scope: other languages, the financial graph module, automatic patching.
