# API and schema contracts

`codetwin contracts` compares every OpenAPI (2 or 3) and JSON-schema file at the base commit with the working tree.
Files are found automatically (`openapi*`, `swagger*`, `*.openapi.*`, `*.schema.json`, `schemas/*.json`) or listed:

```toml
[contracts]
files = ["api/openapi.yaml", "schemas/order.schema.json"]
```

**Breaking changes:** removed paths, operations, parameters, response codes, schemas, properties and enum values;
type changes; parameters or properties that became required. Added paths, operations and properties are listed
as non-breaking.

**Consumers.** Each breaking change is linked to code that may rely on it, in this repository and in every
repository declared in `[[repos]]` (`docs/crossrepo.md`):

- `path-literal`: a string with the API path (`{id}` matches any segment; `` `/users/${id}` `` and
  `"/users/" + id` count);
- `name-match`: a removed or changed field used as a key, attribute or argument (`"email"`, `.email`, `email:`).
  Names are not unique, so this is a *possible* use.

The tests that reach those files come from each repository's recorded run or static graph. A breaking change with
no consumer found is reported as **unknown** (the path may be built dynamically, or the clients live elsewhere),
never as safe.

Output: `codetwin contracts [--base REF] [--json] [--fail-on-breaking]`, the `contracts` section of
`codetwin select --json` (listed in the GitHub Action's job summary), and the MCP tool `get_contract_changes`.
