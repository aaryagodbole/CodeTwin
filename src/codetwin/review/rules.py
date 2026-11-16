"""Catalogue of review rules. Every finding names one of these ids.

Keeping ids stable lets teams suppress a rule, lets SARIF consumers group alerts, and lets the paper refer to a
rule by number. Add a rule here before an analyzer uses it; never reuse or renumber an id.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    short: str
    help: str


RULES: dict[str, Rule] = {r.id: r for r in [
    Rule("CT001", "residual-risk-above-target",
         "The estimated chance that a skipped test is affected is above the target.",
         "CodeTwin abstained: the evidence is too weak to skip tests safely. Run the broader suite before merging."),
    Rule("CT002", "untested-changed-symbol",
         "A changed function, method or class was not executed by any test before the change.",
         "No recorded test runs this code, so no selection can catch a regression in it. Add a test."),
    Rule("CT003", "unresolved-dependency",
         "The change touches code whose dependencies cannot be followed statically.",
         "Dynamic calls (getattr, reflection, string imports) hide callers. The impact may be larger than shown."),
    Rule("CT004", "breaking-contract-change",
         "An API contract (OpenAPI / JSON Schema) changed in a breaking way.",
         "Consumers of the contract may fail. Check the listed consumers and their tests."),
    Rule("CT005", "cross-repository-consumer",
         "Code in a connected repository uses what this change modifies.",
         "Run or ask for the tests of the consuming repository before releasing."),
    Rule("CT006", "no-evidence-for-file",
         "A changed source file has no recorded evidence (new or never parsed).",
         "Record a run on the base branch (codetwin record) so the file's tests are known."),
    Rule("CT007", "semantic-no-op",
         "The change does not alter behaviour (formatting, comments, annotations).",
         "No test needs to run for these lines."),
    Rule("CT100", "llm-review-comment",
         "Advisory comment from a language model.",
         "Not verified by evidence. Treat as a suggestion from a reviewer who has not run the code."),
]}
