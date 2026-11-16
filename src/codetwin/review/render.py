"""Turn a Review into what each consumer needs.

* `markdown`  - the pull-request summary comment (updated in place thanks to MARKER)
* `github`    - a body for POST /repos/{owner}/{repo}/pulls/{n}/reviews with inline comments on diff lines
* `sarif`     - SARIF 2.1.0 for GitHub code scanning (github/codeql-action/upload-sarif) and other tools
* `json`      - Review.to_dict()
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import __version__
from .model import Finding, Review, Severity, Source
from .rules import RULES

MARKER = "<!-- codetwin-review -->"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_ICON = {Severity.CRITICAL: "🔴", Severity.HIGH: "🟠", Severity.MEDIUM: "🟡", Severity.LOW: "🔵", Severity.INFO: "⚪"}
MAX_INLINE = 30        # GitHub reviews with many comments are hard to read; the rest stay in the summary


def _loc(f: Finding) -> str:
    if not f.path:
        return "pull request"
    return f"`{f.path}`" + (f" line {f.start_line}" if f.start_line else "")


def _finding_md(f: Finding) -> str:
    tag = " _(AI suggestion, not verified)_" if f.source is Source.LLM else ""
    out = [f"{_ICON[f.severity]} **{f.title}**{tag} — {_loc(f)} · `{f.rule}`", "", f.message]
    if f.evidence:
        out += ["", "Evidence:"] + [f"- {e}" for e in f.evidence]
    if f.suggestion:
        out += ["", f"**Suggested:** {f.suggestion}"]
    return "\n".join(out)


def markdown(review: Review) -> str:
    c = review.counts()
    verdict = "⛔ Run more tests before merging" if review.decision == "abstain" else (
        "⚠️ Needs attention" if review.blocking else "✅ Evidence supports this change")
    target = f" (target {review.alpha:.0%})" if review.alpha is not None else ""
    lines = [MARKER, "## CodeTwin review", "",
             f"**{verdict}** · residual risk {'of the broader selection ' if review.decision == 'abstain' else ''}"
             f"**{review.residual_risk:.1%}**{target} · "
             f"{len(review.selected)} tests selected", "",
             "| Severity | " + " | ".join(s.value for s in Severity) + " |",
             "|---|" + "---|" * len(Severity),
             "| Findings | " + " | ".join(str(c[s.value]) for s in Severity) + " |", ""]
    if review.files:
        lines += ["<details><summary>Changed files</summary>", "", "| File | Changed lines | Selected tests covering it | Findings |",
                  "|---|---|---|---|"]
        lines += [f"| `{f.path}` | {f.changed_lines} | {', '.join(f'`{t}`' for t in f.tests[:3]) or '–'}"
                  f"{' …' if len(f.tests) > 3 else ''} | {f.findings} |" for f in review.files]
        lines += ["", "</details>", ""]
    if review.findings:
        lines += ["### Findings", ""]
        for f in review.findings:
            lines += [_finding_md(f), "", "---", ""]
    else:
        lines += ["No findings.", ""]
    if review.selected:
        lines += ["<details><summary>Selected tests</summary>", ""] + [f"- `{t}`" for t in review.selected] + ["", "</details>", ""]
    if review.notes:
        lines += ["<details><summary>Notes</summary>", ""] + [f"- {n}" for n in review.notes] + ["", "</details>", ""]
    lines.append(f"<sub>CodeTwin {__version__}. Evidence findings come from recorded coverage and static analysis; "
                 "AI suggestions are advisory.</sub>")
    return "\n".join(lines)


def github(review: Review, in_diff: Callable[[str | None, int | None], bool]) -> dict[str, Any]:
    """Body of a pull-request review. `in_diff(path, line)` tells whether GitHub accepts a comment there."""
    comments: list[dict[str, Any]] = []
    for f in review.findings:
        if len(comments) >= MAX_INLINE:
            break
        if f.path and f.start_line and in_diff(f.path, f.start_line):
            comments.append({"path": f.path, "line": f.start_line, "side": "RIGHT",
                             "body": f"{_finding_md(f)}\n\n<!-- codetwin-fp:{f.fingerprint} -->"})
    return {"event": "COMMENT", "body": f"CodeTwin found {len(review.findings)} items; see the summary comment.",
            "comments": comments}


def sarif(review: Review) -> dict[str, Any]:
    used = sorted({f.rule for f in review.findings})
    results = []
    for f in review.findings:
        r: dict[str, Any] = {"ruleId": f.rule, "level": f.severity.sarif_level,
                             "message": {"text": f"{f.title}. {f.message}"},
                             "partialFingerprints": {"codetwinFinding/v1": f.fingerprint},
                             "properties": {"severity": f.severity.value, "source": f.source.value,
                                            "evidence": f.evidence}}
        if f.path:
            region = {"startLine": f.start_line or 1}
            if f.end_line:
                region["endLine"] = f.end_line
            r["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": f.path}, "region": region}}]
        results.append(r)
    return {"$schema": SARIF_SCHEMA, "version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "CodeTwin", "semanticVersion": __version__,
                            "informationUri": "https://github.com/aaryagodbole/CodeTwin",
                            "rules": [{"id": i, "name": RULES[i].name, "shortDescription": {"text": RULES[i].short},
                                       "help": {"text": RULES[i].help}} for i in used if i in RULES]}},
        "results": results}]}
