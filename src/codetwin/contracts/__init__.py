"""OpenAPI / JSON-schema contract diff linked to consumer files and tests (this repository and connected ones).

Contract files are found automatically (`openapi*`, `swagger*`, `*.openapi.*`, `*.schema.json`, `schemas/*.json`)
or listed in `[contracts] files = [...]`. The version at the base commit is compared with the working tree.
Breaking changes are: removed paths, operations, parameters, response codes, schema properties and enum values;
type changes; parameters or properties that became required. Each one is linked to the code that may rely on it:
string literals of the path (with `{param}` matching any segment) and uses of a removed or changed field name,
in source files of this repository and of every repository in `[[repos]]`, with the tests that reach them.
A field-name match is a *possible* use (names are not unique), so it is labelled `name-match`.
"""
from __future__ import annotations

from .diff import ContractChange, diff_documents, find_contract_files
from .link import for_change

__all__ = ["ContractChange", "diff_documents", "find_contract_files", "for_change"]
